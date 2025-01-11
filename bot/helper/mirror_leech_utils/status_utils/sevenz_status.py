from time import time

from .... import LOGGER
from ...ext_utils.status_utils import (
    get_readable_file_size,
    MirrorStatus,
    get_readable_time,
)


class SevenZStatus:
    def __init__(self, listener, obj, gid, status=""):
        self.listener = listener
        self._obj = obj
        self._gid = gid
        self._start_time = time()
        self._cstatus = status

    def gid(self):
        return self._gid

    def _speed_raw(self):
        return self._obj.processed_bytes / (time() - self._start_time)

    async def progress(self):
        return self._obj.progress

    def speed(self):
        return f"{get_readable_file_size(self._speed_raw())}/s"

    def processed_bytes(self):
        return get_readable_file_size(self._obj.processed_bytes)

    def name(self):
        return self.listener.name

    def size(self):
        return get_readable_file_size(self.listener.size)

    def eta(self):
        try:
            seconds = (
                self.listener.subsize - self._obj.processed_bytes
            ) / self._speed_raw()
            return get_readable_time(seconds)
        except:
            return "-"

    def status(self):
        if self._cstatus == "Extract":
            return MirrorStatus.STATUS_EXTRACT
        else:
            return MirrorStatus.STATUS_ARCHIVE

    def task(self):
        return self

    async def cancel_task(self):
        LOGGER.info(f"Cancelling {self._cstatus}: {self.listener.name}")
        self.listener.is_cancelled = True
        if (
            self.listener.subproc is not None
            and self.listener.subproc.returncode is None
        ):
            try:
                self.listener.subproc.kill()
            except:
                pass
        await self.listener.on_upload_error(f"{self._cstatus} stopped by user!")
