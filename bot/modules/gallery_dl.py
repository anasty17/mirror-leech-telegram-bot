from gallery_dl import extractor

from .. import LOGGER, bot_loop, task_dict_lock, DOWNLOAD_DIR
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import (
    new_task,
    sync_to_async,
    arg_parser,
    COMMAND_USAGE,
)
from ..helper.ext_utils.links_utils import is_url
from ..helper.listeners.task_listener import TaskListener
from ..helper.mirror_leech_utils.download_utils.gallery_dl_download import (
    GalleryDLHelper,
)
from ..helper.telegram_helper.message_utils import send_message


def _check_gallery_dl_link(link):
    try:
        return extractor.find(link) is not None
    except Exception:
        return False


class GalleryDL(TaskListener):
    def __init__(
        self,
        client,
        message,
        _=None,
        is_leech=False,
        __=None,
        ___=None,
        same_dir=None,
        bulk=None,
        multi_tag=None,
        options="",
    ):
        if same_dir is None:
            same_dir = {}
        if bulk is None:
            bulk = []
        self.message = message
        self.client = client
        self.multi_tag = multi_tag
        self.options = options
        self.same_dir = same_dir
        self.bulk = bulk
        super().__init__()
        self.is_gallerydl = True
        self.is_leech = is_leech

    async def new_event(self):
        text = self.message.text.split("\n")
        input_list = text[0].split(" ")

        args = {
            "-doc": False,
            "-med": False,
            "-b": False,
            "-z": False,
            "-sv": False,
            "-ss": False,
            "-f": False,
            "-fd": False,
            "-fu": False,
            "-hl": False,
            "-bt": False,
            "-ut": False,
            "-i": 0,
            "-sp": 0,
            "link": "",
            "-m": "",
            "-opt": {},
            "-n": "",
            "-up": "",
            "-rcf": "",
            "-t": "",
            "-ca": "",
            "-cv": "",
            "-ns": "",
            "-tl": "",
            "-ff": set(),
        }

        arg_parser(input_list[1:], args)

        try:
            self.multi = int(args["-i"])
        except (ValueError, TypeError):
            self.multi = 0

        try:
            opt = eval(args["-opt"]) if args["-opt"] else {}
        except Exception as e:
            LOGGER.error(e)
            opt = {}

        self.ffmpeg_cmds = args["-ff"]
        self.name = args["-n"]
        self.up_dest = args["-up"]
        self.rc_flags = args["-rcf"]
        self.link = args["link"]
        self.compress = args["-z"]
        self.thumb = args["-t"]
        self.split_size = args["-sp"]
        self.sample_video = args["-sv"]
        self.screen_shots = args["-ss"]
        self.force_run = args["-f"]
        self.force_download = args["-fd"]
        self.force_upload = args["-fu"]
        self.convert_audio = args["-ca"]
        self.convert_video = args["-cv"]
        self.name_sub = args["-ns"]
        self.hybrid_leech = args["-hl"]
        self.thumbnail_layout = args["-tl"]
        self.as_doc = args["-doc"]
        self.as_med = args["-med"]
        self.folder_name = (
            f"/{args['-m']}".rstrip("/") if len(args["-m"]) > 0 else ""
        )
        self.bot_trans = args["-bt"]
        self.user_trans = args["-ut"]

        is_bulk = args["-b"]

        bulk_start = 0
        bulk_end = 0

        if not isinstance(is_bulk, bool):
            dargs = is_bulk.split(":")
            bulk_start = dargs[0] or None
            if len(dargs) == 2:
                bulk_end = dargs[1] or None
            is_bulk = True

        if not is_bulk:
            if self.multi > 0:
                if self.folder_name:
                    async with task_dict_lock:
                        if self.folder_name in self.same_dir:
                            self.same_dir[self.folder_name]["tasks"].add(
                                self.mid
                            )
                            for fd_name in self.same_dir:
                                if fd_name != self.folder_name:
                                    self.same_dir[fd_name]["total"] -= 1
                        elif self.same_dir:
                            self.same_dir[self.folder_name] = {
                                "total": self.multi,
                                "tasks": {self.mid},
                            }
                            for fd_name in self.same_dir:
                                if fd_name != self.folder_name:
                                    self.same_dir[fd_name]["total"] -= 1
                        else:
                            self.same_dir = {
                                self.folder_name: {
                                    "total": self.multi,
                                    "tasks": {self.mid},
                                }
                            }
                elif self.same_dir:
                    async with task_dict_lock:
                        for fd_name in self.same_dir:
                            self.same_dir[fd_name]["total"] -= 1
        else:
            await self.init_bulk(input_list, bulk_start, bulk_end, GalleryDL)
            return

        if len(self.bulk) != 0:
            del self.bulk[0]

        path = f"{DOWNLOAD_DIR}{self.mid}{self.folder_name}"

        await self.get_tag(text)

        opt = (
            opt
            or self.user_dict.get("GALLERY_DL_OPTIONS")
            or Config.GALLERY_DL_OPTIONS
        )

        if not self.link and (reply_to := self.message.reply_to_message):
            self.link = reply_to.text.split("\n", 1)[0].strip()

        if not is_url(self.link):
            await send_message(
                self.message,
                COMMAND_USAGE["gdl"][0],
                COMMAND_USAGE["gdl"][1],
            )
            await self.remove_from_same_dir()
            return

        if not await sync_to_async(_check_gallery_dl_link, self.link):
            await send_message(
                self.message,
                f"{self.tag} This link is not supported by gallery-dl.",
            )
            await self.remove_from_same_dir()
            return

        try:
            await self.before_start()
        except Exception as e:
            await send_message(self.message, e)
            await self.remove_from_same_dir()
            return

        await self.run_multi(input_list, GalleryDL)

        LOGGER.info(f"Downloading with gallery-dl: {self.link}")
        gdl = GalleryDLHelper(self)
        await gdl.add_download(path, opt)


async def gallery_dl(client, message):
    bot_loop.create_task(GalleryDL(client, message).new_event())


async def gallery_dl_leech(client, message):
    bot_loop.create_task(
        GalleryDL(client, message, is_leech=True).new_event()
    )
