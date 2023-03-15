#!/usr/bin/env python3
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time


class CloneStatus:
    def __init__(self, obj, size, message, gid):
        self.__obj = obj
        self.__size = size
        self.__gid = gid
        self.message = message

    def processed_bytes(self):
        return get_readable_file_size(self.__obj.transferred_size)

    def size(self):
        return get_readable_file_size(self.__size)

    def status(self):
        return MirrorStatus.STATUS_CLONING

    def name(self):
        return self.__obj.name

    def gid(self) -> str:
        return self.__gid

    def progress_raw(self):
        try:
            return self.__obj.transferred_size / self.__size * 100
        except:
            return 0

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed(self):
        return f'{get_readable_file_size(self.__obj.cspeed())}/s'

    def eta(self):
        try:
            seconds = (self.__size - self.__obj.transferred_size) / self.__obj.cspeed()
            return f'{get_readable_time(seconds)}'
        except:
            return '-'

    def download(self):
        return self.__obj