import logging
import random

from time import time
from threading import RLock, Lock, Thread

from bot import LOGGER, download_dict, download_dict_lock, app, STOP_DUPLICATE
from ..status_utils.telegram_download_status import TelegramDownloadStatus
from bot.helper.telegram_helper.message_utils import sendMarkup, sendStatusMessage
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper

global_lock = Lock()
GLOBAL_GID = set()
logging.getLogger("pyrogram").setLevel(logging.WARNING)


class TelegramDownloadHelper:
    def __init__(self, listener):
        self.name = ""
        self.size = 0
        self.progress = 0
        self.downloaded_bytes = 0
        self.__start_time = time()
        self.__listener = listener
        self.__id = ""
        self.__is_cancelled = False
        self.__resource_lock = RLock()

    @property
    def download_speed(self):
        with self.__resource_lock:
            return self.downloaded_bytes / (time() - self.__start_time)

    def __onDownloadStart(self, name, size, file_id):
        with global_lock:
            GLOBAL_GID.add(file_id)
        with self.__resource_lock:
            self.name = name
            self.size = size
            self.__id = file_id
        gid = ''.join(random.choices(file_id, k=12))
        with download_dict_lock:
            download_dict[self.__listener.uid] = TelegramDownloadStatus(self, self.__listener, gid)
        sendStatusMessage(self.__listener.update, self.__listener.bot)

    def __onDownloadProgress(self, current, total):
        if self.__is_cancelled:
            self.__onDownloadError('Cancelled by user!')
            app.stop_transmission()
            return
        with self.__resource_lock:
            self.downloaded_bytes = current
            try:
                self.progress = current / self.size * 100
            except ZeroDivisionError:
                pass

    def __onDownloadError(self, error):
        with global_lock:
            try:
                GLOBAL_GID.remove(self.__id)
            except KeyError:
                pass
        self.__listener.onDownloadError(error)

    def __onDownloadComplete(self):
        with global_lock:
            GLOBAL_GID.remove(self.__id)
        self.__listener.onDownloadComplete()

    def __download(self, message, path):
        try:
            download = app.download_media(message,
                                                progress = self.__onDownloadProgress,
                                                file_name = path
                                               )
        except Exception as e:
            LOGGER.error(str(e))
            return self.__onDownloadError(str(e))
        if download is not None:
            self.__onDownloadComplete()
        elif not self.__is_cancelled:
            self.__onDownloadError('Internal error occurred')

    def add_download(self, message, path, filename):
        _message = app.get_messages(message.chat.id, reply_to_message_ids=message.message_id)
        media = None
        media_array = [_message.document, _message.video, _message.audio]
        for i in media_array:
            if i is not None:
                media = i
                break
        if media is not None:
            with global_lock:
                # For avoiding locking the thread lock for long time unnecessarily
                download = media.file_id not in GLOBAL_GID
            if filename == "":
                name = media.file_name
            else:
                name = filename
                path = path + name

            if download:
                if STOP_DUPLICATE and not self.__listener.isLeech:
                    LOGGER.info('Checking File/Folder if already in Drive...')
                    smsg, button = GoogleDriveHelper().drive_list(name, True, True)
                    if smsg:
                        msg = "File/Folder is already available in Drive.\nHere are the search results:"
                        return sendMarkup(msg, self.__listener.bot, self.__listener.update, button)
                self.__onDownloadStart(name, media.file_size, media.file_id)
                LOGGER.info(f'Downloading Telegram file with id: {media.file_id}')
                Thread(target=self.__download, args=(_message, path)).start()
            else:
                self.__onDownloadError('File already being downloaded!')
        else:
            self.__onDownloadError('No document in the replied message')

    def cancel_download(self):
        LOGGER.info(f'Cancelling download on user request: {self.__id}')
        self.__is_cancelled = True
