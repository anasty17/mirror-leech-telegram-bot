"""
Metrics Collection Module

Collects and exposes metrics for monitoring upload performance
and worker pool health.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Deque
from time import time
from collections import deque


@dataclass
class MetricsCollector:
    """
    Collect and expose metrics for monitoring.
    
    Tracks upload performance, worker health, and error rates
    for observability and debugging.
    """
    
    # Upload metrics
    uploads_total: int = 0
    uploads_success: int = 0
    uploads_failed: int = 0
    bytes_uploaded: int = 0
    
    # Download metrics
    downloads_total: int = 0
    downloads_success: int = 0
    downloads_failed: int = 0
    bytes_downloaded: int = 0
    
    # Timing metrics (rolling window)
    upload_times: Deque[float] = field(
        default_factory=lambda: deque(maxlen=100)
    )
    download_times: Deque[float] = field(
        default_factory=lambda: deque(maxlen=100)
    )
    
    # Per-worker metrics
    worker_metrics: Dict[str, dict] = field(default_factory=dict)
    
    # Error tracking
    recent_errors: Deque[dict] = field(
        default_factory=lambda: deque(maxlen=50)
    )
    
    # Session start time
    start_time: float = field(default_factory=time)
    
    def _ensure_worker_metrics(self, session_id: str) -> dict:
        """Get or create worker metrics entry."""
        if session_id not in self.worker_metrics:
            self.worker_metrics[session_id] = {
                "uploads": 0,
                "downloads": 0,
                "bytes_uploaded": 0,
                "bytes_downloaded": 0,
                "upload_errors": 0,
                "download_errors": 0,
                "total_upload_time": 0.0,
                "total_download_time": 0.0,
            }
        return self.worker_metrics[session_id]
    
    def record_upload(
        self,
        session_id: str,
        bytes_count: int,
        duration: float,
        success: bool,
        error: str = None,
    ) -> None:
        """
        Record an upload attempt.
        
        Args:
            session_id: Worker session identifier
            bytes_count: Bytes transferred
            duration: Upload duration in seconds
            success: Whether upload succeeded
            error: Error message if failed
        """
        self.uploads_total += 1
        
        if success:
            self.uploads_success += 1
            self.bytes_uploaded += bytes_count
        else:
            self.uploads_failed += 1
            
            if error:
                self.recent_errors.append({
                    "timestamp": time(),
                    "session_id": session_id,
                    "error": error,
                })
        
        self.upload_times.append(duration)
        
        # Update per-worker metrics
        wm = self._ensure_worker_metrics(session_id)
        wm["uploads"] += 1
        wm["total_upload_time"] += duration
        
        if success:
            wm["bytes_uploaded"] += bytes_count
        else:
            wm["upload_errors"] += 1
    
    def record_download(
        self,
        session_id: str,
        bytes_count: int,
        duration: float,
        success: bool,
        error: str = None,
    ) -> None:
        """
        Record a download attempt.
        
        Args:
            session_id: Worker session identifier
            bytes_count: Bytes transferred
            duration: Download duration in seconds
            success: Whether download succeeded
            error: Error message if failed
        """
        self.downloads_total += 1
        
        if success:
            self.downloads_success += 1
            self.bytes_downloaded += bytes_count
        else:
            self.downloads_failed += 1
            
            if error:
                self.recent_errors.append({
                    "timestamp": time(),
                    "session_id": session_id,
                    "error": error,
                    "type": "download",
                })
        
        self.download_times.append(duration)
        
        # Update per-worker metrics
        wm = self._ensure_worker_metrics(session_id)
        wm["downloads"] += 1
        wm["total_download_time"] += duration
        
        if success:
            wm["bytes_downloaded"] += bytes_count
        else:
            wm["download_errors"] += 1
    
    def record_rate_limit(
        self,
        session_id: str,
        wait_time: float,
    ) -> None:
        """Record a rate limit event."""
        self.recent_errors.append({
            "timestamp": time(),
            "session_id": session_id,
            "error": f"FloodWait: {wait_time}s",
            "type": "rate_limit",
        })
    
    def get_stats(self) -> dict:
        """
        Get comprehensive statistics.
        
        Returns:
            Dict with all tracked metrics
        """
        uptime = time() - self.start_time
        avg_upload_time = (
            sum(self.upload_times) / len(self.upload_times)
            if self.upload_times else 0
        )
        avg_download_time = (
            sum(self.download_times) / len(self.download_times)
            if self.download_times else 0
        )
        
        return {
            "uptime_seconds": uptime,
            "uploads": {
                "total": self.uploads_total,
                "success": self.uploads_success,
                "failed": self.uploads_failed,
                "success_rate": (
                    self.uploads_success / max(1, self.uploads_total)
                ),
            },
            "downloads": {
                "total": self.downloads_total,
                "success": self.downloads_success,
                "failed": self.downloads_failed,
                "success_rate": (
                    self.downloads_success / max(1, self.downloads_total)
                ),
            },
            "throughput": {
                "bytes_uploaded": self.bytes_uploaded,
                "bytes_downloaded": self.bytes_downloaded,
                "mb_uploaded": self.bytes_uploaded / (1024 * 1024),
                "mb_downloaded": self.bytes_downloaded / (1024 * 1024),
                "avg_upload_time_sec": avg_upload_time,
                "avg_download_time_sec": avg_download_time,
            },
            "workers": {
                session_id: {
                    "uploads": wm["uploads"],
                    "downloads": wm["downloads"],
                    "bytes_uploaded_mb": wm["bytes_uploaded"] / (1024 * 1024),
                    "bytes_downloaded_mb": wm["bytes_downloaded"] / (1024 * 1024),
                    "upload_errors": wm["upload_errors"],
                    "download_errors": wm["download_errors"],
                    "avg_upload_time": (
                        wm["total_upload_time"] / max(1, wm["uploads"])
                    ),
                    "avg_download_time": (
                        wm["total_download_time"] / max(1, wm["downloads"])
                    ),
                }
                for session_id, wm in self.worker_metrics.items()
            },
            "recent_errors": list(self.recent_errors)[-10:],
        }
    
    def get_worker_stats(self, session_id: str) -> dict:
        """Get stats for a specific worker."""
        if session_id not in self.worker_metrics:
            return {}
            
        wm = self.worker_metrics[session_id]
        total_ops = wm["uploads"] + wm["downloads"]
        total_errors = wm["upload_errors"] + wm["download_errors"]
        
        return {
            "uploads": wm["uploads"],
            "downloads": wm["downloads"],
            "bytes_uploaded_mb": wm["bytes_uploaded"] / (1024 * 1024),
            "bytes_downloaded_mb": wm["bytes_downloaded"] / (1024 * 1024),
            "upload_errors": wm["upload_errors"],
            "download_errors": wm["download_errors"],
            "avg_upload_time_sec": wm["total_upload_time"] / max(1, wm["uploads"]),
            "avg_download_time_sec": wm["total_download_time"] / max(1, wm["downloads"]),
            "success_rate": 1 - (total_errors / max(1, total_ops)),
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.uploads_total = 0
        self.uploads_success = 0
        self.uploads_failed = 0
        self.bytes_uploaded = 0
        self.downloads_total = 0
        self.downloads_success = 0
        self.downloads_failed = 0
        self.bytes_downloaded = 0
        self.upload_times.clear()
        self.download_times.clear()
        self.worker_metrics.clear()
        self.recent_errors.clear()
        self.start_time = time()


# Global metrics instance
_metrics: MetricsCollector = None


def get_metrics() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def reset_metrics() -> None:
    """Reset global metrics."""
    global _metrics
    if _metrics:
        _metrics.reset()
