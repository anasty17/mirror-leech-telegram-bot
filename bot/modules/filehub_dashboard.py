from datetime import datetime, timezone

from .. import DOWNLOAD_DIR, queued_dl, queued_up, task_dict, task_dict_lock
from ..core.branding import APP_NAME
from ..core.filehub_platform import HEALTH, HISTORY, PROVIDERS, QUOTAS, WORKFLOWS
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.status_utils import get_readable_file_size
from ..helper.telegram_helper.message_utils import send_message


def _bar(value: float, width: int = 10) -> str:
    value = max(0.0, min(100.0, value))
    filled = round((value / 100) * width)
    return "█" * filled + "░" * (width - filled)


def _status_icon(status: str) -> str:
    return {
        "healthy": "🟢",
        "degraded": "🟡",
        "offline": "⚪",
        "disabled": "⚪",
        "unhealthy": "🔴",
    }.get(status, "⚪")


@new_task
async def filehub_dashboard(_, message):
    from psutil import cpu_percent, disk_usage, virtual_memory

    cpu = cpu_percent()
    ram = virtual_memory().percent
    disk = disk_usage(DOWNLOAD_DIR)
    async with task_dict_lock:
        active = len(task_dict)
    queued = len(queued_dl) + len(queued_up)

    text = (
        f"<b>⚡ {APP_NAME} Control Center</b>\n\n"
        f"<b>Tasks</b>\n"
        f"• Active: <code>{active}</code>\n"
        f"• Queued: <code>{queued}</code>\n\n"
        f"<b>System</b>\n"
        f"• CPU  {_bar(cpu)} <code>{cpu:.1f}%</code>\n"
        f"• RAM  {_bar(ram)} <code>{ram:.1f}%</code>\n"
        f"• Disk {_bar(disk.percent)} <code>{disk.percent:.1f}%</code>\n"
        f"• Free <code>{get_readable_file_size(disk.free)}</code>\n\n"
        f"<b>Platform</b>\n"
        f"• Storage adapters: <code>{len(PROVIDERS.storage_names())}</code>\n"
        f"• Workflow actions: <code>{len(PROVIDERS.action_names())}</code>\n\n"
        "Use /doctor for backend health, /history for completed work, "
        "/quota for limits, /workers for worker state and /workflows for saved pipelines."
    )
    await send_message(message, text)


@new_task
async def filehub_doctor(_, message):
    results = await HEALTH.check()
    lines = [f"<b>🩺 {APP_NAME} Doctor</b>", ""]
    healthy = 0
    for result in results:
        if result.status == "healthy":
            healthy += 1
        detail = f" — <code>{result.detail}</code>" if result.detail else ""
        lines.append(f"{_status_icon(result.status)} <b>{result.name}</b>: {result.status}{detail}")
    lines.extend(["", f"Healthy checks: <code>{healthy}/{len(results)}</code>"])
    await send_message(message, "\n".join(lines))


@new_task
async def filehub_history(_, message):
    user_id = message.from_user.id
    rows = await HISTORY.recent(user_id=user_id, limit=10)
    if not rows:
        await send_message(
            message,
            "<b>🕘 FileHub History</b>\n\nNo persistent history yet. MongoDB must be configured and task lifecycle events must be recorded.",
        )
        return
    lines = ["<b>🕘 FileHub History</b>", ""]
    for row in rows:
        status = row.get("status", "unknown")
        action = row.get("action", "task")
        engine = row.get("engine") or "auto"
        size = get_readable_file_size(int(row.get("size", 0)))
        lines.append(f"• <b>{action}</b> · {status} · <code>{engine}</code> · {size}")
    await send_message(message, "\n".join(lines))


@new_task
async def filehub_quota(_, message):
    user_id = message.from_user.id
    policy = QUOTAS.default
    active = await QUOTAS.active_tasks(user_id)
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    daily = await HISTORY.usage_bytes(user_id, day_start)
    monthly = await HISTORY.usage_bytes(user_id, month_start)
    text = (
        "<b>📊 FileHub Quota</b>\n\n"
        f"• Active tasks: <code>{active}/{policy.max_concurrent_tasks or '∞'}</code>\n"
        f"• Daily transfer: <code>{get_readable_file_size(daily)}</code>"
        f" / <code>{get_readable_file_size(policy.max_daily_bytes) if policy.max_daily_bytes else '∞'}</code>\n"
        f"• Monthly transfer: <code>{get_readable_file_size(monthly)}</code>"
        f" / <code>{get_readable_file_size(policy.max_monthly_bytes) if policy.max_monthly_bytes else '∞'}</code>\n"
        f"• Command rate: <code>{policy.commands_per_minute}/minute</code>"
    )
    await send_message(message, text)


@new_task
async def filehub_workers(_, message):
    results = await HEALTH.check()
    unhealthy = [item for item in results if item.status not in {"healthy", "disabled", "offline"}]
    async with task_dict_lock:
        active = len(task_dict)
    state = "degraded" if unhealthy else "ready"
    text = (
        "<b>🖥 FileHub Workers</b>\n\n"
        "<b>local</b>\n"
        f"• State: <code>{state}</code>\n"
        f"• Active tasks: <code>{active}</code>\n"
        f"• Queue: <code>{len(queued_dl) + len(queued_up)}</code>\n"
        f"• Backend warnings: <code>{len(unhealthy)}</code>\n\n"
        "Multi-node registration is supported by the new platform layer; additional workers can be attached through the provider/worker registry in the next integration stage."
    )
    await send_message(message, text)


@new_task
async def filehub_workflows(_, message):
    user_id = message.from_user.id
    rows = await WORKFLOWS.list(user_id)
    if not rows:
        await send_message(
            message,
            "<b>🔁 FileHub Workflows</b>\n\nNo saved workflows. Workflow persistence is available when MongoDB is configured. Registered actions: "
            + (", ".join(f"<code>{x}</code>" for x in PROVIDERS.action_names()) or "<code>none</code>"),
        )
        return
    lines = ["<b>🔁 FileHub Workflows</b>", ""]
    for row in rows[:20]:
        steps = row.get("steps", [])
        enabled = "✅" if row.get("enabled", True) else "⏸"
        lines.append(f"{enabled} <b>{row.get('name', 'workflow')}</b> · {len(steps)} steps")
    await send_message(message, "\n".join(lines))
