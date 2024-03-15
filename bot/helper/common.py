from aiofiles.os import path as aiopath, remove, makedirs
from asyncio import sleep, create_subprocess_exec, gather
from asyncio.subprocess import PIPE
from os import walk, path as ospath
from secrets import token_urlsafe
from aioshutil import move, copy2
from pyrogram.enums import ChatAction
from re import sub, I

from bot import (
    DOWNLOAD_DIR,
    MAX_SPLIT_SIZE,
    config_dict,
    user_data,
    IS_PREMIUM_USER,
    user,
    multi_tags,
    LOGGER,
    task_dict_lock,
    task_dict,
    GLOBAL_EXTENSION_FILTER,
    cpu_eater_lock,
    subprocess_lock,
)
from bot.helper.ext_utils.bot_utils import new_task, sync_to_async, getSizeBytes
from bot.helper.ext_utils.bulk_links import extractBulkLinks
from bot.helper.ext_utils.exceptions import NotSupportedExtractionArchive
from bot.helper.ext_utils.files_utils import (
    get_base_name,
    is_first_archive_split,
    is_archive,
    is_archive_split,
    get_path_size,
    clean_target,
)
from bot.helper.ext_utils.links_utils import (
    is_gdrive_id,
    is_rclone_path,
    is_gdrive_link,
    is_telegram_link,
)
from bot.helper.ext_utils.media_utils import (
    createThumb,
    createSampleVideo,
    take_ss,
)
from bot.helper.ext_utils.media_utils import (
    split_file,
    get_document_type,
    convert_video,
    convert_audio,
)
from bot.helper.mirror_leech_utils.gdrive_utils.list import gdriveList
from bot.helper.mirror_leech_utils.rclone_utils.list import RcloneList
from bot.helper.mirror_leech_utils.status_utils.extract_status import ExtractStatus
from bot.helper.mirror_leech_utils.status_utils.sample_video_status import (
    SampleVideoStatus,
)
from bot.helper.mirror_leech_utils.status_utils.media_convert_status import (
    MediaConvertStatus,
)
from bot.helper.mirror_leech_utils.status_utils.split_status import SplitStatus
from bot.helper.mirror_leech_utils.status_utils.zip_status import ZipStatus
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    sendStatusMessage,
    get_tg_link_message,
)


