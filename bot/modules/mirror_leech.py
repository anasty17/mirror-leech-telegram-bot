from aiofiles.os import path as aiopath, remove
from base64 import b64encode
from pyrogram.filters import command
from pyrogram.handlers import MessageHandler
from re import match as re_match

from bot import bot, DOWNLOAD_DIR, LOGGER
from bot.helper.ext_utils.bot_utils import (
    get_content_type,
    new_task,
    sync_to_async,
    arg_parser,
    COMMAND_USAGE,
)
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from bot.helper.ext_utils.links_utils import (
    is_url,
    is_magnet,
    is_gdrive_link,
    is_rclone_path,
    is_telegram_link,
    is_gdrive_id,
)
from bot.helper.listeners.task_listener import TaskListener
from bot.helper.mirror_leech_utils.download_utils.aria2_download import add_aria2c_download
from bot.helper.mirror_leech_utils.download_utils.direct_downloader import add_direct_download
from bot.helper.mirror_leech_utils.download_utils.direct_link_generator import (
    direct_link_generator,
)
from bot.helper.mirror_leech_utils.download_utils.gd_download import add_gd_download
from bot.helper.mirror_leech_utils.download_utils.jd_download import add_jd_download
from bot.helper.mirror_leech_utils.download_utils.qbit_download import add_qb_torrent
from bot.helper.mirror_leech_utils.download_utils.rclone_download import add_rclone_download
from bot.helper.mirror_leech_utils.download_utils.telegram_download import (
    TelegramDownloadHelper,
)
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, get_tg_link_message
from myjd.exception import MYJDException


