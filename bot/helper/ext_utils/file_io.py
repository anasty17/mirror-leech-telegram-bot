"""
Optimized File I/O Utilities

Provides memory-mapped file handling for large files to reduce memory usage
and improve read performance through OS-level caching.
"""

import mmap
import os
from typing import Union, BinaryIO, Optional
from contextlib import contextmanager
from logging import getLogger

LOGGER = getLogger(__name__)

# Threshold for using memory-mapped I/O (100MB)
MMAP_THRESHOLD = 100 * 1024 * 1024


class MappedFile:
    """
    Memory-mapped file wrapper for efficient large file handling.
    
    Benefits:
    - Reduced memory usage (file not loaded into Python heap)
    - OS-level page caching for faster repeated reads
    - Lazy loading - only accessed pages are loaded
    """
    
    def __init__(self, path: str):
        self.path = path
        self.size = os.path.getsize(path)
        self._file: Optional[BinaryIO] = None
        self._mmap: Optional[mmap.mmap] = None
        self._use_mmap = self.size >= MMAP_THRESHOLD
        
    def __enter__(self) -> Union[mmap.mmap, BinaryIO]:
        if self._use_mmap:
            self._file = open(self.path, 'rb')
            try:
                self._mmap = mmap.mmap(
                    self._file.fileno(), 
                    0, 
                    access=mmap.ACCESS_READ
                )
                LOGGER.debug(f"Using mmap for {self.path} ({self.size / (1024**2):.1f} MB)")
                return self._mmap
            except Exception as e:
                LOGGER.warning(f"mmap failed, falling back to regular I/O: {e}")
                self._file.close()
                self._file = open(self.path, 'rb')
                return self._file
        else:
            self._file = open(self.path, 'rb')
            return self._file
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._mmap:
            try:
                self._mmap.close()
            except Exception:
                pass
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
        return False


@contextmanager
def open_optimized(path: str):
    """
    Context manager for optimized file reading.
    
    Uses memory-mapped I/O for files >= 100MB,
    regular file I/O for smaller files.
    
    Usage:
        with open_optimized('/path/to/large_file.zip') as f:
            data = f.read(chunk_size)
    """
    mapped = MappedFile(path)
    try:
        yield mapped.__enter__()
    finally:
        mapped.__exit__(None, None, None)


def should_use_mmap(file_size: int) -> bool:
    """Check if file size warrants memory-mapped I/O."""
    return file_size >= MMAP_THRESHOLD


def get_optimal_chunk_size(file_size: int) -> int:
    """
    Calculate optimal chunk size for file transfers.
    
    Larger chunks = fewer syscalls but more memory.
    Smaller chunks = more syscalls but lower memory.
    """
    if file_size < 10 * 1024 * 1024:       # < 10MB
        return 512 * 1024                   # 512KB chunks
    elif file_size < 100 * 1024 * 1024:    # < 100MB
        return 1024 * 1024                  # 1MB chunks
    elif file_size < 1024 * 1024 * 1024:   # < 1GB
        return 2 * 1024 * 1024              # 2MB chunks
    else:
        return 4 * 1024 * 1024              # 4MB chunks for huge files
