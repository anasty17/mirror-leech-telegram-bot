#!/usr/bin/env python3
from logging import getLogger, ERROR
from time import time
from asyncio import Lock, Event

from bot import LOGGER, download_dict, download_dict_lock, config_dict, non_queued_dl, non_queued_up, queued_dl, queue_dict_lock, bot, user, IS_PREMIUM_USER
from ..status_utils.telegram_download_status import TelegramDownloadStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.telegram_helper.message_utils import sendStatusMessage, sendMessage
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.bot_utils import sync_to_async

global_lock = Lock()
GLOBAL_GID = set()
getLogger("pyrogram").setLevel(ERROR)


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

    @property
    def download_speed(self):
        return self.downloaded_bytes / (time() - self.__start_time)

    async def __onDownloadStart(self, name, size, file_id, from_queue):
        async with global_lock:
            GLOBAL_GID.add(file_id)
        self.name = name
        self.size = size
        self.__id = file_id
        async with download_dict_lock:
            download_dict[self.__listener.uid] = TelegramDownloadStatus(self, self.__listener.message, file_id[:12])
        async with queue_dict_lock:
            non_queued_dl.add(self.__listener.uid)
        if not from_queue:
            await self.__listener.onDownloadStart()
            await sendStatusMessage(self.__listener.message)
            LOGGER.info(f'Download from Telegram: {name}')
        else:
            LOGGER.info(f'Start Queued Download from Telegram: {name}')

    async def __onDownloadProgress(self, current, total):
        if self.__is_cancelled:
            if IS_PREMIUM_USER:
                user.stop_transmission()
            else:
                bot.stop_transmission()
        self.downloaded_bytes = current
        try:
            self.progress = current / self.size * 100
        except:
            pass

    async def __onDownloadError(self, error):
        async with global_lock:
            try:
                GLOBAL_GID.remove(self.__id)
            except:
                pass
        await self.__listener.onDownloadError(error)

    async def __onDownloadComplete(self):
        await self.__listener.onDownloadComplete()
        async with global_lock:
            GLOBAL_GID.remove(self.__id)

    async def __download(self, message, path):
        try:
            download = await message.download(file_name=path, progress=self.__onDownloadProgress)
            if self.__is_cancelled:
                await self.__onDownloadError('Cancelled by user!')
                return
        except Exception as e:
            LOGGER.error(str(e))
            await self.__onDownloadError(str(e))
            return
        if download is not None:
            await self.__onDownloadComplete()
        elif not self.__is_cancelled:
            await self.__onDownloadError('Internal error occurred')

    async def add_download(self, message, path, filename):
        if IS_PREMIUM_USER:
            if not self.__listener.isSuperGroup:
                await sendMessage(message, 'Use SuperGroup to download with User!')
                return
            message = await user.get_messages(chat_id=message.chat.id, message_ids=message.id)
        media = message.document or message.photo or message.video or message.audio or \
                 message.voice or message.video_note or message.sticker or message.animation or None
        if media is not None:
            async with global_lock:
                download = media.file_unique_id not in GLOBAL_GID
            if download:
                if filename == "":
                    name = media.file_name if hasattr(media, 'file_name') else 'None'
                else:
                    name = filename
                    path = path + name
                size = media.file_size
                gid = media.file_unique_id
                if config_dict['STOP_DUPLICATE'] and not self.__listener.isLeech and self.__listener.upPath == 'gd':
                    LOGGER.info('Checking File/Folder if already in Drive...')
                    smsg, button = await sync_to_async(GoogleDriveHelper().drive_list, name, True, True)
                    if smsg:
                        msg = "File/Folder is already available in Drive.\nHere are the search results:"
                        await sendMessage(self.__listener.message, msg, button)
                        return
                all_limit = config_dict['QUEUE_ALL']
                dl_limit = config_dict['QUEUE_DOWNLOAD']
                from_queue = False
                if all_limit or dl_limit:
                    added_to_queue = False
                    async with queue_dict_lock:
                        dl = len(non_queued_dl)
                        up = len(non_queued_up)
                        if (all_limit and dl + up >= all_limit and (not dl_limit or dl >= dl_limit)) or (dl_limit and dl >= dl_limit):
                            added_to_queue = True
                            event = Event()
                            queued_dl[self.__listener.uid] = event
                    if added_to_queue:
                        LOGGER.info(f"Added to Queue/Download: {name}")
                        async with download_dict_lock:
                            download_dict[self.__listener.uid] = QueueStatus(name, size, gid, self.__listener, 'Dl')
                        await self.__listener.onDownloadStart()
                        await sendStatusMessage(self.__listener.message)
                        await event.wait()
                        async with download_dict_lock:
                            if self.__listener.uid not in download_dict:
                                return
                        from_queue = True
                await self.__onDownloadStart(name, size, gid, from_queue)
                await self.__download(message, path)
            else:
                await self.__onDownloadError('File already being downloaded!')
        else:
            await self.__onDownloadError('No document in the replied message')

    async def cancel_download(self):
        LOGGER.info(f'Cancelling download on user request: {self.__id}')
        self.__is_cancelled = True
