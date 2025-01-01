from .... import LOGGER
from ...ext_utils.bot_utils import new_task
from ...ext_utils.status_utils import (
    get_readable_file_size,
    MirrorStatus,
    get_readable_time,
)


class FFmpegStatus:
    def __init__(self, listener, gid, status=""):
        self.listener = listener
        self._gid = gid
        self._processed_bytes = 0
        self._speed_raw = 0
        self._progress_raw = 0
        self._active = False
        self.cstatus = status

    @new_task
    async def _ffmpeg_progress(self):
        while True:
            async with self.listener.subprocess_lock:
                if self.listener.subproc is None or self.listener.is_cancelled:
                    break
                line = await self.listener.subproc.stdout.readline()
                if not line:
                    break
                line = line.decode().strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    if value != "N/A":
                        if key == "total_size":
                            self._processed_bytes = int(value)
                            self._progress_raw = (
                                self._processed_bytes / self.listener.subsize * 100
                            )
                        elif key == "bitrate":
                            self._speed_raw = (float(value.strip("kbits/s")) / 8) * 1000
        self._active = False

    def speed(self):
        return f"{get_readable_file_size(self._speed_raw)}/s"

    def processed_bytes(self):
        return get_readable_file_size(self._processed_bytes)

    async def progress(self):
        if not self._active and self.listener.subsize and self.listener.subproc is not None:
            await self._ffmpeg_progress()
            self._active = True
        return f"{round(self._progress_raw, 2)}%"

    def gid(self):
        return self._gid

    def name(self):
        return self.listener.name

    def size(self):
        return get_readable_file_size(self.listener.size)

    def eta(self):
        try:
            seconds = (self.listener.subsize - self._processed_bytes) / self._speed_raw
            return get_readable_time(seconds)
        except:
            return "-"

    def status(self):
        if self.cstatus == "Convert":
            return MirrorStatus.STATUS_CONVERT
        elif self.cstatus == "Split":
            return MirrorStatus.STATUS_SPLIT
        elif self.cstatus == "Sample Video":
            return MirrorStatus.STATUS_SAMVID
        else:
            return MirrorStatus.STATUS_FFMPEG

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
