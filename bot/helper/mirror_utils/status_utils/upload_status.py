#!/usr/bin/env python3
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time


class UploadStatus:
    def __init__(self, obj, size, gid, listener):
        self.__obj = obj
        self.__size = size
        self.__gid = gid
        self.message = listener.message
        self.source = self.__listener.source
        self.startTime = self.__listener.startTime
        self.__listener = listener
        self.message = self.__listener.message
        

    def processed_bytes(self):
        return self.__obj.processed_bytes

    def size_raw(self):
        return self.__size

    def size(self):
        return get_readable_file_size(self.__size)

    def status(self):
        return MirrorStatus.STATUS_UPLOADING

    def name(self):
        return self.__obj.name

    def progress_raw(self):
        try:
            return self.__obj.processed_bytes / self.__size * 100
        except ZeroDivisionError:
            return 0

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed_raw(self):
        """
        :return: Upload speed in Bytes/Seconds
        """
        return self.__obj.speed()

    def speed(self):
        return f'{get_readable_file_size(self.speed_raw())}/s'

    def eta(self):
        try:
            seconds = (self.__size - self.__obj.processed_bytes) / self.speed_raw()
            return f'{get_readable_time(seconds)}'
        except ZeroDivisionError:
            return '-'

    def gid(self) -> str:
        return self.__gid

    def download(self):
        return self.__obj

    def __source(self):
        if (reply_to := self.message.reply_to_message) and reply_to.from_user and not reply_to.from_user.is_bot:
            source = reply_to.from_user.username or reply_to.from_user.id
        elif self.__listener.tag == 'Anonymous':
            source = self.__listener.tag
        else:
            source = self.message.from_user.username or self.message.from_user.id
        if self.__listener.isSuperGroup:
            return f"<a href='{self.message.link}'>{source}</a>"
        else:
            return f"<i>{source}</i>"

    