class TaskConfig:
    def __init__(self):
        self.mid = self.message.id
        self.user = self.message.from_user or self.message.sender_chat
        self.userId = self.user.id
        self.userDict = user_data.get(self.userId, {})
        self.dir = f"{DOWNLOAD_DIR}{self.mid}"
        self.link = ""
        self.upDest = ""
        self.rcFlags = ""
        self.tag = ""
        self.name = ""
        self.newDir = ""
        self.nameSub = ""
        self.splitSize = 0
        self.maxSplitSize = 0
        self.multi = 0
        self.size = 0
        self.isLeech = False
        self.isQbit = False
        self.isJd = False
        self.isClone = False
        self.isYtDlp = False
        self.equalSplits = False
        self.userTransmission = False
        self.extract = False
        self.compress = False
        self.select = False
        self.seed = False
        self.compress = False
        self.extract = False
        self.join = False
        self.privateLink = False
        self.stopDuplicate = False
        self.sampleVideo = False
        self.convertAudio = False
        self.convertVideo = False
        self.screenShots = False
        self.asDoc = False
        self.isCancelled = False
        self.forceRun = False
        self.forceDownload = False
        self.forceUpload = False
        self.isTorrent = False
        self.suproc = None
        self.thumb = None
        self.extensionFilter = []
        self.isSuperChat = self.message.chat.type.name in ["SUPERGROUP", "CHANNEL"]

    def getTokenPath(self, dest):
        if dest.startswith("mtp:"):
            return f"tokens/{self.userId}.pickle"
        elif (
            dest.startswith("sa:")
            or config_dict["USE_SERVICE_ACCOUNTS"]
            and not dest.startswith("tp:")
        ):
            return "accounts"
        else:
            return "token.pickle"

    def getConfigPath(self, dest):
        return (
            f"rclone/{self.userId}.conf" if dest.startswith("mrcc:") else "rclone.conf"
        )

    async def isTokenExists(self, path, status):
        if is_rclone_path(path):
            config_path = self.getConfigPath(path)
            if config_path != "rclone.conf" and status == "up":
                self.privateLink = True
            if not await aiopath.exists(config_path):
                raise ValueError(f"Rclone Config: {config_path} not Exists!")
        elif (
            status == "dl"
            and is_gdrive_link(path)
            or status == "up"
            and is_gdrive_id(path)
        ):
            token_path = self.getTokenPath(path)
            if token_path.startswith("tokens/") and status == "up":
                self.privateLink = True
            if not await aiopath.exists(token_path):
                raise ValueError(f"NO TOKEN! {token_path} not Exists!")

    async def beforeStart(self):
        self.nameSub = (
            self.nameSub
            or self.userDict.get("name_sub", False) or config_dict["NAME_SUBSTITUTE"]
            if "name_sub" not in self.userDict
            else ""
        )
        if self.nameSub:
            self.nameSub = [x.split(" : ") for x in self.nameSub.split("|")]
            self.seed = False
        self.extensionFilter = (
            self.userDict.get("excluded_extensions") or GLOBAL_EXTENSION_FILTER
            if "excluded_extensions" not in self.userDict
            else ["aria2", "!qB"]
        )
        if self.link not in ["rcl", "gdl"]:
            if not self.isYtDlp and not self.isJd:
                await self.isTokenExists(self.link, "dl")
        elif self.link == "rcl":
            if not self.isYtDlp and not self.isJd:
                self.link = await RcloneList(self).get_rclone_path("rcd")
                if not is_rclone_path(self.link):
                    raise ValueError(self.link)
        elif self.link == "gdl":
            if not self.isYtDlp and not self.isJd:
                self.link = await gdriveList(self).get_target_id("gdd")
                if not is_gdrive_id(self.link):
                    raise ValueError(self.link)

        self.userTransmission = IS_PREMIUM_USER and (
            self.userDict.get("user_transmission")
            or config_dict["USER_TRANSMISSION"]
            and "user_transmission" not in self.userDict
        )

        if (
            "upload_paths" in self.userDict
            and self.upDest
            and self.upDest in self.userDict["upload_paths"]
        ):
            self.upDest = self.userDict["upload_paths"][self.upDest]

        if not self.isLeech:
            self.stopDuplicate = (
                self.userDict.get("stop_duplicate")
                or "stop_duplicate" not in self.userDict
                and config_dict["STOP_DUPLICATE"]
            )
            default_upload = (
                self.userDict.get("default_upload", "") or config_dict["DEFAULT_UPLOAD"]
            )
            if (not self.upDest and default_upload == "rc") or self.upDest == "rc":
                self.upDest = (
                    self.userDict.get("rclone_path") or config_dict["RCLONE_PATH"]
                )
            elif (not self.upDest and default_upload == "gd") or self.upDest == "gd":
                self.upDest = self.userDict.get("gdrive_id") or config_dict["GDRIVE_ID"]
            if not self.upDest:
                raise ValueError("No Upload Destination!")
            if not is_gdrive_id(self.upDest) and not is_rclone_path(self.upDest):
                raise ValueError("Wrong Upload Destination!")
            if self.upDest not in ["rcl", "gdl"]:
                await self.isTokenExists(self.upDest, "up")

            if self.upDest == "rcl":
                if self.isClone:
                    if not is_rclone_path(self.link):
                        raise ValueError(
                            "You can't clone from different types of tools"
                        )
                    config_path = self.getConfigPath(self.link)
                else:
                    config_path = None
                self.upDest = await RcloneList(self).get_rclone_path("rcu", config_path)
                if not is_rclone_path(self.upDest):
                    raise ValueError(self.upDest)
            elif self.upDest == "gdl":
                if self.isClone:
                    if not is_gdrive_link(self.link):
                        raise ValueError(
                            "You can't clone from different types of tools"
                        )
                    token_path = self.getTokenPath(self.link)
                else:
                    token_path = None
                self.upDest = await gdriveList(self).get_target_id("gdu", token_path)
                if not is_gdrive_id(self.upDest):
                    raise ValueError(self.upDest)
            elif self.isClone:
                if is_gdrive_link(self.link) and self.getTokenPath(
                    self.link
                ) != self.getTokenPath(self.upDest):
                    raise ValueError("You must use the same token to clone!")
                elif is_rclone_path(self.link) and self.getConfigPath(
                    self.link
                ) != self.getConfigPath(self.upDest):
                    raise ValueError("You must use the same config to clone!")
        else:
            self.upDest = (
                self.upDest
                or self.userDict.get("leech_dest")
                or config_dict["LEECH_DUMP_CHAT"]
            )
            if self.upDest:
                if not isinstance(self.upDest, int):
                    if self.upDest.startswith("b:"):
                        self.upDest = self.upDest.replace("b:", "", 1)
                        self.userTransmission = False
                    elif self.upDest.startswith("u:"):
                        self.upDest = self.upDest.replace("u:", "", 1)
                        self.userTransmission = IS_PREMIUM_USER
                    if self.upDest.isdigit() or self.upDest.startswith("-"):
                        self.upDest = int(self.upDest)
                    elif self.upDest.lower() == "pm":
                        self.upDest = self.userId

                if self.userTransmission:
                    chat = await user.get_chat(self.upDest)
                    uploader_id = user.me.id
                else:
                    chat = await self.client.get_chat(self.upDest)
                    uploader_id = self.client.me.id

                if chat.type.name in ["SUPERGROUP", "CHANNEL"]:
                    member = await chat.get_member(uploader_id)
                    if (
                        not member.privileges.can_manage_chat
                        or not member.privileges.can_delete_messages
                    ):
                        raise ValueError(
                            "You don't have enough privileges in this chat!"
                        )
                elif self.userTransmission:
                    raise ValueError(
                        "Custom Leech Destination only allowed for super-group or channel when UserTransmission enalbed!\nDisable UserTransmission so bot can send files to user!"
                    )
                else:
                    try:
                        await self.client.send_chat_action(
                            self.upDest, ChatAction.TYPING
                        )
                    except:
                        raise ValueError("Start the bot and try again!")
            elif self.userTransmission and not self.isSuperChat:
                self.userTransmission = False
            if self.splitSize:
                if self.splitSize.isdigit():
                    self.splitSize = int(self.splitSize)
                else:
                    self.splitSize = getSizeBytes(self.splitSize)
            self.splitSize = (
                self.splitSize
                or self.userDict.get("split_size")
                or config_dict["LEECH_SPLIT_SIZE"]
            )
            self.equalSplits = (
                self.userDict.get("equal_splits")
                or config_dict["EQUAL_SPLITS"]
                and "equal_splits" not in self.userDict
            )
            self.maxSplitSize = MAX_SPLIT_SIZE if self.userTransmission else 2097152000
            self.splitSize = min(self.splitSize, self.maxSplitSize)

            self.asDoc = (
                self.userDict.get("as_doc", False)
                or config_dict["AS_DOCUMENT"]
                and "as_doc" not in self.userDict
            )

            if is_telegram_link(self.thumb):
                msg = (await get_tg_link_message(self.thumb))[0]
                self.thumb = await createThumb(msg) if msg.photo or msg.document else ""

    async def getTag(self, text: list):
        if len(text) > 1 and text[1].startswith("Tag: "):
            self.tag, id_ = text[1].split("Tag: ")[1].split()
            self.user = self.message.from_user = await self.client.get_users(id_)
            self.userId = self.user.id
            self.userDict = user_data.get(self.userId, {})
            try:
                await self.message.unpin()
            except:
                pass
        if username := self.user.username:
            self.tag = f"@{username}"
        else:
            self.tag = self.message.from_user.mention

    @new_task
    async def run_multi(self, input_list, folder_name, obj):
        await sleep(7)
        if not self.multiTag and self.multi > 1:
            self.multiTag = token_urlsafe(3)
            multi_tags.add(self.multiTag)
        elif self.multi <= 1:
            multi_tags.discard(self.multiTag)
            return
        if self.multiTag and self.multiTag not in multi_tags:
            await sendMessage(
                self.message, f"{self.tag} Multi Task has been cancelled!"
            )
            await sendStatusMessage(self.message)
            return
        if len(self.bulk) != 0:
            msg = input_list[:1]
            msg.append(f"{self.bulk[0]} -i {self.multi - 1} {self.options}")
            msgts = " ".join(msg)
            if self.multi > 2:
                msgts += f"\nCancel Multi: <code>/{BotCommands.CancelTaskCommand[1]} {self.multiTag}</code>"
            nextmsg = await sendMessage(self.message, msgts)
        else:
            msg = [s.strip() for s in input_list]
            index = msg.index("-i")
            msg[index + 1] = f"{self.multi - 1}"
            nextmsg = await self.client.get_messages(
                chat_id=self.message.chat.id,
                message_ids=self.message.reply_to_message_id + 1,
            )
            msgts = " ".join(msg)
            if self.multi > 2:
                msgts += f"\nCancel Multi: <code>/{BotCommands.CancelTaskCommand[1]} {self.multiTag}</code>"
            nextmsg = await sendMessage(nextmsg, msgts)
        nextmsg = await self.client.get_messages(
            chat_id=self.message.chat.id, message_ids=nextmsg.id
        )
        if folder_name:
            self.sameDir["tasks"].add(nextmsg.id)
        if self.message.from_user:
            nextmsg.from_user = self.user
        else:
            nextmsg.sender_chat = self.user
        obj(
            self.client,
            nextmsg,
            self.isQbit,
            self.isLeech,
            self.isJd,
            self.sameDir,
            self.bulk,
            self.multiTag,
            self.options,
        ).newEvent()

    async def initBulk(self, input_list, bulk_start, bulk_end, obj):
        try:
            self.bulk = await extractBulkLinks(self.message, bulk_start, bulk_end)
            if len(self.bulk) == 0:
                raise ValueError("Bulk Empty!")
            b_msg = input_list[:1]
            self.options = input_list[1:]
            index = self.options.index("-b")
            del self.options[index]
            if bulk_start or bulk_end:
                del self.options[index + 1]
            self.options = " ".join(self.options)
            b_msg.append(f"{self.bulk[0]} -i {len(self.bulk)} {self.options}")
            nextmsg = await sendMessage(self.message, " ".join(b_msg))
            nextmsg = await self.client.get_messages(
                chat_id=self.message.chat.id, message_ids=nextmsg.id
            )
            if self.message.from_user:
                nextmsg.from_user = self.user
            else:
                nextmsg.sender_chat = self.user
            obj(
                self.client,
                nextmsg,
                self.isQbit,
                self.isLeech,
                self.isJd,
                self.sameDir,
                self.bulk,
                self.multiTag,
                self.options,
            ).newEvent()
        except:
            await sendMessage(
                self.message,
                "Reply to text file or to telegram message that have links seperated by new line!",
            )

    async def proceedExtract(self, dl_path, gid):
        pswd = self.extract if isinstance(self.extract, str) else ""
        try:
            LOGGER.info(f"Extracting: {self.name}")
            async with task_dict_lock:
                task_dict[self.mid] = ExtractStatus(self, gid)
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
                            if self.isCancelled:
                                return ""
                            async with subprocess_lock:
                                self.suproc = await create_subprocess_exec(
                                    *cmd, stderr=PIPE
                                )
                            _, stderr = await self.suproc.communicate()
                            if self.isCancelled:
                                return ""
                            code = self.suproc.returncode
                            if code != 0:
                                try:
                                    stderr = stderr.decode().strip()
                                except:
                                    stderr = "Unable to decode the error!"
                                LOGGER.error(
                                    f"{stderr}. Unable to extract archive splits!. Path: {f_path}"
                                )
                    if (
                        not self.seed
                        and self.suproc is not None
                        and self.suproc.returncode == 0
                    ):
                        for file_ in files:
                            if is_archive_split(file_) or is_archive(file_):
                                del_path = ospath.join(dirpath, file_)
                                try:
                                    await remove(del_path)
                                except:
                                    self.isCancelled = True
                return up_path
            else:
                up_path = get_base_name(dl_path)
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
                if self.isCancelled:
                    return ""
                async with subprocess_lock:
                    self.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
                _, stderr = await self.suproc.communicate()
                if self.isCancelled:
                    return ""
                code = self.suproc.returncode
                if code == -9:
                    self.isCancelled = True
                    return ""
                elif code == 0:
                    LOGGER.info(f"Extracted Path: {up_path}")
                    if not self.seed:
                        try:
                            await remove(dl_path)
                        except:
                            self.isCancelled = True
                    return up_path
                else:
                    try:
                        stderr = stderr.decode().strip()
                    except:
                        stderr = "Unable to decode the error!"
                    LOGGER.error(
                        f"{stderr}. Unable to extract archive! Uploading anyway. Path: {dl_path}"
                    )
                    self.newDir = ""
                    return dl_path
        except NotSupportedExtractionArchive:
            LOGGER.info(
                f"Not any valid archive, uploading file as it is. Path: {dl_path}"
            )
            self.newDir = ""
            return dl_path

    async def proceedCompress(self, dl_path, gid, o_files, ft_delete):
        pswd = self.compress if isinstance(self.compress, str) else ""
        if self.seed and not self.newDir:
            self.newDir = f"{self.dir}10000"
            up_path = f"{self.newDir}/{self.name}.zip"
            delete = False
        else:
            up_path = f"{dl_path}.zip"
            delete = True
        async with task_dict_lock:
            task_dict[self.mid] = ZipStatus(self, gid)
        size = await get_path_size(dl_path)
        if self.equalSplits:
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
        if await aiopath.isdir(dl_path):
            cmd.extend(f"-xr!*.{ext}" for ext in self.extensionFilter)
            if o_files:
                for f in o_files:
                    if self.newDir and self.newDir in f:
                        fte = f.replace(f"{self.newDir}/", "")
                    else:
                        fte = f.replace(f"{self.dir}/", "")
                    cmd.append(f"-xr!{fte}")
        if self.isLeech and int(size) > self.splitSize:
            if not pswd:
                del cmd[4]
            LOGGER.info(f"Zip: orig_path: {dl_path}, zip_path: {up_path}.0*")
        else:
            del cmd[1]
            if not pswd:
                del cmd[3]
            LOGGER.info(f"Zip: orig_path: {dl_path}, zip_path: {up_path}")
        if self.isCancelled:
            return ""
        async with subprocess_lock:
            self.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
        _, stderr = await self.suproc.communicate()
        if self.isCancelled:
            return ""
        code = self.suproc.returncode
        if code == -9:
            self.isCancelled = True
            return ""
        elif code == 0:
            if not self.seed or delete:
                await clean_target(dl_path)
            for f in ft_delete:
                if await aiopath.exists(f):
                    try:
                        await remove(f)
                    except:
                        pass
            ft_delete.clear()
            return up_path
        else:
            await clean_target(self.newDir)
            if not delete:
                self.newDir = ""
            try:
                stderr = stderr.decode().strip()
            except:
                stderr = "Unable to decode the error!"
            LOGGER.error(f"{stderr}. Unable to zip this path: {dl_path}")
            return dl_path

    async def proceedSplit(self, up_dir, m_size, o_files, gid):
        checked = False
        for dirpath, _, files in await sync_to_async(walk, up_dir, topdown=False):
            for file_ in files:
                f_path = ospath.join(dirpath, file_)
                if f_path in o_files:
                    continue
                f_size = await aiopath.getsize(f_path)
                if f_size > self.splitSize:
                    if not checked:
                        checked = True
                        async with task_dict_lock:
                            task_dict[self.mid] = SplitStatus(self, gid)
                        LOGGER.info(f"Splitting: {self.name}")
                    res = await split_file(
                        f_path, f_size, dirpath, file_, self.splitSize, self
                    )
                    if self.isCancelled:
                        return
                    if not res:
                        if f_size >= self.maxSplitSize:
                            if self.seed and not self.newDir:
                                m_size.append(f_size)
                                o_files.append(f_path)
                            else:
                                try:
                                    await remove(f_path)
                                except:
                                    return
                        continue
                    elif not self.seed or self.newDir:
                        try:
                            await remove(f_path)
                        except:
                            return
                    else:
                        m_size.append(f_size)
                        o_files.append(f_path)

    async def generateSampleVideo(self, dl_path, gid, unwanted_files, ft_delete):
        data = self.sampleVideo.split(":") if isinstance(self.sampleVideo, str) else ""
        if data:
            sample_duration = int(data[0]) if data[0] else 60
            part_duration = int(data[1]) if len(data) > 1 else 4
        else:
            sample_duration = 60
            part_duration = 4

        async with task_dict_lock:
            task_dict[self.mid] = SampleVideoStatus(self, gid)

        checked = False
        if await aiopath.isfile(dl_path):
            if (await get_document_type(dl_path))[0]:
                checked = True
                await cpu_eater_lock.acquire()
                LOGGER.info(f"Creating Sample video: {self.name}")
                res = await createSampleVideo(
                    self, dl_path, sample_duration, part_duration
                )
                cpu_eater_lock.release()
                if res:
                    newfolder = ospath.splitext(dl_path)[0]
                    name = dl_path.rsplit("/", 1)[1]
                    if self.seed and not self.newDir:
                        if self.isLeech and not self.compress:
                            return self.dir
                        self.newDir = f"{self.dir}10000"
                        newfolder = newfolder.replace(self.dir, self.newDir)
                        await makedirs(newfolder, exist_ok=True)
                        await gather(
                            copy2(dl_path, f"{newfolder}/{name}"),
                            move(res, f"{newfolder}/SAMPLE.{name}"),
                        )
                    else:
                        await makedirs(newfolder, exist_ok=True)
                        await gather(
                            move(dl_path, f"{newfolder}/{name}"),
                            move(res, f"{newfolder}/SAMPLE.{name}"),
                        )
                    return newfolder
        else:
            for dirpath, _, files in await sync_to_async(walk, dl_path, topdown=False):
                for file_ in files:
                    f_path = ospath.join(dirpath, file_)
                    if f_path in unwanted_files:
                        continue
                    if (await get_document_type(f_path))[0]:
                        if not checked:
                            checked = True
                            await cpu_eater_lock.acquire()
                            LOGGER.info(f"Creating Sample videos: {self.name}")
                        if self.isCancelled:
                            cpu_eater_lock.release()
                            return ""
                        res = await createSampleVideo(
                            self, f_path, sample_duration, part_duration
                        )
                        if res:
                            ft_delete.append(res)
            if checked:
                cpu_eater_lock.release()

        return dl_path

    async def convertMedia(self, dl_path, gid, o_files, m_size, ft_delete):
        fvext = []
        if self.convertVideo:
            vdata = self.convertVideo.split()
            vext = vdata[0]
            if len(vdata) > 2:
                if "+" in vdata[1].split():
                    vstatus = "+"
                elif "-" in vdata[1].split():
                    vstatus = "-"
                else:
                    vstatus = ""
                fvext.extend(f".{ext}" for ext in vdata[2:])
            else:
                vstatus = ""
        else:
            vext = ""
            vstatus = ""

        faext = []
        if self.convertAudio:
            adata = self.convertAudio.split()
            aext = adata[0]
            if len(adata) > 2:
                if "+" in adata[1].split():
                    astatus = "+"
                elif "-" in adata[1].split():
                    astatus = "-"
                else:
                    astatus = ""
                faext.extend(f".{ext}" for ext in adata[2:])
            else:
                astatus = ""
        else:
            aext = ""
            astatus = ""

        checked = False

        async def proceedConvert(m_path):
            nonlocal checked
            is_video, is_audio, _ = await get_document_type(m_path)
            if (
                is_video
                and vext
                and not m_path.endswith(f".{vext}")
                and (
                    vstatus == "+"
                    and m_path.endswith(tuple(fvext))
                    or vstatus == "-"
                    and not m_path.endswith(tuple(fvext))
                    or not vstatus
                )
            ):
                if not checked:
                    checked = True
                    await cpu_eater_lock.acquire()
                    LOGGER.info(f"Converting: {self.name}")
                else:
                    LOGGER.info(f"Converting: {m_path}")
                res = await convert_video(self, m_path, vext)
                return "" if self.isCancelled else res
            elif (
                is_audio
                and aext
                and not is_video
                and not m_path.endswith(f".{aext}")
                and (
                    astatus == "+"
                    and m_path.endswith(tuple(faext))
                    or astatus == "-"
                    and not m_path.endswith(tuple(faext))
                    or not astatus
                )
            ):
                if not checked:
                    checked = True
                    await cpu_eater_lock.acquire()
                    LOGGER.info(f"Converting: {self.name}")
                else:
                    LOGGER.info(f"Converting: {m_path}")
                res = await convert_audio(self, m_path, aext)
                return "" if self.isCancelled else res
            else:
                return ""

        async with task_dict_lock:
            task_dict[self.mid] = MediaConvertStatus(self, gid)

        if await aiopath.isfile(dl_path):
            output_file = await proceedConvert(dl_path)
            if checked:
                cpu_eater_lock.release()
            if output_file:
                if self.seed:
                    self.newDir = f"{self.dir}10000"
                    new_output_file = output_file.replace(self.dir, self.newDir)
                    await makedirs(self.newDir, exist_ok=True)
                    await move(output_file, new_output_file)
                    return new_output_file
                else:
                    try:
                        await remove(dl_path)
                    except:
                        pass
                    return output_file
        else:
            for dirpath, _, files in await sync_to_async(walk, dl_path, topdown=False):
                for file_ in files:
                    if self.isCancelled:
                        cpu_eater_lock.release()
                        return ""
                    f_path = ospath.join(dirpath, file_)
                    res = await proceedConvert(f_path)
                    if res:
                        if self.seed and not self.newDir:
                            o_files.append(f_path)
                            fsize = await aiopath.getsize(f_path)
                            m_size.append(fsize)
                            ft_delete.append(res)
                        else:
                            try:
                                await remove(f_path)
                            except:
                                pass
            if checked:
                cpu_eater_lock.release()
        return dl_path

    async def generateScreenshots(self, dl_path):
        ss_nb = int(self.screenShots) if isinstance(self.screenShots, str) else 10
        if await aiopath.isfile(dl_path):
            if (await get_document_type(dl_path))[0]:
                LOGGER.info(f"Creating Screenshot for: {dl_path}")
                res = await take_ss(dl_path, ss_nb)
                if res:
                    newfolder = ospath.splitext(dl_path)[0]
                    name = dl_path.rsplit("/", 1)[1]
                    if self.seed and not self.newDir:
                        if self.isLeech and not self.compress:
                            return self.dir
                        await makedirs(newfolder, exist_ok=True)
                        self.newDir = f"{self.dir}10000"
                        newfolder = newfolder.replace(self.dir, self.newDir)
                        await gather(
                            copy2(dl_path, f"{newfolder}/{name}"),
                            move(res, newfolder),
                        )
                    else:
                        await makedirs(newfolder, exist_ok=True)
                        await gather(
                            move(dl_path, f"{newfolder}/{name}"),
                            move(res, newfolder),
                        )
                    return newfolder
        else:
            LOGGER.info(f"Creating Screenshot for: {dl_path}")
            for dirpath, _, files in await sync_to_async(walk, dl_path, topdown=False):
                for file_ in files:
                    f_path = ospath.join(dirpath, file_)
                    if (await get_document_type(f_path))[0]:
                        await take_ss(f_path, ss_nb)
        return dl_path

    async def substitute(self, dl_path):
        if await aiopath.isfile(dl_path):
            up_dir, name = dl_path.rsplit("/", 1)
            for l in self.nameSub:
                pattern = l[0]
                res = l[1] if len(l) > 1  and l[1] else ""
                sen = len(l) > 2 and l[2] == "s"
                new_name = sub(fr"{pattern}", res, name, flags=I if sen else 0)
            new_path = ospath.join(up_dir, new_name)
            await move(dl_path, new_path)
            return new_path
        else:
            for dirpath, _, files in await sync_to_async(walk, dl_path, topdown=False):
                for file_ in files:
                    f_path = ospath.join(dirpath, file_)
                    for l in self.nameSub:
                        pattern = l[0]
                        res = l[1] if len(l) > 1  and l[1] else ""
                        sen = len(l) > 2 and l[2] == "s"
                        new_name = sub(rf"{pattern}", res, file_, flags=I if sen else 0)
                    await move(f_path, ospath.join(dirpath, new_name))
            return dl_path
