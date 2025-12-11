"""
Base Dispatcher Module

Abstract base class for upload/download dispatchers.
Provides common dispatch loop, worker acquisition, and retry logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, TYPE_CHECKING
from asyncio import (
    PriorityQueue, 
    Lock, 
    Event, 
    create_task, 
    wait_for, 
    TimeoutError as AsyncTimeoutError,
    sleep,
    wait,
    FIRST_COMPLETED,
)
from enum import IntEnum
from time import time
from logging import getLogger

from pyrogram.errors import FloodWait, FloodPremiumWait

if TYPE_CHECKING:
    from .worker_pool import WorkerPool, WorkerSession

LOGGER = getLogger(__name__)


class TaskPriority(IntEnum):
    """Task priority levels."""
    HIGH = 1      # User-initiated, small files
    NORMAL = 2    # Standard operations
    LOW = 3       # Batch/bulk operations
    RETRY = 4     # Failed task retries


def priority_from_size(file_size: int) -> TaskPriority:
    """
    Calculate priority based on file size.
    
    Small files get higher priority for better UX.
    
    Args:
        file_size: Size in bytes
        
    Returns:
        Appropriate TaskPriority
    """
    if file_size < 10 * 1024 * 1024:       # < 10MB
        return TaskPriority.HIGH
    elif file_size < 100 * 1024 * 1024:    # < 100MB
        return TaskPriority.NORMAL
    else:
        return TaskPriority.LOW


@dataclass(order=True)
class BaseTask:
    """Base task for dispatcher queue."""
    priority: TaskPriority
    created_at: float = field(compare=False, default_factory=time)
    task_id: str = field(compare=False, default="")
    listener: Any = field(compare=False, default=None)
    retry_count: int = field(compare=False, default=0)
    assigned_worker: Optional[str] = field(compare=False, default=None)
    cancelled: Event = field(compare=False, default_factory=Event)
    file_size: int = field(compare=False, default=0)


class BaseDispatcher(ABC):
    """
    Abstract base dispatcher for task distribution.
    
    Provides common functionality:
    - Priority queue management
    - Worker acquisition with backpressure
    - Retry logic with configurable limits
    - Task cancellation support
    - Graceful shutdown
    """
    
    def __init__(self, worker_pool: "WorkerPool", config):
        self._pool = worker_pool
        self._config = config
        self._queue: PriorityQueue = PriorityQueue()
        self._active_tasks: Dict[str, Any] = {}
        self._lock = Lock()
        self._running = False
        self._dispatch_task = None
        self._max_retries = getattr(config, 'WORKER_MAX_RETRIES', 3)
        self._scheduling = getattr(config, 'WORKER_SCHEDULING', 'least_loaded')
        self._prefetched_worker: Optional["WorkerSession"] = None
    
    async def _prefetch_next_worker(self) -> None:
        """Prefetch next worker if queue has pending tasks."""
        if self._queue.qsize() > 0 and self._prefetched_worker is None:
            self._prefetched_worker = await self._pool.get_worker(
                strategy=self._scheduling
            )
    
    @property
    @abstractmethod
    def _task_type(self) -> str:
        """Return task type name for logging."""
        pass
    
    @abstractmethod
    async def _execute_task(self, task: Any, worker: "WorkerSession") -> None:
        """Execute task on assigned worker. Must be implemented by subclass."""
        pass
    
    @abstractmethod
    async def _on_max_retries_exceeded(self, task: Any, error_msg: str) -> None:
        """Handle when task exceeds max retries. Must be implemented by subclass."""
        pass
        
    async def start(self) -> None:
        """Start the dispatcher loop."""
        if self._running:
            return
            
        self._running = True
        self._dispatch_task = create_task(self._dispatch_loop())
        LOGGER.info(f"{self._task_type} dispatcher started")
    
    async def stop(self) -> None:
        """Stop the dispatcher and wait for active tasks."""
        LOGGER.info(f"Stopping {self._task_type} dispatcher...")
        self._running = False
        
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except Exception:
                pass
                
        LOGGER.info(f"{self._task_type} dispatcher stopped")
    
    async def _submit_task(self, task: Any) -> Any:
        """Submit task to the queue."""
        await self._queue.put(task)
        
        async with self._lock:
            self._active_tasks[task.task_id] = task
        
        LOGGER.debug(
            f"{self._task_type} task {task.task_id} submitted with priority {task.priority.name}"
        )
        
        return task
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel a pending or active task."""
        async with self._lock:
            if task_id in self._active_tasks:
                self._active_tasks[task_id].cancelled.set()
                del self._active_tasks[task_id]
                LOGGER.info(f"{self._task_type} task {task_id} cancelled")
                return True
        return False
    
    async def _dispatch_loop(self) -> None:
        """Main dispatch loop - assigns tasks to available workers."""
        while self._running:
            try:
                # Wait for task with timeout
                try:
                    task = await wait_for(self._queue.get(), timeout=1.0)
                except AsyncTimeoutError:
                    continue
                
                # Skip cancelled tasks
                if task.cancelled.is_set():
                    async with self._lock:
                        if task.task_id in self._active_tasks:
                            del self._active_tasks[task.task_id]
                    continue
                
                # Wait for available worker
                worker = await self._acquire_worker(task)
                
                if worker is None:
                    continue
                
                # Assign and execute
                task.assigned_worker = worker.session_id
                worker.metrics.current_task_id = task.task_id
                
                create_task(self._execute_with_retry(task, worker))
                
            except Exception as e:
                LOGGER.error(f"{self._task_type} dispatcher error: {e}")
                await sleep(1)
    
    async def _acquire_worker(self, task: Any) -> Optional["WorkerSession"]:
        """Acquire worker with backpressure handling and prefetching."""
        # Use prefetched worker if available
        if self._prefetched_worker is not None:
            worker = self._prefetched_worker
            self._prefetched_worker = None
            
            # Verify still available (may have been taken by another dispatcher)
            if worker.is_available and not worker.is_rate_limited:
                # Trigger prefetch for next task in background
                create_task(self._prefetch_next_worker())
                return worker
            else:
                # Prefetched worker no longer valid, release it
                await self._pool.release_worker(worker.session_id)
        
        worker = None
        
        while worker is None and not task.cancelled.is_set():
            worker = await self._pool.get_worker(strategy=self._scheduling)
            
            if worker is None:
                wait_task = create_task(self._pool.wait_for_available_worker())
                cancel_task = create_task(task.cancelled.wait())
                
                done, pending = await wait(
                    [wait_task, cancel_task],
                    return_when=FIRST_COMPLETED
                )
                
                for t in pending:
                    t.cancel()
                    
                if cancel_task in done:
                    break
        
        # Handle cancellation
        if task.cancelled.is_set():
            if worker:
                await self._pool.release_worker(worker.session_id)
            return None
        
        # Trigger prefetch for next task
        create_task(self._prefetch_next_worker())
            
        return worker
    
    async def _execute_with_retry(self, task: Any, worker: "WorkerSession") -> None:
        """Execute task with FloodWait handling and retry logic."""
        try:
            await self._execute_task(task, worker)
            
        except (FloodWait, FloodPremiumWait) as e:
            wait_time = e.value if hasattr(e, 'value') else 60
            LOGGER.warning(
                f"Worker {worker.session_id} hit FloodWait: {wait_time}s"
            )
            
            await self._pool.mark_rate_limited(worker.session_id, wait_time)
            await self._requeue_or_fail(task, f"FloodWait: {wait_time}s")
            
        except Exception as e:
            error_msg = str(e)
            LOGGER.error(f"{self._task_type} failed on {worker.session_id}: {error_msg}")
            
            # Don't retry on access errors - they won't be fixed by retrying
            access_errors = ["cannot access message", "telegram restricts", "not found in chat"]
            if any(err in error_msg.lower() for err in access_errors):
                # Fail immediately to trigger fallback faster
                await self._on_max_retries_exceeded(task, error_msg)
            else:
                await self._requeue_or_fail(task, error_msg)
            
        finally:
            async with self._lock:
                if task.task_id in self._active_tasks:
                    del self._active_tasks[task.task_id]
    
    async def _requeue_or_fail(self, task: Any, error_msg: str) -> None:
        """Requeue task or report failure if max retries exceeded."""
        if task.retry_count < self._max_retries:
            task.retry_count += 1
            task.priority = TaskPriority.RETRY
            task.assigned_worker = None
            await self._queue.put(task)
            LOGGER.info(
                f"{self._task_type} task {task.task_id} re-queued (retry {task.retry_count})"
            )
        else:
            await self._on_max_retries_exceeded(task, error_msg)
    
    @property
    def pending_count(self) -> int:
        """Number of tasks waiting in queue."""
        return self._queue.qsize()
    
    @property
    def active_count(self) -> int:
        """Number of tasks currently being processed."""
        return len(self._active_tasks)
    
    @property
    def is_running(self) -> bool:
        """Check if dispatcher is running."""
        return self._running
    
    def get_stats(self) -> dict:
        """Get dispatcher statistics."""
        return {
            "type": self._task_type,
            "running": self._running,
            "pending_tasks": self.pending_count,
            "active_tasks": self.active_count,
            "scheduling_strategy": self._scheduling,
            "max_retries": self._max_retries,
        }
