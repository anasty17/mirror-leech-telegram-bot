from bot.helper.ext_utils.bot_utils import MirrorStatus


class RcloneStatus:
    def __init__(self, obj, message, gid, status):
        self.__obj = obj
        self.__gid = gid
        self.__status = status
        self.message = message

    def gid(self):
        return self.__gid

    def progress(self):
        return self.__obj.percentage

    def speed(self):
        return self.__obj.speed

    def name(self):
        return self.__obj.name

    def size(self):
        return self.__obj.size

    def eta(self):
        return self.__obj.eta

    def status(self):
        if self.__status == 'dl':
            return MirrorStatus.STATUS_DOWNLOADING
        elif self.__status == 'up':
            return MirrorStatus.STATUS_UPLOADING
        else:
            return MirrorStatus.STATUS_CLONING

    def processed_bytes(self):
        return self.__obj.transferred_size

    def download(self):
        return self.__obj
