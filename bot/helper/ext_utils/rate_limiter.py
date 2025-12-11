"""
Per-Worker Bandwidth Limiting Module

Provides token bucket rate limiting for fair bandwidth allocation
across multiple worker sessions.
"""

from time import time
from typing import Dict
from dataclasses import dataclass
from asyncio import sleep


@dataclass
class BandwidthBucket:
    """Token bucket for bandwidth rate limiting."""
    bytes_per_second: int
    tokens: float
    last_update: float
    
    def consume(self, bytes_count: int) -> float:
        """
        Consume tokens and return wait time if insufficient.
        
        Args:
            bytes_count: Number of bytes to consume
            
        Returns:
            Wait time in seconds (0 if tokens available)
        """
        now = time()
        elapsed = now - self.last_update
        self.last_update = now
        
        # Refill tokens based on elapsed time
        self.tokens = min(
            float(self.bytes_per_second),  # Max bucket size
            self.tokens + (elapsed * self.bytes_per_second)
        )
        
        if self.tokens >= bytes_count:
            self.tokens -= bytes_count
            return 0.0
        else:
            deficit = bytes_count - self.tokens
            wait_time = deficit / self.bytes_per_second
            self.tokens = 0
            return wait_time


class BandwidthLimiter:
    """
    Per-worker bandwidth limiting for fair resource allocation.
    
    Uses token bucket algorithm to enforce bandwidth limits
    on individual worker sessions.
    """
    
    def __init__(self, bytes_per_second: int = 0):
        """
        Initialize bandwidth limiter.
        
        Args:
            bytes_per_second: Default limit per worker (0 = unlimited)
        """
        self._buckets: Dict[str, BandwidthBucket] = {}
        self._default_limit = bytes_per_second
    
    def register_worker(
        self, 
        session_id: str, 
        limit: int = None
    ) -> None:
        """
        Register a worker with bandwidth limit.
        
        Args:
            session_id: Worker session identifier
            limit: Bandwidth limit in bytes/sec (None = use default)
        """
        limit = limit or self._default_limit
        
        if limit > 0:
            self._buckets[session_id] = BandwidthBucket(
                bytes_per_second=limit,
                tokens=float(limit),
                last_update=time()
            )
    
    def unregister_worker(self, session_id: str) -> None:
        """Remove worker from bandwidth tracking."""
        self._buckets.pop(session_id, None)
    
    async def throttle(
        self, 
        session_id: str, 
        bytes_count: int
    ) -> float:
        """
        Apply bandwidth throttling for a worker's upload chunk.
        
        Args:
            session_id: Worker session identifier
            bytes_count: Number of bytes being transferred
            
        Returns:
            Time waited (in seconds)
        """
        if session_id not in self._buckets:
            return 0.0
            
        wait_time = self._buckets[session_id].consume(bytes_count)
        
        if wait_time > 0:
            await sleep(wait_time)
            
        return wait_time
    
    def get_remaining_tokens(self, session_id: str) -> float:
        """Get remaining bandwidth tokens for a worker."""
        if session_id in self._buckets:
            return self._buckets[session_id].tokens
        return float('inf')
    
    def update_limit(
        self, 
        session_id: str, 
        bytes_per_second: int
    ) -> None:
        """Update bandwidth limit for a worker."""
        if session_id in self._buckets:
            self._buckets[session_id].bytes_per_second = bytes_per_second
        elif bytes_per_second > 0:
            self.register_worker(session_id, bytes_per_second)
    
    @property
    def is_enabled(self) -> bool:
        """Check if bandwidth limiting is enabled."""
        return self._default_limit > 0 or len(self._buckets) > 0
