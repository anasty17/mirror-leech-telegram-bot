from asyncio import Lock, sleep
from time import time
from pyrogram.errors import FloodWait, FloodPremiumWait

from .... import (
    LOGGER,
    task_dict,
    task_dict_lock,
)
from ....core.mltb_client import TgClient
from ...ext_utils.task_manager import check_running_tasks, stop_duplicate_check
from ...mirror_leech_utils.status_utils.queue_status import QueueStatus
from ...mirror_leech_utils.status_utils.telegram_status import TelegramStatus
from ...telegram_helper.message_utils import send_status_message

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

    async def _on_download_start(self, file_id, from_queue):
        async with global_lock:
            GLOBAL_GID.add(file_id)
        self._id = file_id
        async with task_dict_lock:
            task_dict[self._listener.mid] = TelegramStatus(
                self._listener, self, file_id[:12], "dl"
            )
        if not from_queue:
            await self._listener.on_download_start()
            if self._listener.multi <= 1:
                await send_status_message(self._listener.message)
            LOGGER.info(f"Download from Telegram: {self._listener.name}")
        else:
            LOGGER.info(f"Start Queued Download from Telegram: {self._listener.name}")

    async def _on_download_progress(self, current, _):
        if self._listener.is_cancelled:
            if self.session == "user":
                TgClient.user.stop_transmission()
            else:
                TgClient.bot.stop_transmission()
        self._processed_bytes = current

    async def _on_download_error(self, error):
        async with global_lock:
            if self._id in GLOBAL_GID:
                GLOBAL_GID.remove(self._id)
        await self._listener.on_download_error(error)

    async def _on_download_complete(self):
        await self._listener.on_download_complete()
        async with global_lock:
            GLOBAL_GID.remove(self._id)

    async def _download(self, message, path):
        try:
            download = await message.download(
                file_name=path, progress=self._on_download_progress
            )
            if self._listener.is_cancelled:
                return
        except (FloodWait, FloodPremiumWait) as f:
            LOGGER.warning(str(f))
            await sleep(f.value)
            await self._download(message, path)
            return
        except Exception as e:
            LOGGER.error(str(e))
            await self._on_download_error(str(e))
            return
        if download is not None:
            await self._on_download_complete()
        elif not self._listener.is_cancelled:
            await self._on_download_error("Internal error occurred")

    async def add_download(self, message, path, session):
        self.session = session
        if (
            self.session not in ["user", "bot"]
            and self._listener.user_transmission
            and self._listener.is_super_chat
        ):
            self.session = "user"
            message = await TgClient.user.get_messages(
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
                    await self._listener.on_download_error(msg, button)
                    return

                add_to_queue, event = await check_running_tasks(self._listener)
                if add_to_queue:
                    LOGGER.info(f"Added to Queue/Download: {self._listener.name}")
                    async with task_dict_lock:
                        task_dict[self._listener.mid] = QueueStatus(
                            self._listener, gid, "dl"
                        )
                    await self._listener.on_download_start()
                    if self._listener.multi <= 1:
                        await send_status_message(self._listener.message)
                    await event.wait()
                    if self.session == "bot":
                        message = await self._listener.client.get_messages(
                            chat_id=message.chat.id, message_ids=message.id
                        )
                    else:
                        message = await TgClient.user.get_messages(
                            chat_id=message.chat.id, message_ids=message.id
                        )
                    if self._listener.is_cancelled:
                        async with global_lock:
                            if self._id in GLOBAL_GID:
                                GLOBAL_GID.remove(self._id)
                        return

                await self._on_download_start(gid, add_to_queue)
                await self._download(message, path)
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
