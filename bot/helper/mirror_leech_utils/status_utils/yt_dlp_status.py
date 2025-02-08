from ...ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
)


class YtDlpStatus:
    def __init__(self, listener, obj, gid):
        self._obj = obj
        self._gid = gid
        self.listener = listener
        self.tool = "yt-dlp"

    def gid(self):
        return self._gid

    def processed_bytes(self):
        return get_readable_file_size(self._obj.downloaded_bytes)

    def size(self):
        return get_readable_file_size(self._obj.size)

    def status(self):
        return MirrorStatus.STATUS_DOWNLOAD

    def name(self):
        return self.listener.name

    def progress(self):
        return f"{round(self._obj.progress, 2)}%"

    def speed(self):
        return f"{get_readable_file_size(self._obj.download_speed)}/s"

    def eta(self):
        if self._obj.eta != "-":
            return get_readable_time(self._obj.eta)
        try:
            seconds = (
                self._obj.size - self._obj.downloaded_bytes
            ) / self._obj.download_speed
            return get_readable_time(seconds)
        except:
            return "-"

    def task(self):
        return self._obj
