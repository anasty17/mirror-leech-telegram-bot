from asyncio import Lock, sleep
from time import time
from pyrogram.errors import FloodWait

from bot import (
    LOGGER,
    task_dict,
    task_dict_lock,
    non_queued_dl,
    queue_dict_lock,
    bot,
    user,
)
from bot.helper.ext_utils.task_manager import check_running_tasks, stop_duplicate_check
from bot.helper.mirror_leech_utils.status_utils.queue_status import QueueStatus
from bot.helper.mirror_leech_utils.status_utils.telegram_status import TelegramStatus
from bot.helper.telegram_helper.message_utils import sendStatusMessage

global_lock = Lock()
GLOBAL_GID = set()


class TelegramDownloadHelper:
    def __init__(self, listener):
        self._processed_bytes = 0
        self._start_time = time()
        self._listener = listener
        self._id = ""
        self.session = ""

    @property
    def speed(self):
        return self._processed_bytes / (time() - self._start_time)

    @property
    def processed_bytes(self):
        return self._processed_bytes

    async def _onDownloadStart(self, file_id, from_queue):
        async with global_lock:
            GLOBAL_GID.add(file_id)
        self._id = file_id
        async with task_dict_lock:
            task_dict[self._listener.mid] = TelegramStatus(
                self._listener, self, file_id[:12], "dl"
            )
        if not from_queue:
            await self._listener.onDownloadStart()
            if self._listener.multi <= 1:
                await sendStatusMessage(self._listener.message)
            LOGGER.info(f"Download from Telegram: {self._listener.name}")
        else:
            LOGGER.info(f"Start Queued Download from Telegram: {self._listener.name}")

    async def _onDownloadProgress(self, current, total):
        if self._listener.isCancelled:
            if self.session == "user":
                user.stop_transmission()
            else:
                bot.stop_transmission()
        self._processed_bytes = current

    async def _onDownloadError(self, error):
        async with global_lock:
            try:
                GLOBAL_GID.remove(self._id)
            except:
                pass
        await self._listener.onDownloadError(error)

    async def _onDownloadComplete(self):
        await self._listener.onDownloadComplete()
        async with global_lock:
            GLOBAL_GID.remove(self._id)

    async def _download(self, message, path):
        try:
            download = await message.download(
                file_name=path, progress=self._onDownloadProgress
            )
            if self._listener.isCancelled:
                await self._onDownloadError("Cancelled by user!")
                return
        except FloodWait as f:
            LOGGER.warning(str(f))
            await sleep(f.value)
        except Exception as e:
            LOGGER.error(str(e))
            await self._onDownloadError(str(e))
            return
        if download is not None:
            await self._onDownloadComplete()
        elif not self._listener.isCancelled:
            await self._onDownloadError("Internal error occurred")

    async def add_download(self, message, path, session):
        self.session = session
        if (
            self.session not in ["user", "bot"]
            and self._listener.userTransmission
            and self._listener.isSuperChat
        ):
            self.session = "user"
            message = await user.get_messages(
                chat_id=message.chat.id, message_ids=message.id
            )
        elif self.session != "user":
            self.session = "bot"

        media = (
            message.document
            or message.photo
            or message.video
            or message.audio
            or message.voice
            or message.video_note
            or message.sticker
            or message.animation
            or None
        )

        if media is not None:
            async with global_lock:
                download = media.file_unique_id not in GLOBAL_GID

            if download:
                if self._listener.name == "":
                    self._listener.name = (
                        media.file_name if hasattr(media, "file_name") else "None"
                    )
                else:
                    path = path + self._listener.name
                self._listener.size = media.file_size
                gid = media.file_unique_id

                msg, button = await stop_duplicate_check(self._listener)
                if msg:
                    await self._listener.onDownloadError(msg, button)
                    return

                add_to_queue, event = await check_running_tasks(self._listener)
                if add_to_queue:
                    LOGGER.info(f"Added to Queue/Download: {self._listener.name}")
                    async with task_dict_lock:
                        task_dict[self._listener.mid] = QueueStatus(
                            self._listener, gid, "dl"
                        )
                    await self._listener.onDownloadStart()
                    if self._listener.multi <= 1:
                        await sendStatusMessage(self._listener.message)
                    await event.wait()
                    if self._listener.isCancelled:
                        return
                    async with queue_dict_lock:
                        non_queued_dl.add(self._listener.mid)

                await self._onDownloadStart(gid, add_to_queue)
                await self._download(message, path)
            else:
                await self._onDownloadError("File already being downloaded!")
        else:
            await self._onDownloadError(
                "No document in the replied message! Use SuperGroup incase you are trying to download with User session!"
            )

    async def cancel_task(self):
        self._listener.isCancelled = True
        LOGGER.info(
            f"Cancelling download on user request: name: {self._listener.name} id: {self._id}"
        )
