#!/usr/bin/env python3

from bot.helper.ext_utils.bot_utils import (MirrorStatus,
                                            get_readable_file_size,
                                            get_readable_time)


class DirectStatus:
    def __init__(self, obj, gid, listener):
        self.__gid = gid
        self.__listener = listener
        self.__obj = obj
        self.message = self.__listener.message

    def gid(self):
        return self.__gid

    def progress_raw(self):
        try:
            return self.__obj.processed_bytes / self.__obj.total_size * 100
        except:
            return 0

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed(self):
        return f'{get_readable_file_size(self.__obj.speed)}/s'

    def name(self):
        return self.__obj.name

    def size(self):
        return get_readable_file_size(self.__obj.total_size)

    def eta(self):
        try:
            seconds = (self.__obj.total_size - self.__obj.processed_bytes) / self.__obj.speed
            return get_readable_time(seconds)
        except:
            return '-'

    def status(self):
        if self.__obj.task and self.__obj.task.is_waiting:
            return MirrorStatus.STATUS_QUEUEDL
        return MirrorStatus.STATUS_DOWNLOADING

    def processed_bytes(self):
        return get_readable_file_size(self.__obj.processed_bytes)

    def download(self):
        return self.__obj
