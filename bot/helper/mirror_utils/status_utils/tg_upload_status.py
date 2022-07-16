from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time


class TgUploadStatus:
    def __init__(self, obj, size, gid, listener):
        self.__obj = obj
        self.__size = size
        self.__gid = gid
        self.message = listener.message

    def processed_bytes(self):
        return self.__obj.uploaded_bytes

    def size_raw(self):
        return self.__size

    def size(self):
        return get_readable_file_size(self.__size)

    def status(self):
        return MirrorStatus.STATUS_UPLOADING

    def name(self):
        return self.__obj.name

    def progress_raw(self):
        try:
            return self.__obj.uploaded_bytes / self.__size * 100
        except ZeroDivisionError:
            return 0

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed_raw(self):
        """
        :return: Upload speed in Bytes/Seconds
        """
        return self.__obj.speed

    def speed(self):
        return f'{get_readable_file_size(self.speed_raw())}/s'

    def eta(self):
        try:
            seconds = (self.__size - self.__obj.uploaded_bytes) / self.speed_raw()
            return f'{get_readable_time(seconds)}'
        except ZeroDivisionError:
            return '-'

    def gid(self) -> str:
        return self.__gid

    def download(self):
        return self.__obj
