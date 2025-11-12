from asyncio import Lock, sleep
from time import time
from aioshutil import move
from aiofiles.os import makedirs

from .... import (
    LOGGER,
    task_dict,
    task_dict_lock,
)
from ....core.telegram_client import TgManager
from ...ext_utils.task_manager import check_running_tasks, stop_duplicate_check
from ...mirror_leech_utils.status_utils.queue_status import QueueStatus
from ...mirror_leech_utils.status_utils.telegram_status import TelegramStatus
from ...telegram_helper.message_utils import send_status_message
from ...telegram_helper.progress import tracker

global_lock = Lock()
GLOBAL_GID = set()


class TelegramDownloadHelper:
    def __init__(self, listener):
        self._processed_bytes = 0
        self._start_time = 1
        self._listener = listener
        self._gid = ""
        self.session = ""

    @property
    def speed(self):
        return self._processed_bytes / (time() - self._start_time)

    @property
    def processed_bytes(self):
        return self._processed_bytes

    async def _on_download_start(self, from_queue):
        async with global_lock:
            GLOBAL_GID.add(self._gid)
        async with task_dict_lock:
            task_dict[self._listener.mid] = TelegramStatus(
                self._listener, self, self._gid, "dl"
            )
        if not from_queue:
            await self._listener.on_download_start()
            if self._listener.multi <= 1:
                await send_status_message(self._listener.message)
            LOGGER.info(f"Download from Telegram: {self._listener.name}")
        else:
            LOGGER.info(f"Start Queued Download from Telegram: {self._listener.name}")

    async def _download_progress(self, key, progress_dict, _, file_id):
        if self._listener.is_cancelled:
            if self.session == "user":
                await TgManager.user.cancelDownloadFile(file_id=file_id)
            else:
                await TgManager.bot.cancelDownloadFile(file_id=file_id)
            await tracker.cancel_progress(key)
        self._processed_bytes = progress_dict["transferred"]

    async def _on_download_error(self, error):
        async with global_lock:
            if self._gid in GLOBAL_GID:
                GLOBAL_GID.remove(self._gid)
        await self._listener.on_download_error(error)

    async def _on_download_complete(self):
        async with global_lock:
            if self._gid in GLOBAL_GID:
                GLOBAL_GID.remove(self._gid)
        await self._listener.on_download_complete()

    async def _download(self, message, dl_path):
        download = await message.download(synchronous=True)
        if download.is_error:
            if wait_for := download.limited_seconds:
                LOGGER.warning(download["message"])
                await sleep(wait_for * 1.2)
                return await self._download(message, dl_path)
            LOGGER.error(download["message"])
            await self._on_download_error(download["message"])
            return
        if self._listener.is_cancelled:
            return
        if download.is_downloading_completed:
            current_path = download.path
            await makedirs(dl_path.rsplit("/", 1)[0], exist_ok=True)
            await move(current_path, dl_path)
            await self._on_download_complete()

    async def add_download(self, message, dl_path, session):
        self.session = session
        if not self.session:
            if self._listener.user_transmission and self._listener.is_super_chat:
                self.session = "user"
                message = await TgManager.user.getMessage(
                    chat_id=message.chat_id, message_id=message.id
                )
            else:
                self.session = "bot"
        content_type = message.content.getType()
        if content_type == "messageDocument":
            media = message.content.document
            media_file = media.document
        elif content_type == "messagePhoto":
            media = message.content.photo.sizes[-1].photo
            media_file = media
        elif content_type == "messageVideo":
            media = message.content.video
            media_file = media.video
        elif content_type == "messageAudio":
            media = message.content.audio
            media_file = media.audio
        elif content_type == "messageVoiceNote":
            media = message.content.voice_note
            media_file = media.voice
        elif content_type == "messageVideoNote":
            media = message.content.video_note
            media_file = media.video
        elif content_type == "messageSticker":
            media = message.content.sticker
            media_file = media.sticker
        elif content_type == "messageAnimation":
            media = message.content.animation
            media_file = media.animation
        else:
            media = None
        if media is not None:
            self._gid = message.remote_unique_file_id
            async with global_lock:
                download = self._gid not in GLOBAL_GID
            if download:
                if not self._listener.name:
                    if content_type in ["messagePhoto", "messageSticker"]:
                        self._listener.name = (
                            f"{time()}." + "jpeg"
                            if content_type == "messagePhoto"
                            else "webm"
                        )
                    else:
                        self._listener.name = media.file_name
                dl_path = dl_path + self._listener.name
                self._listener.size = media_file.size or media_file.expected_size

                msg, button = await stop_duplicate_check(self._listener)
                if msg:
                    await self._listener.on_download_error(msg, button)
                    return

                add_to_queue, event = await check_running_tasks(self._listener)
                if add_to_queue:
                    LOGGER.info(f"Added to Queue/Download: {self._listener.name}")
                    async with task_dict_lock:
                        task_dict[self._listener.mid] = QueueStatus(
                            self._listener, self._gid, "dl"
                        )
                    await self._listener.on_download_start()
                    if self._listener.multi <= 1:
                        await send_status_message(self._listener.message)
                    await event.wait()
                    if self._listener.is_cancelled:
                        return
                    if self.session == "bot":
                        message = await self._listener.client.getMessage(
                            chat_id=message.chat_id, message_id=message.id
                        )
                    else:
                        message = await TgManager.user.getMessage(
                            chat_id=message.chat_id, message_id=message.id
                        )
                    if message.is_error:
                        await self._on_download_error(message["message"])
                        return
                self._start_time = time()
                await self._on_download_start(add_to_queue)
                await tracker.add_to_progress(
                    media_file.remote.id,
                    callback=self._download_progress,
                )
                await self._download(message, dl_path)
            else:
                await self._on_download_error("File already being downloaded!")
        else:
            await self._on_download_error(
                "No document in the replied message! Use SuperGroup incase you are trying to download with User session!"
            )

    async def cancel_task(self):
        self._listener.is_cancelled = True
        LOGGER.info(
            f"Cancelling download on user request: name: {self._listener.name} id: {self._id}"
        )
        await self._on_download_error("Stopped by user!")
