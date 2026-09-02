from __future__ import annotations

from abc import ABC, abstractmethod
from asyncio import Lock, gather
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from inspect import isawaitable
from time import monotonic
from typing import Any, Awaitable, Callable

from psutil import cpu_percent, disk_usage, virtual_memory

from .. import DOWNLOAD_DIR, LOGGER, sabnzbd_client, task_dict, task_dict_lock
from ..helper.ext_utils.db_handler import database
from .jdownloader_booter import jdownloader
from .torrent_manager import TorrentManager


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class FileHubEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)


class EventBus:
    """Small async event bus used by task history, metrics and future plugins."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[[FileHubEvent], Any]]] = defaultdict(list)
        self._lock = Lock()

    async def subscribe(self, event_name: str, listener: Callable[[FileHubEvent], Any]) -> None:
        async with self._lock:
            if listener not in self._listeners[event_name]:
                self._listeners[event_name].append(listener)

    async def publish(self, event_name: str, **payload: Any) -> None:
        event = FileHubEvent(event_name, payload)
        async with self._lock:
            listeners = [*self._listeners.get(event_name, ()), *self._listeners.get("*", ())]
        if not listeners:
            return
        results = []
        for listener in listeners:
            try:
                result = listener(event)
                if isawaitable(result):
                    results.append(result)
            except Exception as exc:
                LOGGER.exception("FileHub event listener failed for %s: %s", event_name, exc)
        if results:
            await gather(*results, return_exceptions=True)


EVENTS = EventBus()


@dataclass(slots=True)
class HistoryRecord:
    task_id: str
    user_id: int
    action: str
    status: str
    source: str = ""
    destination: str = ""
    size: int = 0
    engine: str = ""
    error: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


class HistoryStore:
    """Persistent task/audit history when MongoDB is configured."""

    collection_name = "filehub_history"

    async def upsert(self, record: HistoryRecord) -> None:
        if database.db is None:
            return
        data = asdict(record)
        await database.db[self.collection_name].update_one(
            {"task_id": record.task_id}, {"$set": data}, upsert=True
        )

    async def recent(self, user_id: int | None = None, limit: int = 10) -> list[dict[str, Any]]:
        if database.db is None:
            return []
        query = {"user_id": user_id} if user_id else {}
        cursor = database.db[self.collection_name].find(query).sort("updated_at", -1).limit(max(1, min(limit, 50)))
        return [row async for row in cursor]

    async def usage_bytes(self, user_id: int, since: datetime | None = None) -> int:
        if database.db is None:
            return 0
        match: dict[str, Any] = {"user_id": user_id, "status": "completed"}
        if since is not None:
            match["updated_at"] = {"$gte": since}
        pipeline = [{"$match": match}, {"$group": {"_id": None, "total": {"$sum": "$size"}}}]
        rows = database.db[self.collection_name].aggregate(pipeline)
        async for row in rows:
            return int(row.get("total", 0))
        return 0


HISTORY = HistoryStore()


@dataclass(slots=True)
class QuotaPolicy:
    max_concurrent_tasks: int = 3
    max_daily_bytes: int = 0
    max_monthly_bytes: int = 0
    commands_per_minute: int = 30


class QuotaManager:
    """Fair-use limits with real active-task accounting and rolling command rate limits."""

    def __init__(self) -> None:
        self.default = QuotaPolicy()
        self._rates: dict[int, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def active_tasks(self, user_id: int) -> int:
        async with task_dict_lock:
            return sum(
                1
                for task in task_dict.values()
                if getattr(getattr(task, "listener", None), "user_id", None) == user_id
            )

    async def check_concurrency(self, user_id: int, policy: QuotaPolicy | None = None) -> tuple[bool, str]:
        policy = policy or self.default
        active = await self.active_tasks(user_id)
        if policy.max_concurrent_tasks and active >= policy.max_concurrent_tasks:
            return False, f"Concurrent task limit reached ({active}/{policy.max_concurrent_tasks})."
        return True, "ok"

    async def consume_command(self, user_id: int, policy: QuotaPolicy | None = None) -> tuple[bool, str]:
        policy = policy or self.default
        if not policy.commands_per_minute:
            return True, "ok"
        now = monotonic()
        cutoff = now - 60
        async with self._lock:
            bucket = self._rates[user_id]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= policy.commands_per_minute:
                return False, "Command rate limit reached. Try again shortly."
            bucket.append(now)
        return True, "ok"


QUOTAS = QuotaManager()


class StorageBackend(ABC):
    """Common contract for Drive/rclone/S3/WebDAV/Telegram storage adapters."""

    name: str

    @abstractmethod
    async def stat(self, path: str) -> dict[str, Any]: ...

    @abstractmethod
    async def list(self, path: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def upload(self, local_path: str, destination: str, **options: Any) -> Any: ...

    @abstractmethod
    async def download(self, source: str, local_path: str, **options: Any) -> Any: ...

    async def copy(self, source: str, destination: str, **options: Any) -> Any:
        raise NotImplementedError(f"{self.name} does not support server-side copy")

    async def delete(self, path: str) -> None:
        raise NotImplementedError(f"{self.name} does not support deletion")


class ProviderRegistry:
    def __init__(self) -> None:
        self._storage: dict[str, StorageBackend] = {}
        self._workflow_actions: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register_storage(self, backend: StorageBackend) -> None:
        key = backend.name.lower().strip()
        if not key:
            raise ValueError("Storage backend name cannot be empty")
        self._storage[key] = backend

    def storage(self, name: str) -> StorageBackend:
        return self._storage[name.lower()]

    def storage_names(self) -> list[str]:
        return sorted(self._storage)

    def register_action(self, name: str, handler: Callable[..., Awaitable[Any]]) -> None:
        self._workflow_actions[name.lower()] = handler

    def action(self, name: str) -> Callable[..., Awaitable[Any]]:
        return self._workflow_actions[name.lower()]

    def action_names(self) -> list[str]:
        return sorted(self._workflow_actions)


PROVIDERS = ProviderRegistry()


@dataclass(slots=True)
class WorkflowStep:
    action: str
    options: dict[str, Any] = field(default_factory=dict)
    continue_on_error: bool = False


@dataclass(slots=True)
class WorkflowDefinition:
    name: str
    steps: list[WorkflowStep]
    owner_id: int = 0
    enabled: bool = True


class WorkflowEngine:
    collection_name = "filehub_workflows"

    async def save(self, workflow: WorkflowDefinition) -> None:
        if database.db is None:
            raise RuntimeError("MongoDB is required for persistent workflows")
        doc = {
            "name": workflow.name,
            "owner_id": workflow.owner_id,
            "enabled": workflow.enabled,
            "steps": [asdict(step) for step in workflow.steps],
            "updated_at": utcnow(),
        }
        await database.db[self.collection_name].replace_one(
            {"name": workflow.name, "owner_id": workflow.owner_id}, doc, upsert=True
        )

    async def list(self, owner_id: int) -> list[dict[str, Any]]:
        if database.db is None:
            return []
        cursor = database.db[self.collection_name].find({"owner_id": owner_id}).sort("name", 1)
        return [row async for row in cursor]

    async def run(self, workflow: WorkflowDefinition, context: dict[str, Any]) -> dict[str, Any]:
        result = dict(context)
        await EVENTS.publish("workflow.started", workflow=workflow.name, context=result)
        for index, step in enumerate(workflow.steps):
            handler = PROVIDERS.action(step.action)
            try:
                output = await handler(result, **step.options)
                if isinstance(output, dict):
                    result.update(output)
                await EVENTS.publish(
                    "workflow.step.completed", workflow=workflow.name, index=index, action=step.action
                )
            except Exception as exc:
                await EVENTS.publish(
                    "workflow.step.failed",
                    workflow=workflow.name,
                    index=index,
                    action=step.action,
                    error=str(exc),
                )
                if not step.continue_on_error:
                    raise
        await EVENTS.publish("workflow.completed", workflow=workflow.name, context=result)
        return result


WORKFLOWS = WorkflowEngine()


@dataclass(slots=True)
class HealthResult:
    name: str
    status: str
    detail: str = ""


class HealthMonitor:
    async def _mongo(self) -> HealthResult:
        if database.db is None:
            return HealthResult("MongoDB", "disabled", "No active database connection")
        try:
            await database.db.command("ping")
            return HealthResult("MongoDB", "healthy")
        except Exception as exc:
            return HealthResult("MongoDB", "unhealthy", str(exc)[:120])

    async def _aria2(self) -> HealthResult:
        try:
            await TorrentManager.aria2.getVersion()
            return HealthResult("aria2", "healthy")
        except Exception as exc:
            return HealthResult("aria2", "unhealthy", str(exc)[:120])

    async def _qbittorrent(self) -> HealthResult:
        try:
            version = await TorrentManager.qbittorrent.app.version()
            return HealthResult("qBittorrent", "healthy", str(version))
        except Exception as exc:
            return HealthResult("qBittorrent", "unhealthy", str(exc)[:120])

    async def _sabnzbd(self) -> HealthResult:
        try:
            if not sabnzbd_client.LOGGED_IN:
                return HealthResult("SABnzbd", "degraded", "Client not logged in")
            await sabnzbd_client.get_downloads()
            return HealthResult("SABnzbd", "healthy")
        except Exception as exc:
            return HealthResult("SABnzbd", "unhealthy", str(exc)[:120])

    async def _jdownloader(self) -> HealthResult:
        return HealthResult(
            "JDownloader",
            "healthy" if jdownloader.is_connected else "offline",
        )

    async def check(self) -> list[HealthResult]:
        system = [
            HealthResult("CPU", "healthy", f"{cpu_percent()}%"),
            HealthResult("RAM", "healthy", f"{virtual_memory().percent}%"),
        ]
        disk = disk_usage(DOWNLOAD_DIR)
        disk_status = "degraded" if disk.percent >= 90 else "healthy"
        system.append(HealthResult("Disk", disk_status, f"{disk.percent}% used"))
        backend = await gather(
            self._mongo(), self._aria2(), self._qbittorrent(), self._sabnzbd(), self._jdownloader()
        )
        return system + list(backend)


HEALTH = HealthMonitor()


async def task_snapshots() -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    async with task_dict_lock:
        tasks = list(task_dict.items())
    for message_id, task in tasks:
        listener = getattr(task, "listener", None)
        obj = task.task() if callable(getattr(task, "task", None)) else task
        status_method = getattr(task, "status", None)
        try:
            status = await status_method() if callable(status_method) and isawaitable(status_method()) else (
                status_method() if callable(status_method) else "unknown"
            )
        except Exception:
            status = "unknown"
        snapshots.append(
            {
                "message_id": message_id,
                "user_id": getattr(listener, "user_id", 0),
                "name": getattr(obj, "name", lambda: "")() if callable(getattr(obj, "name", None)) else str(getattr(obj, "name", "")),
                "status": status,
                "engine": getattr(task, "tool", ""),
            }
        )
    return snapshots
