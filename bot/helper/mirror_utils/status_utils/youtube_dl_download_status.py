from bot import DOWNLOAD_DIR
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time
from .status import Status


class YoutubeDLDownloadStatus(Status):
    def __init__(self, obj, listener):
        self.obj = obj
        self.uid = listener.uid
        self.message = listener.message

    def gid(self):
        return self.obj.gid

    def path(self):
        return f"{DOWNLOAD_DIR}{self.uid}"

    def processed_bytes(self):
        return self.obj.downloaded_bytes

    def size_raw(self):
        return self.obj.size

    def size(self):
        return get_readable_file_size(self.size_raw())

    def status(self):
        return MirrorStatus.STATUS_DOWNLOADING

    def name(self):
        return self.obj.name

    def progress_raw(self):
        return self.obj.progress

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed_raw(self):
        """
        :return: Download speed in Bytes/Seconds
        """
        return self.obj.download_speed

    def speed(self):
        return f'{get_readable_file_size(self.speed_raw())}/s'

    def eta(self):
        try:
            seconds = (self.size_raw() - self.processed_bytes()) / self.speed_raw()
            return f'{get_readable_time(seconds)}'
        except ZeroDivisionError:
            return '-'

    def download(self):
        return self.obj
