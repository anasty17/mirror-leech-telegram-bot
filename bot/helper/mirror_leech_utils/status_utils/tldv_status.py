from ...ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
)


class TldvStatus:
    def __init__(self, listener, obj, gid):
        self._obj = obj
        self._gid = gid
        self.listener = listener
        self.tool = "tldv"

    def gid(self):
        return self._gid

    def processed_bytes(self):
        return get_readable_file_size(self._obj.processed_bytes)

    def size(self):
        return get_readable_file_size(self._obj.estimated_total_size)

    def status(self):
        return MirrorStatus.STATUS_DOWNLOAD

    def name(self):
        return self.listener.name

    def progress(self):
        try:
            pct = (self._obj.completed_segments / self._obj.total_segments) * 100
            return f"{round(pct, 2)}%"
        except:
            return "0%"

    def speed(self):
        return f"{get_readable_file_size(self._obj.speed)}/s"

    def eta(self):
        try:
            seconds = (
                self._obj.estimated_total_size - self._obj.processed_bytes
            ) / self._obj.speed
            return get_readable_time(seconds)
        except:
            return "-"

    def task(self):
        return self._obj
