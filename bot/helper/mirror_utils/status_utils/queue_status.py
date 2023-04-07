#!/usr/bin/env python3
from bot import LOGGER
from bot.helper.ext_utils.bot_utils import get_readable_file_size, MirrorStatus


class QueueStatus:
    def __init__(self, name, size, gid, listener, status):
        self.__name = name
        self.__size = size
        self.__gid = gid
        self.__listener = listener
        self.__status = status
        self.message = listener.message

    def gid(self):
        return self.__gid

    def name(self):
        return self.__name

    def size(self):
        return get_readable_file_size(self.__size)

    def status(self):
        if self.__status == 'dl':
            return MirrorStatus.STATUS_QUEUEDL
        return MirrorStatus.STATUS_QUEUEUP

    def processed_bytes(self):
        return 0

    def progress(self):
        return '0%'

    def speed(self):
        return '0B/s'

    def eta(self):
        return '-'

    def download(self):
        return self

    async def cancel_download(self):
        LOGGER.info(f'Cancelling Queue{self.__status}: {self.__name}')
        if self.__status == 'dl':
            await self.__listener.onDownloadError('task have been removed from queue/download')
        else:
            await self.__listener.onUploadError('task have been removed from queue/upload')
