# Implement By - @anasty17 (https://github.com/SlamDevs/slam-mirrorbot/commit/80d33430715b4296cd253f62cefc089a81937ebf)
# (c) https://github.com/SlamDevs/slam-mirrorbot
# All rights reserved

from .status import Status
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time


class CloneStatus(Status):
    def __init__(self, obj, size, update, gid):
        self.cobj = obj
        self.__csize = size
        self.message = update.message
        self.__cgid = gid

    def processed_bytes(self):
        return self.cobj.transferred_size

    def size_raw(self):
        return self.__csize

    def size(self):
        return get_readable_file_size(self.__csize)

    def status(self):
        return MirrorStatus.STATUS_CLONING

    def name(self):
        return self.cobj.name

    def gid(self) -> str:
        return self.__cgid

    def progress_raw(self):
        try:
            return self.cobj.transferred_size / self.__csize * 100
        except ZeroDivisionError:
            return 0

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed_raw(self):
        """
        :return: Download speed in Bytes/Seconds
        """
        return self.cobj.cspeed()

    def speed(self):
        return f'{get_readable_file_size(self.speed_raw())}/s'

    def eta(self):
        try:
            seconds = (self.__csize - self.cobj.transferred_size) / self.speed_raw()
            return f'{get_readable_time(seconds)}'
        except ZeroDivisionError:
            return '-'

    def download(self):
        return self.cobj
