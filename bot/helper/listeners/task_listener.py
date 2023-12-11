from requests import utils as rutils
from aiofiles.os import path as aiopath, listdir, makedirs
from html import escape
from aioshutil import move
from asyncio import sleep, Event, gather

from bot import (
    Interval,
    aria2,
    DOWNLOAD_DIR,
    task_dict,
    task_dict_lock,
    LOGGER,
    DATABASE_URL,
    config_dict,
    non_queued_up,
    non_queued_dl,
    queued_up,
    queued_dl,
    queue_dict_lock,
)
from bot.helper.ext_utils.files_utils import (
    get_path_size,
    clean_download,
    clean_target,
    join_files,
)
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    delete_status,
    update_status_message,
)
from bot.helper.ext_utils.status_utils import get_readable_file_size
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.links_utils import is_gdrive_id
from bot.helper.ext_utils.task_manager import start_from_queued
from bot.helper.mirror_utils.status_utils.gdrive_status import GdriveStatus
from bot.helper.mirror_utils.status_utils.telegram_status import TelegramStatus
from bot.helper.mirror_utils.status_utils.rclone_status import RcloneStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.mirror_utils.gdrive_utils.upload import gdUpload
from bot.helper.mirror_utils.telegram_uploader import TgUploader
from bot.helper.mirror_utils.rclone_utils.transfer import RcloneTransferHelper
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.common import TaskConfig


