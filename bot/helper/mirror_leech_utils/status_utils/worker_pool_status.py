"""
Status tracker for Worker Pool uploads.

Provides status display integration for uploads processed by the worker pool.
"""

from time import time
from typing import Optional
from ...ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
)


class WorkerPoolStatus:
    """
    Status tracker for worker pool uploads.
    
    Tracks progress of uploads assigned to worker pool dispatcher,
    updating status based on the assigned worker's progress.
    """
    
    def __init__(self, listener, gid: str, task_id: str):
        self.listener = listener
        self._gid = gid
        self._task_id = task_id
        self._size = listener.size
        self._processed_bytes = 0
        self._speed = 0.0
        self._start_time = time()
        self._worker_id: Optional[str] = None
        self.tool = "telegram"
    
    def update_progress(
        self, 
        processed_bytes: int, 
        speed: float = 0.0,
        worker_id: str = None
    ):
        """Update progress from worker."""
        self._processed_bytes = processed_bytes
        self._speed = speed
        if worker_id:
            self._worker_id = worker_id
    
    def processed_bytes(self) -> int:
        """Raw processed bytes for calculations."""
        return self._processed_bytes
    
    def speed(self) -> float:
        """Raw speed for calculations."""
        if self._speed > 0:
            return self._speed
        # Calculate from elapsed time
        elapsed = time() - self._start_time
        if elapsed > 0 and self._processed_bytes > 0:
            return self._processed_bytes / elapsed
        return 0.0
    
    def processed_bytes_str(self):
        """Formatted processed bytes."""
        return get_readable_file_size(self._processed_bytes)
    
    def size(self):
        """Formatted total size."""
        return get_readable_file_size(self._size)
    
    def status(self):
        """Current status."""
        return MirrorStatus.STATUS_UPLOAD
    
    def name(self):
        """Task name."""
        return self.listener.name
    
    def progress(self):
        """Progress percentage."""
        try:
            progress_raw = self._processed_bytes / self._size * 100
        except:
            progress_raw = 0
        return f"{round(progress_raw, 2)}%"
    
    def speed_str(self):
        """Formatted speed."""
        return f"{get_readable_file_size(self.speed())}/s"
    
    def eta(self):
        """Estimated time remaining."""
        try:
            remaining = self._size - self._processed_bytes
            current_speed = self.speed()
            if current_speed > 0:
                seconds = remaining / current_speed
                return get_readable_time(seconds)
        except:
            pass
        return "-"
    
    def gid(self):
        """Task group ID."""
        return self._gid
    
    def worker_info(self) -> str:
        """Worker assignment info."""
        if self._worker_id:
            return f"Worker: {self._worker_id}"
        return "Queued"
    
    def task(self):
        """Return self for compatibility."""
        return self
    
    async def cancel_task(self):
        """Cancel the upload task."""
        from ...core.telegram_manager import TgClient
        
        self.listener.is_cancelled = True
        
        if TgClient.dispatcher:
            await TgClient.dispatcher.cancel(self._task_id)
        
        await self.listener.on_upload_error("your upload has been stopped!")
