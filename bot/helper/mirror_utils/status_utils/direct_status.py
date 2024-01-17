from bot.helper.ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
)


class DirectStatus:
    def __init__(self, listener, obj, gid):
        self._gid = gid
        self._obj = obj
        self.listener = listener

    def gid(self):
        return self._gid

    def progress_raw(self):
        try:
            return self._obj.processed_bytes / self._obj.total_size * 100
        except:
            return 0

    def progress(self):
        return f"{round(self.progress_raw(), 2)}%"

    def speed(self):
        return f"{get_readable_file_size(self._obj.speed)}/s"

    def name(self):
        return self.listener.name

    def size(self):
        return get_readable_file_size(self._obj.total_size)

    def eta(self):
        try:
            seconds = (
                self._obj.total_size - self._obj.processed_bytes
            ) / self._obj.speed
            return get_readable_time(seconds)
        except:
            return "-"

    def status(self):
        if self._obj.task and self._obj.task.is_waiting:
            return MirrorStatus.STATUS_QUEUEDL
        return MirrorStatus.STATUS_DOWNLOADING

    def processed_bytes(self):
        return get_readable_file_size(self._obj.processed_bytes)

    def task(self):
        return self._obj
