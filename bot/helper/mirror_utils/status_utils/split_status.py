from bot import LOGGER, subprocess_lock
from bot.helper.ext_utils.status_utils import get_readable_file_size, MirrorStatus


class SplitStatus:
    def __init__(self, listener, size, gid):
        self._gid = gid
        self._size = size
        self.listener = listener

    def gid(self):
        return self._gid

    def progress(self):
        return "0"

    def speed(self):
        return "0"

    def name(self):
        return self.listener.name

    def size(self):
        return get_readable_file_size(self._size)

    def eta(self):
        return "0s"

    def status(self):
        return MirrorStatus.STATUS_SPLITTING

    def processed_bytes(self):
        return 0

    def task(self):
        return self

    async def cancel_task(self):
        LOGGER.info(f"Cancelling Split: {self.listener.name}")
        async with subprocess_lock:
            if (
                self.listener.suproc is not None
                and self.listener.suproc.returncode is None
            ):
                self.listener.suproc.kill()
            else:
                self.listener.suproc = "cancelled"
        await self.listener.onUploadError("splitting stopped by user!")
