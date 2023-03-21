#!/usr/bin/env python3
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time, async_to_sync
from bot.helper.ext_utils.fs_utils import get_path_size

class YtDlpDownloadStatus:
    def __init__(self, obj, listener, gid):
        self.__obj = obj
        self.__listener = listener
        self.__gid = gid
        self.message = listener.message

    def gid(self):
        return self.__gid

    def processed_bytes(self):
        return get_readable_file_size(self.processed_raw())

    def processed_raw(self):
        if self.__obj.downloaded_bytes != 0:
            return self.__obj.downloaded_bytes
        else:
            return async_to_sync(get_path_size, self.__listener.dir)
        
    def size(self):
        return get_readable_file_size(self.__obj.size)

    def status(self):
        return MirrorStatus.STATUS_DOWNLOADING

    def name(self):
        return self.__obj.name

    def progress(self):
        return f'{round(self.__obj.progress, 2)}%'

    def speed(self):
        return f'{get_readable_file_size(self.__obj.download_speed)}/s'

    def eta(self):
        if self.__obj.eta != '-':
            return f'{get_readable_time(self.__obj.eta)}'
        try:
            seconds = (self.__obj.size - self.processed_raw()) / self.__obj.download_speed
            return f'{get_readable_time(seconds)}'
        except:
            return '-'

    def download(self):
        return self.__obj