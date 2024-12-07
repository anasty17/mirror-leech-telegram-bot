from aiofiles.os import path as aiopath, listdir, makedirs, remove
from aioshutil import move
from asyncio import sleep, gather
from html import escape
from requests import utils as rutils

from bot import (
    intervals,
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
    same_directory_lock,
)
from ..common import TaskConfig
from ..ext_utils.bot_utils import sync_to_async
from ..ext_utils.db_handler import database
from ..ext_utils.files_utils import (
    get_path_size,
    clean_download,
    clean_target,
    join_files,
)
from ..ext_utils.links_utils import is_gdrive_id
from ..ext_utils.status_utils import get_readable_file_size
from ..ext_utils.task_manager import start_from_queued, check_running_tasks
from ..mirror_leech_utils.gdrive_utils.upload import GoogleDriveUpload
from ..mirror_leech_utils.rclone_utils.transfer import RcloneTransferHelper
from ..mirror_leech_utils.status_utils.gdrive_status import GoogleDriveStatus
from ..mirror_leech_utils.status_utils.queue_status import QueueStatus
from ..mirror_leech_utils.status_utils.rclone_status import RcloneStatus
from ..mirror_leech_utils.status_utils.telegram_status import TelegramStatus
from ..mirror_leech_utils.telegram_uploader import TelegramUploader
from ..telegram_helper.button_build import ButtonMaker
from ..telegram_helper.message_utils import (
    send_message,
    delete_status,
    update_status_message,
)


