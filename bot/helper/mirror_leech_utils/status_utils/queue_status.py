from bot import LOGGER
from bot.helper.ext_utils.status_utils import get_readable_file_size, MirrorStatus


class QueueStatus:
    def __init__(self, listener, gid, status):
        self.listener = listener
        self._size = self.listener.size
        self._gid = gid
        self._status = status

    def gid(self):
        return self._gid

    def name(self):
        return self.listener.name

    def size(self):
        return get_readable_file_size(self._size)

    def status(self):
        if self._status == "dl":
            return MirrorStatus.STATUS_QUEUEDL
        return MirrorStatus.STATUS_QUEUEUP

    def processed_bytes(self):
        return 0

    def progress(self):
        return "0%"

    def speed(self):
        return "0B/s"

    def eta(self):
        return "-"

    def task(self):
        return self

    async def cancel_task(self):
        self.listener.isCancelled = True
        LOGGER.info(f"Cancelling Queue{self._status}: {self.listener.name}")
        if self._status == "dl":
            await self.listener.onDownloadError(
                "task have been removed from queue/download"
            )
        else:
            await self.listener.onUploadError(
                "task have been removed from queue/upload"
            )
