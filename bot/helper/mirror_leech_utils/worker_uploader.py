"""
Worker-specific uploader that delegates to assigned worker session.

Adapts the existing TelegramUploader to work with worker pool sessions.
"""

from typing import TYPE_CHECKING, Dict, Any
from time import time
from logging import getLogger

from .telegram_uploader import TelegramUploader

if TYPE_CHECKING:
    from ...core.worker_pool import WorkerSession

LOGGER = getLogger(__name__)


class WorkerUploader:
    """
    Upload handler for individual worker sessions.
    
    Wraps the existing TelegramUploader logic to use a specific
    worker's Pyrogram client instead of the primary bot client.
    """
    
    def __init__(
        self,
        worker: "WorkerSession",
        listener,
        file_path: str,
    ):
        """
        Initialize worker uploader.
        
        Args:
            worker: WorkerSession to use for uploads
            listener: TaskListener instance managing this upload
            file_path: Path to file/directory to upload
        """
        self._worker = worker
        self._listener = listener
        self._file_path = file_path
        self._client = worker.client
        self._processed_bytes = 0
        self._start_time = time()
        
    async def upload(self) -> Dict[str, Any]:
        """
        Execute upload using worker's client.
        
        Returns:
            Dict with upload result including bytes transferred
        """
        
        # Create uploader instance
        uploader = TelegramUploader(self._listener, self._file_path)
        
        # Override the client to use worker's client
        # We need to inject the worker client into the upload flow
        original_client = self._listener.client
        
        # Store reference for progress tracking
        original_progress = uploader._upload_progress
        
        async def progress_with_activity(current, total):
            """Wrapper that updates worker activity during upload."""
            # Update worker's last_activity to prevent false stuck detection
            self._worker.metrics.last_activity = time()
            # Call original progress handler
            await original_progress(current, total)
        
        try:
            # Temporarily replace client with worker client
            self._listener.client = self._client
            
            # Force bot session mode (not user session)
            # Temporarily disable user transmission for this upload
            original_user_transmission = self._listener.user_transmission
            self._listener.user_transmission = False
            
            # Inject our progress wrapper
            uploader._upload_progress = progress_with_activity
            
            # Execute upload
            await uploader.upload()
            
            # Collect bytes processed
            self._processed_bytes = uploader.processed_bytes
            
            return {
                "success": True,
                "bytes": self._processed_bytes,
                "duration": time() - self._start_time,
                "worker": self._worker.session_id,
            }
            
        finally:
            # Restore original client and settings
            self._listener.client = original_client
            self._listener.user_transmission = original_user_transmission
    
    @property
    def speed(self) -> float:
        """Current upload speed in bytes/second."""
        elapsed = time() - self._start_time
        if elapsed > 0:
            return self._processed_bytes / elapsed
        return 0.0
    
    @property
    def processed_bytes(self) -> int:
        """Total bytes processed so far."""
        return self._processed_bytes

