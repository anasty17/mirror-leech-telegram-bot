from .status import Status
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time
from bot import DOWNLOAD_DIR


class GdDownloadStatus(Status):
    def __init__(self, obj, size, listener, gid):
        self.dobj = obj
        self.__dsize = size
        self.uid = listener.uid
        self.message = listener.message
        self.__dgid = gid

    def path(self):
        return f"{DOWNLOAD_DIR}{self.uid}"

    def processed_bytes(self):
        return self.dobj.downloaded_bytes

    def size_raw(self):
        return self.__dsize

    def size(self):
        return get_readable_file_size(self.__dsize)

    def status(self):
        return MirrorStatus.STATUS_DOWNLOADING

    def name(self):
        return self.dobj.name

    def gid(self) -> str:
        return self.__dgid

    def progress_raw(self):
        try:
            return self.dobj.downloaded_bytes / self.__dsize * 100
        except ZeroDivisionError:
            return 0

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed_raw(self):
        """
        :return: Download speed in Bytes/Seconds
        """
        return self.dobj.dspeed()

    def speed(self):
        return f'{get_readable_file_size(self.speed_raw())}/s'

    def eta(self):
        try:
            seconds = (self.__dsize - self.dobj.downloaded_bytes) / self.speed_raw()
            return f'{get_readable_time(seconds)}'
        except ZeroDivisionError:
            return '-'

    def download(self):
        return self.dobj
