from .status import Status
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time
from bot import DOWNLOAD_DIR


class UploadStatus(Status):
    def __init__(self, obj, size, listener):
        self.obj = obj
        self.__size = size
        self.uid = listener.uid
        self.message = listener.message

    def path(self):
        return f"{DOWNLOAD_DIR}{self.uid}"

    def processed_bytes(self):
        return self.obj.uploaded_bytes

    def size_raw(self):
        return self.__size

    def size(self):
        return get_readable_file_size(self.__size)

    def status(self):
        return MirrorStatus.STATUS_UPLOADING

    def name(self):
        return self.obj.name

    def progress_raw(self):
        try:
            return self.obj.uploaded_bytes / self.__size * 100
        except ZeroDivisionError:
            return 0

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed_raw(self):
        """
        :return: Upload speed in Bytes/Seconds
        """
        return self.obj.speed()

    def speed(self):
        return f'{get_readable_file_size(self.speed_raw())}/s'

    def eta(self):
        try:
            seconds = (self.__size - self.obj.uploaded_bytes) / self.speed_raw()
            return f'{get_readable_time(seconds)}'
        except ZeroDivisionError:
            return '-'