class TaskListener(TaskConfig):
    def __init__(self):
        super().__init__()

    async def clean(self):
        try:
            if st := intervals["status"]:
                for intvl in list(st.values()):
                    intvl.cancel()
            intervals["status"].clear()
            await gather(sync_to_async(aria2.purge), delete_status())
        except:
            pass

    async def remove_from_same_dir(self):
        async with task_dict_lock:
            if (
                self.folder_name
                and self.same_dir
                and self.mid in self.same_dir[self.folder_name]["tasks"]
            ):
                self.same_dir[self.folder_name]["tasks"].remove(self.mid)
                self.same_dir[self.folder_name]["total"] -= 1

    async def on_download_start(self):
        if (
            self.is_super_chat
            and config_dict["INCOMPLETE_TASK_NOTIFIER"]
            and DATABASE_URL
        ):
            await database.add_incomplete_task(
                self.message.chat.id, self.message.link, self.tag
            )

    async def on_download_complete(self):
        await sleep(2)
        multi_links = False
        if (
            self.folder_name
            and self.same_dir
            and self.mid in self.same_dir[self.folder_name]["tasks"]
        ):
            async with same_directory_lock:
                while True:
                    async with task_dict_lock:
                        if self.mid not in self.same_dir[self.folder_name]["tasks"]:
                            return
                        if self.mid in self.same_dir[self.folder_name]["tasks"] and (
                            self.same_dir[self.folder_name]["total"] <= 1
                            or len(self.same_dir[self.folder_name]["tasks"]) > 1
                        ):
                            if self.same_dir[self.folder_name]["total"] > 1:
                                self.same_dir[self.folder_name]["tasks"].remove(
                                    self.mid
                                )
                                self.same_dir[self.folder_name]["total"] -= 1
                                spath = f"{self.dir}{self.folder_name}"
                                des_id = list(self.same_dir[self.folder_name]["tasks"])[
                                    0
                                ]
                                des_path = f"{DOWNLOAD_DIR}{des_id}{self.folder_name}"
                                await makedirs(des_path, exist_ok=True)
                                LOGGER.info(f"Moving files from {self.mid} to {des_id}")
                                for item in await listdir(spath):
                                    if item.endswith((".aria2", ".!qB")):
                                        continue
                                    item_path = f"{self.dir}{self.folder_name}/{item}"
                                    if item in await listdir(des_path):
                                        await move(
                                            item_path, f"{des_path}/{self.mid}-{item}"
                                        )
                                    else:
                                        await move(item_path, f"{des_path}/{item}")
                                multi_links = True
                            break
                    await sleep(1)
        async with task_dict_lock:
            download = task_dict[self.mid]
            self.name = download.name()
            gid = download.gid()
        LOGGER.info(f"Download completed: {self.name}")

        if not (self.is_torrent or self.is_qbit):
            self.seed = False

        unwanted_files = []
        unwanted_files_size = []
        files_to_delete = []

        if multi_links:
            await self.on_upload_error(
                f"{self.name} Downloaded!\n\nWaiting for other tasks to finish..."
            )
            return

        if self.folder_name:
            self.name = self.folder_name.split("/")[-1]

        if not await aiopath.exists(f"{self.dir}/{self.name}"):
            try:
                files = await listdir(self.dir)
                self.name = files[-1]
                if self.name == "yt-dlp-thumb":
                    self.name = files[0]
            except Exception as e:
                await self.on_upload_error(str(e))
                return

        up_path = f"{self.dir}/{self.name}"
        self.size = await get_path_size(up_path)
        if not config_dict["QUEUE_ALL"]:
            async with queue_dict_lock:
                if self.mid in non_queued_dl:
                    non_queued_dl.remove(self.mid)
            await start_from_queued()

        if self.join and await aiopath.isdir(up_path):
            await join_files(up_path)

        if self.extract and not self.is_nzb:
            up_path = await self.proceed_extract(up_path, gid)
            if self.is_cancelled:
                return
            up_dir, self.name = up_path.rsplit("/", 1)
            self.size = await get_path_size(up_dir)

        if self.ffmpeg_cmds:
            up_path = await self.proceed_ffmpeg(
                up_path,
                gid,
            )
            if self.is_cancelled:
                return
            up_dir, self.name = up_path.rsplit("/", 1)
            self.size = await get_path_size(up_dir)

        if self.name_sub:
            up_path = await self.substitute(up_path)
            if self.is_cancelled:
                return
            self.name = up_path.rsplit("/", 1)[1]

        if self.screen_shots:
            up_path = await self.generate_screenshots(up_path)
            if self.is_cancelled:
                return
            up_dir, self.name = up_path.rsplit("/", 1)
            self.size = await get_path_size(up_dir)

        if self.convert_audio or self.convert_video:
            up_path = await self.convert_media(
                up_path,
                gid,
                unwanted_files,
                unwanted_files_size,
                files_to_delete,
            )
            if self.is_cancelled:
                return
            up_dir, self.name = up_path.rsplit("/", 1)
            self.size = await get_path_size(up_dir)

        if self.sample_video:
            up_path = await self.generate_sample_video(
                up_path, gid, unwanted_files, files_to_delete
            )
            if self.is_cancelled:
                return
            up_dir, self.name = up_path.rsplit("/", 1)
            self.size = await get_path_size(up_dir)

        if self.compress:
            up_path = await self.proceed_compress(
                up_path, gid, unwanted_files, files_to_delete
            )
            if self.is_cancelled:
                return

        up_dir, self.name = up_path.rsplit("/", 1)
        self.size = await get_path_size(up_dir)

        if self.is_leech and not self.compress:
            await self.proceed_split(up_dir, unwanted_files_size, unwanted_files, gid)
            if self.is_cancelled:
                return

        add_to_queue, event = await check_running_tasks(self, "up")
        await start_from_queued()
        if add_to_queue:
            LOGGER.info(f"Added to Queue/Upload: {self.name}")
            async with task_dict_lock:
                task_dict[self.mid] = QueueStatus(self, gid, "Up")
            await event.wait()
            if self.is_cancelled:
                return
            LOGGER.info(f"Start from Queued/Upload: {self.name}")

        self.size = await get_path_size(up_dir)
        for s in unwanted_files_size:
            self.size -= s

        if self.is_leech:
            LOGGER.info(f"Leech Name: {self.name}")
            tg = TelegramUploader(self, up_dir)
            async with task_dict_lock:
                task_dict[self.mid] = TelegramStatus(self, tg, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                tg.upload(unwanted_files, files_to_delete),
            )
        elif is_gdrive_id(self.up_dest):
            LOGGER.info(f"Gdrive Upload Name: {self.name}")
            drive = GoogleDriveUpload(self, up_path)
            async with task_dict_lock:
                task_dict[self.mid] = GoogleDriveStatus(self, drive, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                sync_to_async(drive.upload, unwanted_files, files_to_delete),
            )
        else:
            LOGGER.info(f"Rclone Upload Name: {self.name}")
            RCTransfer = RcloneTransferHelper(self)
            async with task_dict_lock:
                task_dict[self.mid] = RcloneStatus(self, RCTransfer, gid, "up")
            await gather(
                update_status_message(self.message.chat.id),
                RCTransfer.upload(up_path, unwanted_files, files_to_delete),
            )

    async def on_upload_complete(
        self, link, files, folders, mime_type, rclone_path="", dir_id=""
    ):
        if (
            self.is_super_chat
            and config_dict["INCOMPLETE_TASK_NOTIFIER"]
            and DATABASE_URL
        ):
            await database.rm_complete_task(self.message.link)
        msg = f"<b>Name: </b><code>{escape(self.name)}</code>\n\n<b>Size: </b>{get_readable_file_size(self.size)}"
        LOGGER.info(f"Task Done: {self.name}")
        if self.is_leech:
            msg += f"\n<b>Total Files: </b>{folders}"
            if mime_type != 0:
                msg += f"\n<b>Corrupted Files: </b>{mime_type}"
            msg += f"\n<b>cc: </b>{self.tag}\n\n"
            if not files:
                await send_message(self.message, msg)
            else:
                fmsg = ""
                for index, (link, name) in enumerate(files.items(), start=1):
                    fmsg += f"{index}. <a href='{link}'>{name}</a>\n"
                    if len(fmsg.encode() + msg.encode()) > 4000:
                        await send_message(self.message, msg + fmsg)
                        await sleep(1)
                        fmsg = ""
                if fmsg != "":
                    await send_message(self.message, msg + fmsg)
        else:
            msg += f"\n\n<b>Type: </b>{mime_type}"
            if mime_type == "Folder":
                msg += f"\n<b>SubFolders: </b>{folders}"
                msg += f"\n<b>Files: </b>{files}"
            if (
                link
                or rclone_path
                and config_dict["RCLONE_SERVE_URL"]
                and not self.private_link
            ):
                buttons = ButtonMaker()
                if link:
                    buttons.url_button("☁️ Cloud Link", link)
                else:
                    msg += f"\n\nPath: <code>{rclone_path}</code>"
                if (
                    rclone_path
                    and (RCLONE_SERVE_URL := config_dict["RCLONE_SERVE_URL"])
                    and not self.private_link
                ):
                    remote, path = rclone_path.split(":", 1)
                    url_path = rutils.quote(f"{path}")
                    share_url = f"{RCLONE_SERVE_URL}/{remote}/{url_path}"
                    if mime_type == "Folder":
                        share_url += "/"
                    buttons.url_button("🔗 Rclone Link", share_url)
                if not rclone_path and dir_id:
                    INDEX_URL = ""
                    if self.private_link:
                        INDEX_URL = self.user_dict.get("index_url", "") or ""
                    elif config_dict["INDEX_URL"]:
                        INDEX_URL = config_dict["INDEX_URL"]
                    if INDEX_URL:
                        share_url = f"{INDEX_URL}findpath?id={dir_id}"
                        buttons.url_button("⚡ Index Link", share_url)
                        if mime_type.startswith(("image", "video", "audio")):
                            share_urls = f"{INDEX_URL}findpath?id={dir_id}&view=true"
                            buttons.url_button("🌐 View Link", share_urls)
                button = buttons.build_menu(2)
            else:
                msg += f"\n\nPath: <code>{rclone_path}</code>"
                button = None
            msg += f"\n\n<b>cc: </b>{self.tag}"
            await send_message(self.message, msg, button)
        if self.seed:
            if self.new_dir:
                await clean_target(self.new_dir)
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

    async def on_download_error(self, error, button=None):
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        await self.remove_from_same_dir()
        msg = f"{self.tag} Download: {escape(str(error))}"
        await send_message(self.message, msg, button)
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        if (
            self.is_super_chat
            and config_dict["INCOMPLETE_TASK_NOTIFIER"]
            and DATABASE_URL
        ):
            await database.rm_complete_task(self.message.link)

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
        if self.new_dir:
            await clean_download(self.new_dir)
        if self.thumb and await aiopath.exists(self.thumb):
            await remove(self.thumb)

    async def on_upload_error(self, error):
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        await send_message(self.message, f"{self.tag} {escape(str(error))}")
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.message.chat.id)

        if (
            self.is_super_chat
            and config_dict["INCOMPLETE_TASK_NOTIFIER"]
            and DATABASE_URL
        ):
            await database.rm_complete_task(self.message.link)

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
        if self.new_dir:
            await clean_download(self.new_dir)
        if self.thumb and await aiopath.exists(self.thumb):
            await remove(self.thumb)
