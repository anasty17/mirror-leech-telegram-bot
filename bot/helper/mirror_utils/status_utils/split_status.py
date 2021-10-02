# Implement By - @anasty17 (https://github.com/SlamDevs/slam-mirrorbot/commit/d888a1e7237f4633c066f7c2bbfba030b83ad616)
# (c) https://github.com/SlamDevs/slam-mirrorbot
# All rights reserved

from .status import Status
from bot.helper.ext_utils.bot_utils import get_readable_file_size, MirrorStatus


class SplitStatus(Status):
    def __init__(self, name, path, size):
        self.__name = name
        self.__path = path
        self.__size = size

    # The progress of Tar function cannot be tracked. So we just return dummy values.
    # If this is possible in future,we should implement it

    def progress(self):
        return '0'

    def speed(self):
        return '0'

    def name(self):
        return self.__name

    def path(self):
        return self.__path

    def size(self):
        return get_readable_file_size(self.__size)

    def eta(self):
        return '0s'

    def status(self):
        return MirrorStatus.STATUS_SPLITTING

    def processed_bytes(self):
        return 0
