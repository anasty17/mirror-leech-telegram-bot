import threading
import time

from pyrogram import Client

from bot import LOGGER, bot, download_dict, download_dict_lock, TELEGRAM_API, \
    TELEGRAM_HASH, USER_SESSION_STRING
from .download_helper import DownloadHelper
from ..status_utils.telegram_download_status import TelegramDownloadStatus

global_lock = threading.Lock()
GLOBAL_GID = set()


class TelegramDownloadHelper(DownloadHelper):
    def __init__(self, listener):
        super().__init__()
        self.__listener = listener
        self.__resource_lock = threading.RLock()
        self.__name = ""
        self.__gid = ''
        self.__start_time = time.time()
        self.__user_bot = Client(api_id=TELEGRAM_API,
                                 api_hash=TELEGRAM_HASH,
                                 session_name=USER_SESSION_STRING)
        self.__user_bot.start()

    @property
    def gid(self):
        with self.__resource_lock:
            return self.__gid

    @property
    def download_speed(self):
        with self.__resource_lock:
            return self.downloaded_bytes / (time.time() - self.__start_time)

    def __onDownloadStart(self, name, size, file_id):
        with download_dict_lock:
            download_dict[self.__listener.uid] = TelegramDownloadStatus(self, self.__listener.uid)
        with global_lock:
            GLOBAL_GID.add(file_id)
        with self.__resource_lock:
            self.name = name
            self.size = size
            self.__gid = file_id
        self.__listener.onDownloadStarted()

    def __onDownloadProgress(self, current, total):
        with self.__resource_lock:
            self.downloaded_bytes = current
            try:
                self.progress = current / self.size * 100
            except ZeroDivisionError:
                return 0

    def __onDownloadComplete(self):

        self.__listener.onDownloadComplete()

    def __download(self, message, path):
        self.__user_bot.download_media(message,
                                       progress=self.__onDownloadProgress, file_name=path)
        self.__onDownloadComplete()

    def add_download(self, message, path):
        if message.chat.type == "private":
            _message = self.__user_bot.get_messages(bot.get_me().id, message.message_id)
        else:
            _message = self.__user_bot.get_messages(message.chat.id, message.message_id)
        media = _message.document
        if media is not None:
            with global_lock:
                # For avoiding locking the thread lock for long time unnecessarily
                download = media.file_id not in GLOBAL_GID

            if download:
                self.__onDownloadStart(media.file_name, media.file_size, media.file_id)
                LOGGER.info(media.file_id)
                threading.Thread(target=self.__download, args=(_message, path)).start()
            else:
                self.__listener.onDownloadError('File already being downloaded!')
        else:
            self.__listener.onDownloadError('No document in the replied message')
