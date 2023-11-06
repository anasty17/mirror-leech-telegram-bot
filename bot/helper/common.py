from aiofiles.os import path as aiopath
from asyncio import sleep
from secrets import token_urlsafe

from bot import (
    DOWNLOAD_DIR,
    MAX_SPLIT_SIZE,
    config_dict,
    user_data,
    IS_PREMIUM_USER,
    user,
    multi_tags,
)
from bot.helper.ext_utils.bot_utils import new_task
from bot.helper.ext_utils.links_utils import (
    is_gdrive_id,
    is_rclone_path,
    is_gdrive_link,
    is_telegram_link,
)
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    sendStatusMessage,
    get_tg_link_message,
)
from bot.helper.ext_utils.bulk_links import extractBulkLinks
from bot.helper.mirror_utils.rclone_utils.list import RcloneList
from bot.helper.mirror_utils.gdrive_utils.list import gdriveList
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.leech_utils import createThumb, getSplitSizeBytes


class TaskConfig:
    def __init__(self, message):
        self.message = message
        self.mid = self.message.id
        self.user_id = self.message.from_user.id
        self.user_dict = user_data.get(self.user_id, {})
        self.sameDir = {}
        self.bulk = []
        self.dir = f"{DOWNLOAD_DIR}{self.mid}"
        self.link = ""
        self.upDest = ""
        self.rcFlags = ""
        self.options = ""
        self.tag = ""
        self.name = ""
        self.session = ""
        self.newDir = ""
        self.multiTag = 0
        self.splitSize = 0
        self.maxSplitSize = 0
        self.multi = 0
        self.equalSplits = False
        self.userTransmission = False
        self.isClone = False
        self.isQbit = False
        self.isLeech = False
        self.extract = False
        self.compress = False
        self.select = False
        self.seed = False
        self.compress = False
        self.extract = False
        self.join = False
        self.isYtDlp = False
        self.privateLink = False
        self.suproc = None
        self.client = None
        self.thumb = None
        self.isSuperChat = self.message.chat.type.name in ["SUPERGROUP", "CHANNEL"]

    def getTokenPath(self, dest):
        if dest.startswith("mtp:"):
            return f"tokens/{self.user_id}.pickle"
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
            f"rclone/{self.user_id}.conf" if dest.startswith("mrcc:") else "rclone.conf"
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
                raise ValueError(f"SAccounts or token.pickle: {token_path} not Exists!")

    async def beforeStart(self):
        if not self.isYtDlp:
            if self.link not in ["rcl", "gdl"]:
                await self.isTokenExists(self.link, "dl")
            elif self.link == "rcl":
                self.link = await RcloneList(self).get_rclone_path("rcd")
                if not is_rclone_path(self.link):
                    raise ValueError(self.link)
            elif self.link == "gdl":
                self.link = await gdriveList(self).get_target_id("gdd")
                if not is_gdrive_id(self.link):
                    raise ValueError(self.link)

        if not self.isLeech:
            default_upload = self.user_dict.get("default_upload", "")
            if (
                not self.upDest
                and (
                    default_upload == "rc"
                    or not default_upload
                    and config_dict["DEFAULT_UPLOAD"] == "rc"
                )
                or self.upDest == "rc"
            ):
                self.upDest = (
                    self.user_dict.get("rclone_path") or config_dict["RCLONE_PATH"]
                )
            if (
                not self.upDest
                and (
                    default_upload == "gd"
                    or not default_upload
                    and config_dict["DEFAULT_UPLOAD"] == "gd"
                )
                or self.upDest == "gd"
            ):
                self.upDest = (
                    self.user_dict.get("gdrive_id") or config_dict["GDRIVE_ID"]
                )
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
            if self.splitSize:
                if self.splitSize.isdigit():
                    self.splitSize = int(self.splitSize)
                else:
                    self.splitSize = getSplitSizeBytes(self.splitSize)
            self.splitSize = (
                self.splitSize
                or self.user_dict.get("split_size")
                or config_dict["LEECH_SPLIT_SIZE"]
            )
            self.equalSplits = (
                self.user_dict.get("equal_splits")
                or config_dict["EQUAL_SPLITS"]
                and "equal_splits" not in self.user_dict
            )
            self.userTransmission = IS_PREMIUM_USER and (
                self.user_dict.get("user_transmission")
                or config_dict["USER_TRANSMISSION"]
                and "user_transmission" not in self.user_dict
            )
            self.maxSplitSize = MAX_SPLIT_SIZE if self.userTransmission else 2097152000
            self.splitSize = min(self.splitSize, self.maxSplitSize)
            self.upDest = (
                self.upDest
                or self.user_dict.get("leech_dest")
                or config_dict["LEECH_DUMP_CHAT"]
            )
            if not isinstance(self.upDest, int):
                if self.upDest.startswith("b:"):
                    self.upDest = self.upDest.lstrip("b:")
                    self.userTransmission = False
                elif self.upDest.startswith("u:"):
                    self.upDest = self.upDest.lstrip("u:")
                    self.userTransmission = IS_PREMIUM_USER
                if self.upDest.isdigit() or self.upDest.startswith("-"):
                    self.upDest = int(self.upDest)
            if self.upDest:
                if self.userTransmission:
                    chat = await user.get_chat(self.upDest)
                    uploader_id = user.me.id
                else:
                    chat = await self.client.get_chat(self.upDest)
                    uploader_id = self.client.me.id
                if chat.type.name not in ["SUPERGROUP", "CHANNEL"]:
                    raise ValueError(
                        "Custom Leech Destination only allowed for super-group or channel!"
                    )
                member = await chat.get_member(uploader_id)
                if (
                    not member.privileges.can_manage_chat
                    or not member.privileges.can_delete_messages
                ):
                    raise ValueError("You don't have enough privileges in this chat!")
            elif self.userTransmission and not self.isSuperChat:
                raise ValueError(
                    "Use SuperGroup incase you want to upload using User session!"
                )

            if is_telegram_link(self.thumb):
                msg = await get_tg_link_message(self.thumb)
                self.thumb = await createThumb(msg) if msg.photo or msg.document else ""

    async def getTag(self, text: list):
        if len(text) > 1 and text[1].startswith("Tag: "):
            self.tag, id_ = text[1].split("Tag: ")[1].split()
            self.message.from_user = await self.client.get_users(id_)
            try:
                await self.message.unpin()
            except:
                pass
        if username := self.message.from_user.username:
            self.tag = f"@{username}"
        else:
            self.tag = self.message.from_user.mention

    @new_task
    async def run_multi(self, input_list, folder_name, obj):
        await sleep(5)
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
                msgts += f"\nCancel Multi: <code>/{BotCommands.CancelTaskCommand} {self.multiTag}</code>"
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
                msgts += f"\nCancel Multi: <code>/{BotCommands.CancelTaskCommand} {self.multiTag}</code>"
            nextmsg = await sendMessage(nextmsg, msgts)
        nextmsg = await self.client.get_messages(
            chat_id=self.message.chat.id, message_ids=nextmsg.id
        )
        if folder_name:
            self.sameDir["tasks"].add(nextmsg.id)
        nextmsg.from_user = self.message.from_user
        obj(
            self.client,
            nextmsg,
            self.isQbit,
            self.isLeech,
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
            nextmsg.from_user = self.message.from_user
            obj(
                self.client,
                nextmsg,
                self.isQbit,
                self.isLeech,
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
