#!/usr/bin/env python3
from bot.helper.ext_utils.bot_utils import get_readable_file_size, MirrorStatus, get_readable_time


class MegaDownloadStatus:

    def __init__(self, obj, message):
        self.__obj = obj
        self.message = message

    def name(self):
        return self.__obj.name

    def progress_raw(self):
        try:
            return round(self.__obj.downloaded_bytes / self.__obj.size * 100, 2)
        except:
            return 0.0

    def progress(self):
        return f"{self.progress_raw()}%"

    def status(self):
        return MirrorStatus.STATUS_DOWNLOADING

    def processed_bytes(self):
        return get_readable_file_size(self.__obj.downloaded_bytes)

    def eta(self):
        try:
            seconds = (self.__obj.size - self.__obj.downloaded_bytes) / self.__obj.speed
            return f'{get_readable_time(seconds)}'
        except ZeroDivisionError:
            return '-'

    def size(self):
        return get_readable_file_size(self.__obj.size)

    def speed(self):
        return f'{get_readable_file_size(self.__obj.speed)}/s'

    def gid(self):
        return self.__obj.gid

    def download(self):
        return self.__obj