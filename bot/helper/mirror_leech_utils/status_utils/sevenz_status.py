from time import time
from re import search

from .... import LOGGER
from ...ext_utils.bot_utils import new_task
from ...ext_utils.status_utils import (
    get_readable_file_size,
    MirrorStatus,
    get_readable_time,
)


class SevenZStatus:
    def __init__(self, listener, gid, status=""):
        self.listener = listener
        self._gid = gid
        self._start_time = time()
        self._processed_bytes = 0
        self._progress_str = "0%"
        self._active = False
        self.cstatus = status

    @new_task
    async def _sevenz_progress(self):
        pattern = r"\b(?:Add\s+new\s+data\s+to\s+archive:.*?,\s+(\d+)\s+bytes|Physical\s+Size\s*=\s*(\d+))"
        while True:
            async with self.listener.subprocess_lock:
                if self.listener.subproc is None or self.listener.is_cancelled:
                    break
                line = await self.listener.subproc.stdout.readline()
                line = line.decode().strip()
                if line.startswith("Add new data to archive:") or line.startswith(
                    "Physical Size ="
                ):
                    if match := search(pattern, line):
                        size = match[1] or match[2]
                        self.listener.subsize = int(size)
                    break
        s = b""
        while True:
            async with self.listener.subprocess_lock:
                if self.listener.is_cancelled or self.listener.subproc is None:
                    break
                char = await self.listener.subproc.stdout.read(1)
                if not char:
                    break
                s += char
                if char == b"%":
                    try:
                        self._progress_str = s.decode().rsplit(" ", 1)[-1].strip()
                        self._processed_bytes = (
                            int(self._progress_str.strip("%")) / 100
                        ) * self.listener.subsize
                    except:
                        self._processed_bytes = 0
                        self._progress_str = "0%"
                    s = b""

        self._active = False

    def gid(self):
        return self._gid

    def _speed_raw(self):
        return self._processed_bytes / (time() - self._start_time)

    async def progress(self):
        if not self._active and self.listener.subproc is not None:
            await self._sevenz_progress()
            self._active = True
        return self._progress_str

    def speed(self):
        return f"{get_readable_file_size(self._speed_raw())}/s"

    def processed_bytes(self):
        return get_readable_file_size(self._processed_bytes)

    def name(self):
        return self.listener.name

    def size(self):
        return get_readable_file_size(self.listener.size)

    def eta(self):
        try:
            seconds = (
                self.listener.subsize - self._processed_bytes
            ) / self._speed_raw()
            return get_readable_time(seconds)
        except:
            return "-"

    def status(self):
        if self.cstatus == "Extract":
            return MirrorStatus.STATUS_EXTRACT
        else:
            return MirrorStatus.STATUS_ARCHIVE

    def processed_bytes(self):
        return get_readable_file_size(self._processed_bytes)

    def task(self):
        return self

    async def cancel_task(self):
        LOGGER.info(f"Cancelling {self.cstatus}: {self.listener.name}")
        async with self.listener.subprocess_lock:
            self.listener.is_cancelled = True
            if (
                self.listener.subproc is not None
                and self.listener.subproc.returncode is None
            ):
                self.listener.subproc.kill()
        await self.listener.on_upload_error(f"{self.cstatus} stopped by user!")