class Mirror(TaskListener):
    def __init__(
        self,
        client,
        message,
        isQbit=False,
        isLeech=False,
        isJd=False,
        sameDir=None,
        bulk=None,
        multiTag=None,
        options="",
    ):
        if sameDir is None:
            sameDir = {}
        if bulk is None:
            bulk = []
        self.message = message
        self.client = client
        self.multiTag = multiTag
        self.options = options
        self.sameDir = sameDir
        self.bulk = bulk
        super().__init__()
        self.isQbit = isQbit
        self.isLeech = isLeech
        self.isJd = isJd

    @new_task
    async def newEvent(self):
        text = self.message.text.split("\n")
        input_list = text[0].split(" ")

        args = {
            "-d": False,
            "-j": False,
            "-s": False,
            "-b": False,
            "-e": False,
            "-z": False,
            "-sv": False,
            "-ss": False,
            "-f": False,
            "-fd": False,
            "-fu": False,
            "-ml": False,
            "-i": 0,
            "-sp": 0,
            "link": "",
            "-n": "",
            "-m": "",
            "-up": "",
            "-rcf": "",
            "-au": "",
            "-ap": "",
            "-h": "",
            "-t": "",
            "-ca": "",
            "-cv": "",
            "-ns": "",
        }

        arg_parser(input_list[1:], args)

        self.select = args["-s"]
        self.seed = args["-d"]
        self.name = args["-n"]
        self.upDest = args["-up"]
        self.rcFlags = args["-rcf"]
        self.link = args["link"]
        self.compress = args["-z"]
        self.extract = args["-e"]
        self.join = args["-j"]
        self.thumb = args["-t"]
        self.splitSize = args["-sp"]
        self.sampleVideo = args["-sv"]
        self.screenShots = args["-ss"]
        self.forceRun = args["-f"]
        self.forceDownload = args["-fd"]
        self.forceUpload = args["-fu"]
        self.convertAudio = args["-ca"]
        self.convertVideo = args["-cv"]
        self.nameSub = args["-ns"]
        self.mixedLeech = args["-ml"]

        headers = args["-h"]
        isBulk = args["-b"]
        folder_name = args["-m"]

        bulk_start = 0
        bulk_end = 0
        ratio = None
        seed_time = None
        reply_to = None
        file_ = None
        session = ""

        try:
            self.multi = int(args["-i"])
        except:
            self.multi = 0

        if not isinstance(self.seed, bool):
            dargs = self.seed.split(":")
            ratio = dargs[0] or None
            if len(dargs) == 2:
                seed_time = dargs[1] or None
            self.seed = True

        if not isinstance(isBulk, bool):
            dargs = isBulk.split(":")
            bulk_start = dargs[0] or 0
            if len(dargs) == 2:
                bulk_end = dargs[1] or 0
            isBulk = True

        if not isBulk:
            if folder_name:
                self.seed = False
                ratio = None
                seed_time = None
                folder_name = f"/{folder_name}"
                if not self.sameDir:
                    self.sameDir = {
                        "total": self.multi,
                        "tasks": set(),
                        "name": folder_name,
                    }
                self.sameDir["tasks"].add(self.mid)
            elif self.sameDir:
                self.sameDir["total"] -= 1

        else:
            await self.initBulk(input_list, bulk_start, bulk_end, Mirror)
            return

        if len(self.bulk) != 0:
            del self.bulk[0]

        self.run_multi(input_list, folder_name, Mirror)

        await self.getTag(text)

        path = f"{DOWNLOAD_DIR}{self.mid}{folder_name}"

        if not self.link and (reply_to := self.message.reply_to_message):
            if reply_to.text:
                self.link = reply_to.text.split("\n", 1)[0].strip()
        if is_telegram_link(self.link):
            try:
                reply_to, session = await get_tg_link_message(self.link)
            except Exception as e:
                await sendMessage(self.message, f"ERROR: {e}")
                self.removeFromSameDir()
                return

        if isinstance(reply_to, list):
            self.bulk = reply_to
            self.sameDir = {}
            b_msg = input_list[:1]
            self.options = " ".join(input_list[1:])
            b_msg.append(f"{self.bulk[0]} -i {len(self.bulk)} {self.options}")
            nextmsg = await sendMessage(self.message, " ".join(b_msg))
            nextmsg = await self.client.get_messages(
                chat_id=self.message.chat.id, message_ids=nextmsg.id
            )
            if self.message.from_user:
                nextmsg.from_user = self.user
            else:
                nextmsg.sender_chat = self.user
            Mirror(
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
            return

        if reply_to:
            file_ = (
                reply_to.document
                or reply_to.photo
                or reply_to.video
                or reply_to.audio
                or reply_to.voice
                or reply_to.video_note
                or reply_to.sticker
                or reply_to.animation
                or None
            )

            if file_ is None:
                if reply_text := reply_to.text:
                    self.link = reply_text.split("\n", 1)[0].strip()
                else:
                    reply_to = None
            elif reply_to.document and (
                file_.mime_type == "application/x-bittorrent"
                or file_.file_name.endswith((".torrent", ".dlc"))
            ):
                self.link = await reply_to.download()
                file_ = None

        if (
            not self.link
            and file_ is None
            or is_telegram_link(self.link)
            and reply_to is None
            or file_ is None
            and not is_url(self.link)
            and not is_magnet(self.link)
            and not await aiopath.exists(self.link)
            and not is_rclone_path(self.link)
            and not is_gdrive_id(self.link)
            and not is_gdrive_link(self.link)
        ):
            await sendMessage(
                self.message, COMMAND_USAGE["mirror"][0], COMMAND_USAGE["mirror"][1]
            )
            self.removeFromSameDir()
            return

        if self.link:
            LOGGER.info(self.link)

        try:
            await self.beforeStart()
        except Exception as e:
            await sendMessage(self.message, e)
            self.removeFromSameDir()
            return

        if (
            not self.isJd
            and not self.isQbit
            and not is_magnet(self.link)
            and not is_rclone_path(self.link)
            and not is_gdrive_link(self.link)
            and not self.link.endswith(".torrent")
            and file_ is None
            and not is_gdrive_id(self.link)
        ):
            content_type = await get_content_type(self.link)
            if content_type is None or re_match(r"text/html|text/plain", content_type):
                try:
                    self.link = await sync_to_async(direct_link_generator, self.link)
                    if isinstance(self.link, tuple):
                        self.link, headers = self.link
                    elif isinstance(self.link, str):
                        LOGGER.info(f"Generated link: {self.link}")
                except DirectDownloadLinkException as e:
                    e = str(e)
                    if "This link requires a password!" not in e:
                        LOGGER.info(e)
                    if e.startswith("ERROR:"):
                        await sendMessage(self.message, e)
                        self.removeFromSameDir()
                        return

        if file_ is not None:
            await TelegramDownloadHelper(self).add_download(reply_to, f"{path}/", session)
        elif isinstance(self.link, dict):
            await add_direct_download(self, path)
        elif self.isJd:
            try:
                await add_jd_download(self, path)
            except (Exception, MYJDException) as e:
                await sendMessage(self.message, f"{e}".strip())
                self.removeFromSameDir()
                return
            finally:
                if await aiopath.exists(self.link):
                    await remove(self.link)
        elif self.isQbit:
            await add_qb_torrent(self, path, ratio, seed_time)
        elif is_rclone_path(self.link):
            await add_rclone_download(self, f"{path}/")
        elif is_gdrive_link(self.link) or is_gdrive_id(self.link):
            await add_gd_download(self, path)
        else:
            ussr = args["-au"]
            pssw = args["-ap"]
            if ussr or pssw:
                auth = f"{ussr}:{pssw}"
                headers += (
                    f" authorization: Basic {b64encode(auth.encode()).decode('ascii')}"
                )
            await add_aria2c_download(self, path, headers, ratio, seed_time)


async def mirror(client, message):
    Mirror(client, message).newEvent()


async def qb_mirror(client, message):
    Mirror(client, message, isQbit=True).newEvent()


async def leech(client, message):
    Mirror(client, message, isLeech=True).newEvent()


async def qb_leech(client, message):
    Mirror(client, message, isQbit=True, isLeech=True).newEvent()


async def jd_mirror(client, message):
    Mirror(client, message, isJd=True).newEvent()


async def jd_leech(client, message):
    Mirror(client, message, isLeech=True, isJd=True).newEvent()


bot.add_handler(
    MessageHandler(
        mirror, filters=command(BotCommands.MirrorCommand) & CustomFilters.authorized
    )
)
bot.add_handler(
    MessageHandler(
        qb_mirror,
        filters=command(BotCommands.QbMirrorCommand) & CustomFilters.authorized,
    )
)
bot.add_handler(
    MessageHandler(
        leech, filters=command(BotCommands.LeechCommand) & CustomFilters.authorized
    )
)
bot.add_handler(
    MessageHandler(
        qb_leech, filters=command(BotCommands.QbLeechCommand) & CustomFilters.authorized
    )
)
bot.add_handler(
    MessageHandler(
        jd_mirror,
        filters=command(BotCommands.JdMirrorCommand) & CustomFilters.authorized,
    )
)
bot.add_handler(
    MessageHandler(
        jd_leech, filters=command(BotCommands.JdLeechCommand) & CustomFilters.authorized
    )
)
