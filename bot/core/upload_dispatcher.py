"""
Upload Task Dispatcher Module

Dispatcher for distributing upload tasks across worker sessions.
Extends BaseDispatcher with upload-specific logic.
"""

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from asyncio import Event
from time import time
from logging import getLogger

from .base_dispatcher import BaseDispatcher, TaskPriority

if TYPE_CHECKING:
    from .worker_pool import WorkerSession

LOGGER = getLogger(__name__)


@dataclass(order=True)
class UploadTask:
    """Represents a single upload task in the queue."""
    priority: TaskPriority
    created_at: float = field(compare=False, default_factory=time)
    task_id: str = field(compare=False, default="")
    listener: Any = field(compare=False, default=None)
    file_path: str = field(compare=False, default="")
    chat_id: int = field(compare=False, default=0)
    retry_count: int = field(compare=False, default=0)
    assigned_worker: str = field(compare=False, default=None)
    cancelled: Event = field(compare=False, default_factory=Event)
    file_size: int = field(compare=False, default=0)


class UploadDispatcher(BaseDispatcher):
    """
    Dispatcher for upload tasks.
    
    Extends BaseDispatcher with upload-specific execution logic.
    """
    
    @property
    def _task_type(self) -> str:
        return "Upload"
    
    async def submit(
        self,
        task_id: str,
        listener: Any,
        file_path: str,
        chat_id: int,
        priority: TaskPriority = TaskPriority.NORMAL,
        file_size: int = 0,
    ) -> UploadTask:
        """Submit a new upload task to the queue."""
        task = UploadTask(
            priority=priority,
            task_id=task_id,
            listener=listener,
            file_path=file_path,
            chat_id=chat_id,
            file_size=file_size,
        )
        return await self._submit_task(task)
    
    async def _execute_task(self, task: UploadTask, worker: "WorkerSession") -> None:
        """Execute upload task on assigned worker."""
        from ..helper.mirror_leech_utils.worker_uploader import WorkerUploader
        from ..helper.ext_utils.metrics import get_metrics
        
        start_time = time()
        success = False
        bytes_uploaded = 0
        
        try:
            LOGGER.info(
                f"Starting upload task {task.task_id} on worker {worker.session_id}"
            )
            
            # Record operation for rate limit prediction
            worker.metrics.record_operation()
            
            uploader = WorkerUploader(
                worker=worker,
                listener=task.listener,
                file_path=task.file_path,
            )
            
            result = await uploader.upload()
            success = True
            bytes_uploaded = result.get('bytes', 0) if isinstance(result, dict) else 0
            
            LOGGER.info(
                f"Upload task {task.task_id} completed on {worker.session_id}"
            )
            
            # Mark task as completed to prevent re-processing
            task.cancelled.set()
            
        finally:
            elapsed = time() - start_time
            
            # Record speed for adaptive scheduling
            if elapsed > 0 and bytes_uploaded > 0:
                speed = bytes_uploaded / elapsed
                worker.metrics.record_speed(speed)
            
            # Record metrics to global collector
            metrics = get_metrics()
            metrics.record_upload(
                session_id=worker.session_id,
                bytes_count=bytes_uploaded,
                duration=elapsed,
                success=success,
            )
            
            # Update worker's internal metrics
            worker.metrics.total_upload_time += elapsed
            if success:
                worker.metrics.uploads_completed += 1
                worker.metrics.bytes_uploaded += bytes_uploaded
            else:
                worker.metrics.uploads_failed += 1
            
            await self._pool.release_worker(
                worker.session_id, 
                success=success,
            )
    
    async def _on_max_retries_exceeded(self, task: UploadTask, error_msg: str) -> None:
        """Handle upload failure after max retries."""
        await task.listener.on_upload_error(
            f"Max retries exceeded: {error_msg}"
        )
