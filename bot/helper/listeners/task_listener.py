from requests import utils as rutils
from aiofiles.os import path as aiopath, remove as aioremove, listdir, makedirs
from os import walk, path as ospath
from html import escape
from aioshutil import move
from asyncio import create_subprocess_exec, sleep, Event

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
    GLOBAL_EXTENSION_FILTER,
)
from bot.helper.ext_utils.files_utils import (
    get_base_name,
    get_path_size,
    clean_download,
    clean_target,
    is_first_archive_split,
    is_archive,
    is_archive_split,
    join_files,
)
from bot.helper.ext_utils.status_utils import get_readable_file_size
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.links_utils import is_gdrive_id
from bot.helper.ext_utils.leech_utils import split_file
from bot.helper.ext_utils.exceptions import NotSupportedExtractionArchive
from bot.helper.ext_utils.task_manager import start_from_queued
from bot.helper.mirror_utils.status_utils.extract_status import ExtractStatus
from bot.helper.mirror_utils.status_utils.zip_status import ZipStatus
from bot.helper.mirror_utils.status_utils.split_status import SplitStatus
from bot.helper.mirror_utils.status_utils.gdrive_status import GdriveStatus
from bot.helper.mirror_utils.status_utils.telegram_status import TelegramStatus
from bot.helper.mirror_utils.status_utils.rclone_status import RcloneStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.mirror_utils.gdrive_utils.upload import gdUpload
from bot.helper.mirror_utils.telegram_uploader import TgUploader
from bot.helper.mirror_utils.rclone_utils.transfer import RcloneTransferHelper
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    delete_status,
    update_status_message,
)
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.common import TaskConfig


