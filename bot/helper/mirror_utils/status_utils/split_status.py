#!/usr/bin/env python3
from bot import LOGGER
from bot.helper.ext_utils.bot_utils import get_readable_file_size, MirrorStatus


class SplitStatus:
    def __init__(self, name, size, gid, listener):
        self.__name = name
        self.__gid = gid
        self.__size = size
        self.__listener = listener
        self.message = listener.message

    def gid(self):
        return self.__gid

    def progress(self):
        return '0'

    def speed(self):
        return '0'

    def name(self):
        return self.__name

    def size(self):
        return get_readable_file_size(self.__size)

    def eta(self):
        return '0s'

    def status(self):
        return MirrorStatus.STATUS_SPLITTING

    def processed_bytes(self):
        return 0

    def download(self):
        return self

    async def cancel_download(self):
        LOGGER.info(f'Cancelling Split: {self.__name}')
        if self.__listener.suproc is not None:
            self.__listener.suproc.kill()
        else:
            self.__listener.suproc = 'cancelled'
        await self.__listener.onUploadError('splitting stopped by user!')
