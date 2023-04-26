#!/usr/bin/env python3
from time import time

from bot import LOGGER
from bot.helper.ext_utils.bot_utils import get_readable_file_size, MirrorStatus, get_readable_time, async_to_sync
from bot.helper.ext_utils.fs_utils import get_path_size


class ExtractStatus:
    def __init__(self, name, size, gid, listener):
        self.__name = name
        self.__size = size
        self.__gid = gid
        self.__listener = listener
        self.__uid = listener.uid
        self.__start_time = time()
        self.message = listener.message

    def gid(self):
        return self.__gid

    def speed_raw(self):
        return self.processed_raw() / (time() - self.__start_time)

    def progress_raw(self):
        try:
            return self.processed_raw() / self.__size * 100
        except:
            return 0

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed(self):
        return f'{get_readable_file_size(self.speed_raw())}/s'

    def name(self):
        return self.__name

    def size(self):
        return get_readable_file_size(self.__size)

    def eta(self):
        try:
            seconds = (self.__size - self.processed_raw()) / self.speed_raw()
            return get_readable_time(seconds)
        except:
            return '-'

    def status(self):
        return MirrorStatus.STATUS_EXTRACTING

    def processed_bytes(self):
        return get_readable_file_size(self.processed_raw())

    def processed_raw(self):
        if self.__listener.newDir:
            return async_to_sync(get_path_size, self.__listener.newDir)
        else:
            return async_to_sync(get_path_size, self.__listener.dir) - self.__size

    def download(self):
        return self

    async def cancel_download(self):
        LOGGER.info(f'Cancelling Extract: {self.__name}')
        if self.__listener.suproc is not None:
            self.__listener.suproc.kill()
        else:
            self.__listener.suproc = 'cancelled'
        await self.__listener.onUploadError('extracting stopped by user!')
