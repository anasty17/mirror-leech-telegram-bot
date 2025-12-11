"""
Download Task Dispatcher Module

Dispatcher for distributing Telegram file downloads across worker sessions.
Extends BaseDispatcher with download-specific logic.
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


# Alias for backwards compatibility
DownloadPriority = TaskPriority


@dataclass(order=True)
class DownloadTask:
    """Represents a single download task in the queue."""
    priority: TaskPriority
    created_at: float = field(compare=False, default_factory=time)
    task_id: str = field(compare=False, default="")
    listener: Any = field(compare=False, default=None)
    message: Any = field(compare=False, default=None)
    file_path: str = field(compare=False, default="")
    retry_count: int = field(compare=False, default=0)
    assigned_worker: str = field(compare=False, default=None)
    cancelled: Event = field(compare=False, default_factory=Event)
    file_size: int = field(compare=False, default=0)


class DownloadDispatcher(BaseDispatcher):
    """
    Dispatcher for download tasks.
    
    Extends BaseDispatcher with download-specific execution logic.
    """
    
    @property
    def _task_type(self) -> str:
        return "Download"
    
    async def submit(
        self,
        task_id: str,
        listener: Any,
        message: Any,
        file_path: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        file_size: int = 0,
    ) -> DownloadTask:
        """Submit a new download task to the queue."""
        task = DownloadTask(
            priority=priority,
            task_id=task_id,
            listener=listener,
            message=message,
            file_path=file_path,
            file_size=file_size,
        )
        return await self._submit_task(task)
    
    async def _execute_task(self, task: DownloadTask, worker: "WorkerSession") -> None:
        """Execute download task on assigned worker."""
        from ..helper.mirror_leech_utils.worker_downloader import WorkerDownloader
        from ..helper.ext_utils.metrics import get_metrics
        
        start_time = time()
        success = False
        bytes_downloaded = 0
        
        try:
            LOGGER.info(
                f"Starting download task {task.task_id} on worker {worker.session_id}"
            )
            
            # Record operation for rate limit prediction
            worker.metrics.record_operation()
            
            downloader = WorkerDownloader(
                worker=worker,
                listener=task.listener,
                message=task.message,
                file_path=task.file_path,
            )
            
            result = await downloader.download()
            success = True
            bytes_downloaded = result.get('bytes', 0) if isinstance(result, dict) else 0
            
            LOGGER.info(
                f"Download task {task.task_id} completed on {worker.session_id}"
            )
            
            # Mark task as completed to prevent re-processing
            task.cancelled.set()
            
            # Trigger download completion callback to start upload process
            await task.listener.on_download_complete()
            
        finally:
            elapsed = time() - start_time
            
            # Record speed for adaptive scheduling
            if elapsed > 0 and bytes_downloaded > 0:
                speed = bytes_downloaded / elapsed
                worker.metrics.record_speed(speed)
            
            # Record metrics
            metrics = get_metrics()
            metrics.record_download(
                session_id=worker.session_id,
                bytes_count=bytes_downloaded,
                duration=elapsed,
                success=success,
            )
            
            # Update worker metrics
            worker.metrics.total_download_time += elapsed
            if success:
                worker.metrics.downloads_completed += 1
                worker.metrics.bytes_downloaded += bytes_downloaded
            else:
                worker.metrics.downloads_failed += 1
            
            await self._pool.release_worker(
                worker.session_id, 
                success=success,
            )
    
    async def _on_max_retries_exceeded(self, task: DownloadTask, error_msg: str) -> None:
        """Handle download failure after max retries."""
        await task.listener.on_download_error(
            f"Max retries exceeded: {error_msg}"
        )
