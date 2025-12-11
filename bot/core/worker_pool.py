"""
Worker Bot Session Pool Module

Manages a pool of Telegram bot sessions for parallel file uploads.
Provides load balancing, health monitoring, and automatic recovery.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, Optional, List, TYPE_CHECKING
from asyncio import Lock, Event, create_task, sleep, gather
from pyrogram import Client, enums
from time import time
from logging import getLogger
from os import makedirs, path as ospath

from ..helper.ext_utils.metrics import get_metrics

if TYPE_CHECKING:
    from .config_manager import Config

LOGGER = getLogger(__name__)

# Session storage directory
SESSION_DIR = ospath.join(ospath.dirname(ospath.dirname(ospath.dirname(__file__))), "sessions")


class WorkerState(Enum):
    """Possible states for a worker session."""
    INITIALIZING = auto()
    READY = auto()
    BUSY = auto()
    RATE_LIMITED = auto()
    OFFLINE = auto()
    FAILED = auto()


@dataclass
class WorkerMetrics:
    """Metrics tracked for each worker session."""
    # Upload metrics
    uploads_completed: int = 0
    uploads_failed: int = 0
    bytes_uploaded: int = 0
    total_upload_time: float = 0.0
    # Download metrics
    downloads_completed: int = 0
    downloads_failed: int = 0
    bytes_downloaded: int = 0
    total_download_time: float = 0.0
    # Common metrics
    current_task_id: Optional[str] = None
    last_activity: float = field(default_factory=time)
    rate_limit_until: float = 0.0
    consecutive_failures: int = 0
    # Performance tracking for adaptive scheduling
    recent_speeds: List[float] = field(default_factory=list)  # Last 10 speeds
    ops_timestamps: List[float] = field(default_factory=list)  # For rate limit prediction
    
    def record_speed(self, bytes_per_sec: float) -> None:
        """Record a transfer speed for adaptive scheduling."""
        self.recent_speeds.append(bytes_per_sec)
        if len(self.recent_speeds) > 10:
            self.recent_speeds.pop(0)
    
    def record_operation(self) -> None:
        """Record an operation timestamp for rate limit prediction."""
        now = time()
        self.ops_timestamps.append(now)
        # Keep only last 30 timestamps
        cutoff = now - 120  # 2 minute window
        self.ops_timestamps = [t for t in self.ops_timestamps if t > cutoff]
    
    def effective_speed(self) -> float:
        """Get weighted recent speed for adaptive scheduling."""
        if len(self.recent_speeds) >= 3:
            # Use last 5 speeds, weighted towards recent
            recent = self.recent_speeds[-5:] if len(self.recent_speeds) >= 5 else self.recent_speeds
            return sum(recent) / len(recent)
        return 0.0
    
    def ops_per_minute(self) -> int:
        """Count operations in last minute for rate limit prediction."""
        cutoff = time() - 60
        return sum(1 for t in self.ops_timestamps if t > cutoff)


@dataclass
class WorkerSession:
    """Represents a single worker bot session."""
    session_id: str
    client: Client
    bot_username: str = ""
    state: WorkerState = WorkerState.INITIALIZING
    metrics: WorkerMetrics = field(default_factory=WorkerMetrics)
    lock: Lock = field(default_factory=Lock)
    
    @property
    def is_available(self) -> bool:
        """Check if worker is available for new tasks."""
        return self.state == WorkerState.READY
    
    @property
    def is_rate_limited(self) -> bool:
        """Check if worker is currently rate-limited."""
        return (
            self.state == WorkerState.RATE_LIMITED 
            or time() < self.metrics.rate_limit_until
        )
    
    def avg_upload_speed(self) -> float:
        """Calculate average upload speed in bytes/second."""
        if self.metrics.total_upload_time > 0:
            return self.metrics.bytes_uploaded / self.metrics.total_upload_time
        return 0.0


class WorkerPool:
    """
    Manages a pool of Telegram bot sessions for parallel uploads.
    
    Features:
    - Dynamic worker initialization
    - Multiple scheduling strategies
    - Automatic rate-limit recovery
    - Failed worker auto-restart
    - Health monitoring
    """
    
    def __init__(self, config: "Config"):
        self._workers: Dict[str, WorkerSession] = {}
        self._config = config
        self._lock = Lock()
        self._shutdown_event = Event()
        self._worker_available = Event()  # Event for worker availability
        self._round_robin_index = 0
        self._initialized = False
        
    async def initialize(self, tokens: List[str]) -> int:
        """
        Initialize all worker sessions in parallel.
        
        Args:
            tokens: List of bot tokens to initialize
            
        Returns:
            Number of successfully initialized workers
        """
        if not tokens:
            LOGGER.info("No worker tokens provided - worker pool disabled")
            return 0
        
        # Ensure sessions directory exists
        if not ospath.exists(SESSION_DIR):
            makedirs(SESSION_DIR, exist_ok=True)
            LOGGER.info(f"Created sessions directory: {SESSION_DIR}")
        
        async def init_worker(index: int, token: str) -> Optional[WorkerSession]:
            session_id = f"worker_{index}"
            try:
                # Validate token format
                if ":" not in token or len(token) < 40:
                    LOGGER.error(f"Invalid token format for {session_id}")
                    return None
                
                bot_id = token.split(":", 1)[0]
                
                client = Client(
                    name=session_id,
                    api_id=self._config.TELEGRAM_API,
                    api_hash=self._config.TELEGRAM_HASH,
                    bot_token=token,
                    proxy=getattr(self._config, 'TG_PROXY', None),
                    workdir=SESSION_DIR,
                    parse_mode=enums.ParseMode.HTML,
                    max_concurrent_transmissions=10,
                )
                
                await client.start()
                
                worker = WorkerSession(
                    session_id=session_id,
                    client=client,
                    bot_username=client.me.username or bot_id,
                    state=WorkerState.READY,
                )
                
                LOGGER.info(
                    f"Worker {session_id} initialized: @{worker.bot_username}"
                )
                return worker
                
            except Exception as e:
                LOGGER.error(f"Failed to initialize worker {session_id}: {e}")
                return None
        
        # Initialize all workers in parallel
        results = await gather(
            *[init_worker(i, token.strip()) for i, token in enumerate(tokens)],
            return_exceptions=True
        )
        
        # Collect successful initializations
        for result in results:
            if isinstance(result, WorkerSession):
                self._workers[result.session_id] = result
        
        self._initialized = len(self._workers) > 0
        
        if self._initialized:
            self._worker_available.set()
        
        LOGGER.info(
            f"Worker pool initialized: {len(self._workers)}/{len(tokens)} workers ready"
        )
        
        return len(self._workers)
    
    async def warm_connections(self) -> None:
        """
        Pre-warm connections to Telegram servers.
        
        Reduces first-transfer latency by establishing connections
        before they're needed.
        """
        if not self._workers:
            return
            
        LOGGER.info("Warming worker connections...")
        
        async def warm_worker(worker: WorkerSession):
            try:
                await worker.client.get_me()
                LOGGER.debug(f"Warmed connection for {worker.session_id}")
            except Exception as e:
                LOGGER.warning(f"Failed to warm {worker.session_id}: {e}")
        
        await gather(*[warm_worker(w) for w in self._workers.values()])
        LOGGER.info(f"Warmed {len(self._workers)} worker connections")
    
    async def get_worker(
        self, 
        strategy: str = "least_loaded"
    ) -> Optional[WorkerSession]:
        """
        Acquire an available worker using specified scheduling strategy.
        
        Args:
            strategy: One of 'least_loaded', 'round_robin', 'bandwidth_aware'
            
        Returns:
            Available WorkerSession or None if none available
        """
        # Build candidate list without holding global lock
        # Proactive rate limit avoidance: skip workers with high ops/minute
        candidates = [
            w for w in self._workers.values() 
            if w.is_available and not w.is_rate_limited
            and w.metrics.ops_per_minute() < 20  # Skip overloaded workers
        ]
        
        if not candidates:
            # Fallback: include high-ops workers if nothing else available
            candidates = [
                w for w in self._workers.values() 
                if w.is_available and not w.is_rate_limited
            ]
        
        if not candidates:
            self._worker_available.clear()
            return None
        
        # Sort candidates by strategy
        if strategy == "round_robin":
            async with self._lock:
                idx = self._round_robin_index % len(candidates)
                self._round_robin_index += 1
            candidates = [candidates[idx]] + candidates[:idx] + candidates[idx+1:]
            
        elif strategy == "bandwidth_aware":
            candidates.sort(key=lambda w: w.avg_upload_speed(), reverse=True)
        
        elif strategy == "adaptive":
            # Use real-time speed data, fall back to historical
            candidates.sort(
                key=lambda w: w.metrics.effective_speed() or w.avg_upload_speed(),
                reverse=True
            )
            
        else:  # least_loaded (default)
            candidates.sort(
                key=lambda w: w.metrics.uploads_completed + w.metrics.downloads_completed
            )
        
        # Try to acquire worker with per-worker lock (no global lock held)
        for worker in candidates:
            async with worker.lock:
                if worker.is_available and not worker.is_rate_limited:
                    worker.state = WorkerState.BUSY
                    worker.metrics.last_activity = time()
                    return worker
        
        # No worker available after checking all
        self._worker_available.clear()
        return None
    
    async def release_worker(
        self, 
        session_id: str, 
        success: bool = True,
    ) -> None:
        """
        Release worker back to pool after task completion.
        
        Handles state transitions and availability signaling.
        Metrics are recorded by the dispatchers directly.
        
        Args:
            session_id: ID of worker to release
            success: Whether the task completed successfully
        """
        if session_id not in self._workers:
            return
            
        worker = self._workers[session_id]
        
        async with worker.lock:
            worker.metrics.current_task_id = None
            worker.metrics.last_activity = time()
            
            if success:
                worker.metrics.consecutive_failures = 0
                worker.state = WorkerState.READY
                self._worker_available.set()  # Signal availability
            else:
                worker.metrics.consecutive_failures += 1
                
                max_retries = getattr(
                    self._config, 'WORKER_MAX_RETRIES', 3
                )
                
                if worker.metrics.consecutive_failures >= max_retries:
                    worker.state = WorkerState.FAILED
                    create_task(self._auto_restart_worker(session_id))
                else:
                    worker.state = WorkerState.READY
                    self._worker_available.set()
    
    async def mark_rate_limited(
        self, 
        session_id: str, 
        wait_seconds: float
    ) -> None:
        """
        Mark worker as rate-limited with cooldown period.
        
        Args:
            session_id: ID of rate-limited worker
            wait_seconds: Cooldown duration from Telegram
        """
        if session_id not in self._workers:
            return
            
        worker = self._workers[session_id]
        
        async with worker.lock:
            worker.state = WorkerState.RATE_LIMITED
            # Apply 1.3x buffer for safety
            actual_wait = wait_seconds * 1.3
            worker.metrics.rate_limit_until = time() + actual_wait
            
        LOGGER.warning(
            f"Worker {session_id} rate-limited for {actual_wait:.1f}s"
        )
        
        # Schedule automatic recovery
        create_task(self._rate_limit_recovery(session_id, actual_wait))
    
    async def _rate_limit_recovery(
        self, 
        session_id: str, 
        wait_seconds: float
    ) -> None:
        """Automatically recover worker after rate limit expires."""
        await sleep(wait_seconds + 1)  # Extra 1s buffer
        
        if session_id in self._workers:
            worker = self._workers[session_id]
            async with worker.lock:
                if worker.state == WorkerState.RATE_LIMITED:
                    worker.state = WorkerState.READY
                    self._worker_available.set()
                    LOGGER.info(f"Worker {session_id} recovered from rate limit")
    
    async def _auto_restart_worker(self, session_id: str) -> None:
        """Attempt to restart a failed worker."""
        if session_id not in self._workers:
            return
            
        worker = self._workers[session_id]
        LOGGER.warning(f"Attempting to restart failed worker: {session_id}")
        
        # Stop existing client
        try:
            await worker.client.stop()
        except Exception:
            pass
        
        # Wait before restart
        await sleep(5)
        
        # Attempt restart
        try:
            await worker.client.start()
            async with worker.lock:
                worker.state = WorkerState.READY
                worker.metrics.consecutive_failures = 0
                self._worker_available.set()
            LOGGER.info(f"Worker {session_id} restarted successfully")
        except Exception as e:
            LOGGER.error(f"Failed to restart worker {session_id}: {e}")
            # Leave in FAILED state - will be excluded from pool
    
    async def health_check(self) -> Dict[str, dict]:
        """
        Perform health check on all workers.
        
        Returns:
            Dict mapping session_id to health status
        """
        
        results = {}
        global_metrics = get_metrics()
        
        for session_id, worker in self._workers.items():
            # Get worker's internal metrics (updated by dispatchers)
            wm = worker.metrics
            
            # Get global metrics collector data (may have additional tracking)
            global_stats = global_metrics.get_worker_stats(session_id)
            
            # Combine metrics: prefer global collector if available (more accurate),
            # fall back to worker's local metrics
            uploads = global_stats.get("uploads") if global_stats else wm.uploads_completed
            downloads = global_stats.get("downloads") if global_stats else wm.downloads_completed
            
            bytes_up_mb = (
                global_stats.get("bytes_uploaded_mb") 
                if global_stats 
                else wm.bytes_uploaded / (1024 * 1024)
            )
            bytes_down_mb = (
                global_stats.get("bytes_downloaded_mb")
                if global_stats
                else wm.bytes_downloaded / (1024 * 1024)
            )
            
            uploads_failed = (
                global_stats.get("upload_errors") 
                if global_stats 
                else wm.uploads_failed
            )
            downloads_failed = (
                global_stats.get("download_errors")
                if global_stats
                else wm.downloads_failed
            )
            
            # Calculate average speed from recent recordings
            avg_speed = wm.effective_speed() / (1024 * 1024)  # Convert to MB/s
            if avg_speed == 0:
                # Fallback to calculated speed from totals
                avg_speed = worker.avg_upload_speed() / (1024 * 1024)
            
            results[session_id] = {
                "state": worker.state.name,
                "bot_username": worker.bot_username,
                "is_available": worker.is_available,
                "uploads_completed": uploads,
                "downloads_completed": downloads,
                "uploads_failed": uploads_failed,
                "downloads_failed": downloads_failed,
                "bytes_uploaded_mb": bytes_up_mb,
                "bytes_downloaded_mb": bytes_down_mb,
                "avg_speed_mbps": avg_speed,
                "last_activity": wm.last_activity,
                "current_task": wm.current_task_id,
            }
            
        return results
    
    async def shutdown(self) -> None:
        """Gracefully shutdown all workers."""
        LOGGER.info("Shutting down worker pool...")
        self._shutdown_event.set()
        
        for session_id, worker in self._workers.items():
            try:
                LOGGER.debug(f"Stopping worker {session_id}")
                await worker.client.stop()
            except Exception as e:
                LOGGER.warning(f"Error stopping worker {session_id}: {e}")
                
        self._workers.clear()
        self._initialized = False
        LOGGER.info("Worker pool shutdown complete")
    
    def get_worker_by_id(self, session_id: str) -> Optional[WorkerSession]:
        """Get worker by session ID."""
        return self._workers.get(session_id)
    
    @property
    def is_initialized(self) -> bool:
        """Check if pool is initialized with workers."""
        return self._initialized
    
    @property
    def active_count(self) -> int:
        """Number of workers currently processing tasks."""
        return sum(
            1 for w in self._workers.values() 
            if w.state == WorkerState.BUSY
        )
    
    @property
    def available_count(self) -> int:
        """Number of workers available for new tasks."""
        return sum(
            1 for w in self._workers.values() 
            if w.is_available and not w.is_rate_limited
        )
    
    @property
    def total_count(self) -> int:
        """Total number of workers in pool."""
        return len(self._workers)
    
    @property
    def rate_limited_count(self) -> int:
        """Number of workers currently rate-limited."""
        return sum(
            1 for w in self._workers.values() 
            if w.is_rate_limited
        )

    async def wait_for_available_worker(self) -> None:
        """Wait until a worker becomes available."""
        if not self._initialized:
            # If not initialized, wait a bit to avoid busy loop
            await sleep(1)
            return
            
        await self._worker_available.wait()