class TaskListener(TaskConfig):
    def __init__(self, message):
        super().__init__(message)

    async def clean(self):
        try:
            if Interval:
                for intvl in list(Interval.values()):
                    intvl.cancel()
            Interval.clear()
            await sync_to_async(aria2.purge)
            await delete_status()
        except:
            pass

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
                    item_path = f"{self.dir}/{folder_name}/{item}"
                    if item in await listdir(des_path):
                        await move(item_path, f"{des_path}/{self.mid}-{item}")
                    else:
                        await move(item_path, f"{des_path}/{item}")
                multi_links = True
            download = task_dict[self.mid]
            self.name = str(download.name())
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

        dl_path = f"{self.dir}/{self.name}"
        up_path = ""
        size = await get_path_size(dl_path)
        async with queue_dict_lock:
            if self.mid in non_queued_dl:
                non_queued_dl.remove(self.mid)
        await start_from_queued()

        if self.join and await aiopath.isdir(dl_path):
            await join_files(dl_path)

        if self.extract:
            pswd = self.extract if isinstance(self.extract, str) else ""
            try:
                if await aiopath.isfile(dl_path):
                    up_path = get_base_name(dl_path)
                LOGGER.info(f"Extracting: {self.name}")
                async with task_dict_lock:
                    task_dict[self.mid] = ExtractStatus(self, size, gid)
                if await aiopath.isdir(dl_path):
                    if self.seed:
                        self.newDir = f"{self.dir}10000"
                        up_path = f"{self.newDir}/{self.name}"
                    else:
                        up_path = dl_path
                    for dirpath, _, files in await sync_to_async(
                        walk, dl_path, topdown=False
                    ):
                        for file_ in files:
                            if (
                                is_first_archive_split(file_)
                                or is_archive(file_)
                                and not file_.endswith(".rar")
                            ):
                                f_path = ospath.join(dirpath, file_)
                                t_path = (
                                    dirpath.replace(self.dir, self.newDir)
                                    if self.seed
                                    else dirpath
                                )
                                cmd = [
                                    "7z",
                                    "x",
                                    f"-p{pswd}",
                                    f_path,
                                    f"-o{t_path}",
                                    "-aot",
                                    "-xr!@PaxHeader",
                                ]
                                if not pswd:
                                    del cmd[2]
                                if (
                                    self.suproc == "cancelled"
                                    or self.suproc is not None
                                    and self.suproc.returncode == -9
                                ):
                                    return
                                self.suproc = await create_subprocess_exec(*cmd)
                                code = await self.suproc.wait()
                                if code == -9:
                                    return
                                elif code != 0:
                                    LOGGER.error("Unable to extract archive splits!")
                        if (
                            not self.seed
                            and self.suproc is not None
                            and self.suproc.returncode == 0
                        ):
                            for file_ in files:
                                if is_archive_split(file_) or is_archive(file_):
                                    del_path = ospath.join(dirpath, file_)
                                    try:
                                        await aioremove(del_path)
                                    except:
                                        return
                else:
                    if self.seed:
                        self.newDir = f"{self.dir}10000"
                        up_path = up_path.replace(self.dir, self.newDir)
                    cmd = [
                        "7z",
                        "x",
                        f"-p{pswd}",
                        dl_path,
                        f"-o{up_path}",
                        "-aot",
                        "-xr!@PaxHeader",
                    ]
                    if not pswd:
                        del cmd[2]
                    if self.suproc == "cancelled":
                        return
                    self.suproc = await create_subprocess_exec(*cmd)
                    code = await self.suproc.wait()
                    if code == -9:
                        return
                    elif code == 0:
                        LOGGER.info(f"Extracted Path: {up_path}")
                        if not self.seed:
                            try:
                                await aioremove(dl_path)
                            except:
                                return
                    else:
                        LOGGER.error("Unable to extract archive! Uploading anyway")
                        self.newDir = ""
                        up_path = dl_path
            except NotSupportedExtractionArchive:
                LOGGER.info("Not any valid archive, uploading file as it is.")
                self.newDir = ""
                up_path = dl_path

        if self.compress:
            pswd = self.compress if isinstance(self.compress, str) else ""
            if up_path:
                dl_path = up_path
                up_path = f"{up_path}.zip"
            elif self.seed and self.isLeech:
                self.newDir = f"{self.dir}10000"
                up_path = f"{self.newDir}/{self.name}.zip"
            else:
                up_path = f"{dl_path}.zip"
            async with task_dict_lock:
                task_dict[self.mid] = ZipStatus(self, size, gid)
            if self.equalSplits:
                size = await get_path_size(dl_path)
                parts = -(-size // self.splitSize)
                split_size = (size // parts) + (size % parts)
            else:
                split_size = self.splitSize
            cmd = [
                "7z",
                f"-v{split_size}b",
                "a",
                "-mx=0",
                f"-p{pswd}",
                up_path,
                dl_path,
            ]
            for ext in GLOBAL_EXTENSION_FILTER:
                ex_ext = f"-xr!*.{ext}"
                cmd.append(ex_ext)
            if self.isLeech and int(size) > self.splitSize:
                if not pswd:
                    del cmd[4]
                LOGGER.info(f"Zip: orig_path: {dl_path}, zip_path: {up_path}.0*")
            else:
                del cmd[1]
                if not pswd:
                    del cmd[3]
                LOGGER.info(f"Zip: orig_path: {dl_path}, zip_path: {up_path}")
            if self.suproc == "cancelled":
                return
            self.suproc = await create_subprocess_exec(*cmd)
            code = await self.suproc.wait()
            if code == -9:
                return
            elif not self.seed:
                await clean_target(dl_path)

        if not self.compress and not self.extract:
            up_path = dl_path

        up_dir, self.name = up_path.rsplit("/", 1)
        size = await get_path_size(up_dir)
        if self.isLeech:
            m_size = []
            o_files = []
            if not self.compress:
                checked = False
                for dirpath, _, files in await sync_to_async(
                    walk, up_dir, topdown=False
                ):
                    for file_ in files:
                        f_path = ospath.join(dirpath, file_)
                        f_size = await aiopath.getsize(f_path)
                        if f_size > self.splitSize:
                            if not checked:
                                checked = True
                                async with task_dict_lock:
                                    task_dict[self.mid] = SplitStatus(self, size, gid)
                                LOGGER.info(f"Splitting: {self.name}")
                            res = await split_file(
                                f_path, f_size, file_, dirpath, self.splitSize, self
                            )
                            if not res:
                                return
                            if res == "errored":
                                if f_size <= self.maxSplitSize:
                                    continue
                                try:
                                    await aioremove(f_path)
                                except:
                                    return
                            elif not self.seed or self.newDir:
                                try:
                                    await aioremove(f_path)
                                except:
                                    return
                            else:
                                m_size.append(f_size)
                                o_files.append(file_)

        up_limit = config_dict["QUEUE_UPLOAD"]
        all_limit = config_dict["QUEUE_ALL"]
        added_to_queue = False
        async with queue_dict_lock:
            dl = len(non_queued_dl)
            up = len(non_queued_up)
            if (
                all_limit and dl + up >= all_limit and (not up_limit or up >= up_limit)
            ) or (up_limit and up >= up_limit):
                added_to_queue = True
                LOGGER.info(f"Added to Queue/Upload: {self.name}")
                event = Event()
                queued_up[self.mid] = event
        if added_to_queue:
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
            tg_upload_status = TelegramStatus(self, tg, size, gid, "up")
            async with task_dict_lock:
                task_dict[self.mid] = tg_upload_status
            await update_status_message(self.message.chat.id)
            await tg.upload(o_files, m_size, size)
        elif is_gdrive_id(self.upDest):
            size = await get_path_size(up_path)
            LOGGER.info(f"Upload Name: {self.name}")
            drive = gdUpload(self, up_path)
            upload_status = GdriveStatus(self, drive, size, gid, "up")
            async with task_dict_lock:
                task_dict[self.mid] = upload_status
            await update_status_message(self.message.chat.id)
            await sync_to_async(drive.upload, size)
        else:
            size = await get_path_size(up_path)
            LOGGER.info(f"Upload Name: {self.name}")
            RCTransfer = RcloneTransferHelper(self)
            async with task_dict_lock:
                task_dict[self.mid] = RcloneStatus(self, RCTransfer, gid, "up")
            await update_status_message(self.message.chat.id)
            await RCTransfer.upload(up_path, size)

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
            if self.sameDir and self.mid in self.sameDir["tasks"]:
                self.sameDir["tasks"].remove(self.mid)
                self.sameDir["total"] -= 1
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
