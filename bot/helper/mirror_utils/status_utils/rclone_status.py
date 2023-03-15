from bot.helper.ext_utils.bot_utils import get_readable_file_size, MirrorStatus


class RcloneStatus:
    def __init__(self, obj, message, status):
        self.__obj = obj
        self.__status = status
        self.message = message

    def gid(self):
        return self.__obj.gid

    def progress(self):
        return self.__obj.percentage

    def speed(self):
        return self.__obj.speed

    def name(self):
        return self.__obj.name

    def size(self):
        return get_readable_file_size(self.__obj.size)

    def eta(self):
        return self.__obj.eta

    def status(self):
        if self.__status == 'dl':
            return MirrorStatus.STATUS_DOWNLOADING
        else:
            return MirrorStatus.STATUS_UPLOADING

    def processed_bytes(self):
        return self.__obj.transferred_size

    def download(self):
        return self.__obj