class TaskListener(TaskConfig):
    def __init__(self):
        super().__init__()

    async def clean(self):
        try:
            if Interval:
                for intvl in list(Interval.values()):
                    intvl.cancel()
            Interval.clear()
            await gather(sync_to_async(aria2.purge), delete_status())
        except:
            pass

    def removeFromSameDir(self):
        if self.sameDir and self.mid in self.sameDir["tasks"]:
            self.sameDir["tasks"].remove(self.mid)
            self.sameDir["total"] -= 1

    async def onDownloadStart(self):
        if (
            self.isSuperChat
            and config_dict["INCOMPLETE_TASK_NOTIFIER"]
            and DATABASE_URL
        ):
            await DbManger().add_incomplete_task(
                self.message.chat.id, self.message.link, self.tag
            )

    async def onDownloadComplete(self):
        multi_links = False
        if self.sameDir and self.mid in self.sameDir["tasks"]:
            while not (
                self.sameDir["total"] in [1, 0]
                or self.sameDir["total"] > 1
                and len(self.sameDir["tasks"]) > 1
            ):
                await sleep(0.5)

        async with task_dict_lock:
            if (
                self.sameDir
                and self.sameDir["total"] > 1
                and self.mid in self.sameDir["tasks"]
            ):
                self.sameDir["tasks"].remove(self.mid)
                self.sameDir["total"] -= 1
                folder_name = self.sameDir["name"]
                spath = f"{self.dir}{folder_name}"
                des_path = (
                    f"{DOWNLOAD_DIR}{list(self.sameDir['tasks'])[0]}{folder_name}"
                )
                await makedirs(des_path, exist_ok=True)
                for item in await listdir(spath):
                    if item.endswith((".aria2", ".!qB")):
                        continue
                    item_path = f"{self.dir}{folder_name}/{item}"
                    if item in await listdir(des_path):
                        await move(item_path, f"{des_path}/{self.mid}-{item}")
                    else:
                        await move(item_path, f"{des_path}/{item}")
                multi_links = True
            download = task_dict[self.mid]
            self.name = download.name()
            gid = download.gid()
        LOGGER.info(f"Download completed: {self.name}")

        if multi_links:
            await self.onUploadError("Downloaded! Waiting for other tasks...")
            return

        if not await aiopath.exists(f"{self.dir}/{self.name}"):
            try:
                files = await listdir(self.dir)
                self.name = files[-1]
                if self.name == "yt-dlp-thumb":
                    self.name = files[0]
            except Exception as e:
                await self.onUploadError(str(e))
                return

        up_path = f"{self.dir}/{self.name}"
        size = await get_path_size(up_path)
        async with queue_dict_lock:
            if self.mid in non_queued_dl:
                non_queued_dl.remove(self.mid)
        await start_from_queued()

        if self.join and await aiopath.isdir(up_path):
            await join_files(up_path)

        if self.extract:
            up_path = await self.proceedExtract(up_path, size, gid)
            if not up_path:
                return
            up_dir, self.name = up_path.rsplit("/", 1)
            size = await get_path_size(up_dir)

        if self.sampleVideo:
            up_path = await self.generateSampleVideo(up_path, size, gid)
            if not up_path:
                return
            up_dir, self.name = up_path.rsplit("/", 1)
            size = await get_path_size(up_dir)

        if self.compress:
            up_path = await self.proceedCompress(up_path, size, gid)
            if not up_path:
                return

        up_dir, self.name = up_path.rsplit("/", 1)
        size = await get_path_size(up_dir)

        if self.isLeech:
            m_size = []
            o_files = []
            if not self.compress:
                result = await self.proceedSplit(up_dir, m_size, o_files, size, gid)
                if not result:
                    return

        up_limit = config_dict["QUEUE_UPLOAD"]
        all_limit = config_dict["QUEUE_ALL"]
        add_to_queue = False
        async with queue_dict_lock:
            dl = len(non_queued_dl)
            up = len(non_queued_up)
            if (
                all_limit and dl + up >= all_limit and (not up_limit or up >= up_limit)
            ) or (up_limit and up >= up_limit):
                add_to_queue = True
                LOGGER.info(f"Added to Queue/Upload: {self.name}")
                event = Event()
                queued_up[self.mid] = event
        if add_to_queue:
            async with task_dict_lock:
                task_dict[self.mid] = QueueStatus(self, size, gid, "Up")
            await event.wait()
            async with task_dict_lock:
                if self.mid not in task_dict:
                    return
            LOGGER.info(f"Start from Queued/Upload: {self.name}")
        async with queue_dict_lock:
            non_queued_up.add(self.mid)

        if self.isLeech:
            size = await get_path_size(up_dir)
            for s in m_size:
                size -= s
            LOGGER.info(f"Leech Name: {self.name}")
            tg = TgUploader(self, up_dir)
            async with task_dict_lock:
                task_dict[self.mid] = TelegramStatus(self, tg, size, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                tg.upload(o_files, m_size, size),
            )
        elif is_gdrive_id(self.upDest):
            size = await get_path_size(up_path)
            LOGGER.info(f"Gdrive Upload Name: {self.name}")
            drive = gdUpload(self, up_path)
            async with task_dict_lock:
                task_dict[self.mid] = GdriveStatus(self, drive, size, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                sync_to_async(drive.upload, size),
            )
        else:
            size = await get_path_size(up_path)
            LOGGER.info(f"Rclone Upload Name: {self.name}")
            RCTransfer = RcloneTransferHelper(self)
            async with task_dict_lock:
                task_dict[self.mid] = RcloneStatus(self, RCTransfer, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                RCTransfer.upload(up_path, size),
            )

    async def onUploadComplete(
        self, link, size, files, folders, mime_type, rclonePath="", dir_id=""
    ):
        if (
            self.isSuperChat
            and config_dict["INCOMPLETE_TASK_NOTIFIER"]
            and DATABASE_URL
        ):
            await DbManger().rm_complete_task(self.message.link)
        msg = f"<b>Name: </b><code>{escape(self.name)}</code>\n\n<b>Size: </b>{get_readable_file_size(size)}"
        LOGGER.info(f"Task Done: {self.name}")
        if self.isLeech:
            msg += f"\n<b>Total Files: </b>{folders}"
            if mime_type != 0:
                msg += f"\n<b>Corrupted Files: </b>{mime_type}"
            msg += f"\n<b>cc: </b>{self.tag}\n\n"
            if not files:
                await sendMessage(self.message, msg)
            else:
                fmsg = ""
                for index, (link, name) in enumerate(files.items(), start=1):
                    fmsg += f"{index}. <a href='{link}'>{name}</a>\n"
                    if len(fmsg.encode() + msg.encode()) > 4000:
                        await sendMessage(self.message, msg + fmsg)
                        await sleep(1)
                        fmsg = ""
                if fmsg != "":
                    await sendMessage(self.message, msg + fmsg)
            if self.seed:
                if self.newDir:
                    await clean_target(self.newDir)
                async with queue_dict_lock:
                    if self.mid in non_queued_up:
                        non_queued_up.remove(self.mid)
                await start_from_queued()
                return
        else:
            msg += f"\n\n<b>Type: </b>{mime_type}"
            if mime_type == "Folder":
                msg += f"\n<b>SubFolders: </b>{folders}"
                msg += f"\n<b>Files: </b>{files}"
            if (
                link
                or rclonePath
                and config_dict["RCLONE_SERVE_URL"]
                and not self.privateLink
            ):
                buttons = ButtonMaker()
                if link:
                    buttons.ubutton("☁️ Cloud Link", link)
                else:
                    msg += f"\n\nPath: <code>{rclonePath}</code>"
                if (
                    rclonePath
                    and (RCLONE_SERVE_URL := config_dict["RCLONE_SERVE_URL"])
                    and not self.privateLink
                ):
                    remote, path = rclonePath.split(":", 1)
                    url_path = rutils.quote(f"{path}")
                    share_url = f"{RCLONE_SERVE_URL}/{remote}/{url_path}"
                    if mime_type == "Folder":
                        share_url += "/"
                    buttons.ubutton("🔗 Rclone Link", share_url)
                if not rclonePath and dir_id:
                    INDEX_URL = ""
                    if self.privateLink:
                        INDEX_URL = (
                            self.user_dict["index_url"]
                            if self.user_dict.get("index_url")
                            else ""
                        )
                    elif config_dict["INDEX_URL"]:
                        INDEX_URL = config_dict["INDEX_URL"]
                    if INDEX_URL:
                        share_url = f"{INDEX_URL}findpath?id={dir_id}"
                        buttons.ubutton("⚡ Index Link", share_url)
                        if mime_type.startswith(("image", "video", "audio")):
                            share_urls = f"{INDEX_URL}findpath?id={dir_id}&view=true"
                            buttons.ubutton("🌐 View Link", share_urls)
                button = buttons.build_menu(2)
            else:
                msg += f"\n\nPath: <code>{rclonePath}</code>"
                button = None
            msg += f"\n\n<b>cc: </b>{self.tag}"
            await sendMessage(self.message, msg, button)
            if self.seed:
                if self.newDir:
                    await clean_target(self.newDir)
                elif self.compress:
                    await clean_target(f"{self.dir}/{self.name}")
                async with queue_dict_lock:
                    if self.mid in non_queued_up:
                        non_queued_up.remove(self.mid)
                await start_from_queued()
                return

        await clean_download(self.dir)
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        async with queue_dict_lock:
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()

    async def onDownloadError(self, error, button=None):
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
            self.removeFromSameDir()
        msg = f"{self.tag} Download: {escape(error)}"
        await sendMessage(self.message, msg, button)
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        if (
            self.isSuperChat
            and config_dict["INCOMPLETE_TASK_NOTIFIER"]
            and DATABASE_URL
        ):
            await DbManger().rm_complete_task(self.message.link)

        async with queue_dict_lock:
            if self.mid in queued_dl:
                queued_dl[self.mid].set()
                del queued_dl[self.mid]
            if self.mid in queued_up:
                queued_up[self.mid].set()
                del queued_up[self.mid]
            if self.mid in non_queued_dl:
                non_queued_dl.remove(self.mid)
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()
        await sleep(3)
        await clean_download(self.dir)
        if self.newDir:
            await clean_download(self.newDir)

    async def onUploadError(self, error):
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        await sendMessage(self.message, f"{self.tag} {escape(error)}")
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        if (
            self.isSuperChat
            and config_dict["INCOMPLETE_TASK_NOTIFIER"]
            and DATABASE_URL
        ):
            await DbManger().rm_complete_task(self.message.link)

        async with queue_dict_lock:
            if self.mid in queued_dl:
                queued_dl[self.mid].set()
                del queued_dl[self.mid]
            if self.mid in queued_up:
                queued_up[self.mid].set()
                del queued_up[self.mid]
            if self.mid in non_queued_dl:
                non_queued_dl.remove(self.mid)
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()
        await sleep(3)
        await clean_download(self.dir)
        if self.newDir:
            await clean_download(self.newDir)
