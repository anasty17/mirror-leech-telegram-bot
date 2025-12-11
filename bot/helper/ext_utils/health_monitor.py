"""
Health Monitoring Module

Provides periodic health checks, stuck worker detection,
and auto-recovery for the worker pool.
"""

from typing import TYPE_CHECKING, Callable, List, Dict, Any, Optional
from asyncio import create_task, sleep, Task
from time import time
from logging import getLogger

if TYPE_CHECKING:
    from ...core.worker_pool import WorkerPool
    from ...core.upload_dispatcher import UploadDispatcher

LOGGER = getLogger(__name__)


class HealthMonitor:
    """
    Periodic health checks and auto-recovery for worker pool.
    
    Features:
    - Periodic health status collection
    - Stuck worker detection
    - Status change callbacks
    - Degradation assessment
    """
    
    # Health states
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    
    def __init__(
        self,
        pool: "WorkerPool",
        dispatcher: "UploadDispatcher",
        interval: int = 30,
        stuck_threshold: int = 300,
    ):
        """
        Initialize health monitor.
        
        Args:
            pool: WorkerPool to monitor
            dispatcher: UploadDispatcher to monitor
            interval: Health check interval in seconds
            stuck_threshold: Seconds of inactivity before worker is stuck
        """
        self._pool = pool
        self._dispatcher = dispatcher
        self._interval = interval
        self._stuck_threshold = stuck_threshold
        self._running = False
        self._monitor_task: Task = None
        self._callbacks: List[Callable] = []
        self._last_status: Dict[str, Any] = {}
    
    async def start(self) -> None:
        """Start the health monitoring loop."""
        if self._running:
            return
            
        self._running = True
        self._monitor_task = create_task(self._monitor_loop())
        LOGGER.info("Health monitor started")
    
    async def stop(self) -> None:
        """Stop the health monitoring loop."""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except Exception:
                pass
                
        LOGGER.info("Health monitor stopped")
    
    def on_health_change(self, callback: Callable) -> None:
        """
        Register callback for health status changes.
        
        Args:
            callback: Async function to call with status dict
        """
        self._callbacks.append(callback)
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                status = await self.check_health()
                
                # Detect stuck workers
                await self._detect_stuck_workers(status)
                
                # Notify callbacks on status change
                if self._has_significant_change(status):
                    for callback in self._callbacks:
                        try:
                            await callback(status)
                        except Exception as e:
                            LOGGER.error(f"Health callback error: {e}")
                
                self._last_status = status
                
            except Exception as e:
                LOGGER.error(f"Health monitor error: {e}")
            
            await sleep(self._interval)
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Health status dictionary
        """
        pool_health = await self._pool.health_check()
        
        healthy_count = sum(
            1 for w in pool_health.values()
            if w['state'] == 'READY'
        )
        
        return {
            "timestamp": time(),
            "overall_health": self._assess_health(healthy_count),
            "healthy_workers": healthy_count,
            "total_workers": len(pool_health),
            "active_workers": self._pool.active_count,
            "rate_limited_workers": self._pool.rate_limited_count,
            "pending_tasks": self._dispatcher.pending_count,
            "active_tasks": self._dispatcher.active_count,
            "workers": pool_health,
        }
    
    def _assess_health(self, healthy_count: int) -> str:
        """Assess overall health status."""
        total = self._pool.total_count
        
        if total == 0:
            return self.CRITICAL
        
        ratio = healthy_count / total
        
        if ratio >= 0.5:
            return self.HEALTHY
        elif ratio > 0:
            return self.DEGRADED
        else:
            return self.CRITICAL
    
    async def _detect_stuck_workers(self, status: Dict[str, Any]) -> None:
        """Detect and attempt to recover stuck workers."""
        now = time()
        
        for session_id, metrics in status.get('workers', {}).items():
            if metrics['state'] == 'BUSY':
                last_activity = metrics.get('last_activity', now)
                idle_time = now - last_activity
                
                # Worker is stuck if no progress activity for threshold seconds
                if idle_time > self._stuck_threshold:
                    LOGGER.warning(
                        f"Worker {session_id} appears stuck "
                        f"(no progress for {idle_time:.0f}s)"
                    )
                    
                    # Trigger recovery
                    await self._pool._auto_restart_worker(session_id)
    
    def _has_significant_change(self, new_status: Dict[str, Any]) -> bool:
        """Check if health status changed significantly."""
        if not self._last_status:
            return True
            
        # Check for health state change
        if new_status.get('overall_health') != self._last_status.get('overall_health'):
            return True
            
        # Check for worker count change
        if new_status.get('healthy_workers') != self._last_status.get('healthy_workers'):
            return True
            
        return False
    
    def get_concurrency_recommendation(self) -> int:
        """
        Get recommended concurrency limit based on health.
        
        Returns:
            Recommended number of concurrent uploads
        """
        health = self._assess_health(self._pool.available_count)
        
        if health == self.HEALTHY:
            return 10  # Full concurrency
        elif health == self.DEGRADED:
            return 3   # Reduced concurrency
        else:
            return 1   # Minimal operation
    
    @property
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running
    
    @property
    def last_status(self) -> Dict[str, Any]:
        """Get last health status."""
        return self._last_status
