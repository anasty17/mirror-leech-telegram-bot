from bot.helper.ext_utils.bot_utils import get_readable_file_size, MirrorStatus, get_readable_time


class MegaDownloadStatus:

    def __init__(self, obj, listener):
        self.__listener = listener
        self.__obj = obj
        self.message = listener.message

    def name(self) -> str:
        return self.__obj.name

    def progress_raw(self):
        try:
            return round(self.processed_bytes() / self.__obj.size * 100,2)
        except:
            return 0.0

    def progress(self):
        """Progress of download in percentage"""
        return f"{self.progress_raw()}%"

    def status(self) -> str:
        return MirrorStatus.STATUS_DOWNLOADING

    def processed_bytes(self):
        return self.__obj.downloaded_bytes

    def eta(self):
        try:
            seconds = (self.size_raw() - self.processed_bytes()) / self.speed_raw()
            return f'{get_readable_time(seconds)}'
        except ZeroDivisionError:
            return '-'

    def size_raw(self):
        return self.__obj.size

    def size(self) -> str:
        return get_readable_file_size(self.size_raw())

    def downloaded(self) -> str:
        return get_readable_file_size(self.__obj.downloadedBytes)

    def speed_raw(self):
        return self.__obj.speed

    def speed(self) -> str:
        return f'{get_readable_file_size(self.speed_raw())}/s'

    def gid(self) -> str:
        return self.__obj.gid

    def download(self):
        return self.__obj
