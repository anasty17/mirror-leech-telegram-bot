"""
Worker-specific downloader that delegates to assigned worker session.

Adapts Pyrogram's download_media to work with worker pool sessions for
parallel Telegram file downloads.
"""

from typing import TYPE_CHECKING, Dict, Any
from time import time
from logging import getLogger
from os import path as ospath

if TYPE_CHECKING:
    from ...core.worker_pool import WorkerSession

LOGGER = getLogger(__name__)


class WorkerDownloader:
    """
    Download handler for individual worker sessions.
    
    Uses a specific worker's Pyrogram client to download Telegram media,
    enabling parallel downloads and rate limit distribution.
    """
    
    def __init__(
        self,
        worker: "WorkerSession",
        listener,
        message,
        file_path: str,
    ):
        """
        Initialize worker downloader.
        
        Args:
            worker: WorkerSession to use for downloads
            listener: TaskListener instance managing this download
            message: Telegram message containing the media
            file_path: Destination path for downloaded file
        """
        self._worker = worker
        self._listener = listener
        self._message = message
        self._file_path = file_path
        self._client = worker.client
        self._processed_bytes = 0
        self._start_time = time()
        
    async def download(self) -> Dict[str, Any]:
        """
        Execute download using worker's client.
        
        Returns:
            Dict with download result including bytes transferred
            
        Raises:
            Exception: If download fails, allowing fallback to main bot
        """
        LOGGER.info(
            f"Worker {self._worker.session_id} downloading: {self._file_path}"
        )
        
        # Step 1: Probe message access - FAIL FAST if worker can't access
        chat_id = self._message.chat.id
        message_id = self._message.id
        
        try:
            refreshed_message = await self._client.get_messages(chat_id, message_id)
            
            # Definitive access check
            if not refreshed_message:
                raise Exception(f"Message {message_id} not found in chat {chat_id}")
            
            if refreshed_message.empty:
                raise Exception(
                    f"Worker cannot access message content - "
                    f"Telegram restricts this message from worker bot access"
                )
            
            if not refreshed_message.media:
                raise Exception(
                    f"Message has no media - possibly deleted or restricted"
                )
            
            self._message = refreshed_message
            LOGGER.info(f"Worker {self._worker.session_id} verified message access")
        except Exception as e:
            LOGGER.warning(f"File reference refresh failed for {self._worker.session_id}: {e}")
            raise Exception(f"Cannot access message: {e}")
        
        # Step 2: Download media using worker client with refreshed message
        try:
            file_name = await self._client.download_media(
                message=self._message,
                file_name=self._file_path,
                progress=self._download_progress,
            )
        except TimeoutError as e:
            LOGGER.error(f"Worker {self._worker.session_id} download timed out: {e}")
            raise Exception(f"Download timeout: {e}")
        except Exception as e:
            LOGGER.error(f"Worker {self._worker.session_id} download error: {e}")
            raise
        
        # Step 3: Verify download success
        if file_name and ospath.exists(file_name):
            self._processed_bytes = ospath.getsize(file_name)
            
            LOGGER.info(
                f"Worker {self._worker.session_id} completed download: "
                f"{self._processed_bytes / (1024**2):.2f} MB"
            )
            
            return {
                "success": True,
                "bytes": self._processed_bytes,
                "duration": time() - self._start_time,
                "worker": self._worker.session_id,
                "file_name": file_name,
            }
        else:
            raise Exception("Download failed - file not found or empty")
    
    async def _download_progress(self, current: int, total: int):
        """
        Progress callback for download.
        
        Args:
            current: Current bytes downloaded
            total: Total bytes to download
        """
        if self._listener.is_cancelled:
            self._client.stop_transmission()
            return
        
        # Update worker's last_activity to prevent false stuck detection
        self._worker.metrics.last_activity = time()
            
        # Update processed bytes
        chunk_size = current - self._processed_bytes
        self._processed_bytes = current
        
        # Update download helper's processed bytes for status display
        if hasattr(self._listener, '_download_helper'):
            self._listener._download_helper._processed_bytes = current
    
    @property
    def speed(self) -> float:
        """Current download speed in bytes/second."""
        elapsed = time() - self._start_time
        if elapsed > 0:
            return self._processed_bytes / elapsed
        return 0.0
    
    @property
    def processed_bytes(self) -> int:
        """Total bytes processed so far."""
        return self._processed_bytes
