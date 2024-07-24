from aiofiles.os import path as aiopath
from asyncio import wait_for, Event, wrap_future, gather
from functools import partial
from logging import getLogger
from natsort import natsorted
from pyrogram.filters import regex, user
from pyrogram.handlers import CallbackQueryHandler
from tenacity import RetryError
from time import time

from bot import config_dict
from bot.helper.ext_utils.bot_utils import new_thread, new_task, update_user_ldata
from bot.helper.ext_utils.db_handler import DbManager
from bot.helper.ext_utils.status_utils import get_readable_file_size, get_readable_time
from bot.helper.mirror_leech_utils.gdrive_utils.helper import GoogleDriveHelper
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    editMessage,
    deleteMessage,
)

LOGGER = getLogger(__name__)

LIST_LIMIT = 6


@new_task
async def id_updates(_, query, obj):
    await query.answer()
    message = query.message
    data = query.data.split()
    if data[1] == "cancel":
        obj.id = "Task has been cancelled!"
        obj.listener.isCancelled = True
        obj.event.set()
        await deleteMessage(message)
        return
    if obj.query_proc:
        return
    obj.query_proc = True
    if data[1] == "pre":
        obj.iter_start -= LIST_LIMIT * obj.page_step
        await obj.get_items_buttons()
    elif data[1] == "nex":
        obj.iter_start += LIST_LIMIT * obj.page_step
        await obj.get_items_buttons()
    elif data[1] == "back":
        if data[2] == "dr":
            await obj.choose_token()
        else:
            await obj.get_pevious_id()
    elif data[1] == "dr":
        index = int(data[2])
        i = obj.drives[index]
        obj.id = i["id"]
        obj.parents = [{"id": i["id"], "name": i["name"]}]
        await obj.get_items()
    elif data[1] == "pa":
        index = int(data[3])
        i = obj.items_list[index]
        obj.id = i["id"]
        if data[2] == "fo":
            obj.parents.append({"id": i["id"], "name": i["name"]})
            await obj.get_items()
        else:
            await deleteMessage(message)
            obj.event.set()
    elif data[1] == "ps":
        if obj.page_step == int(data[2]):
            return
        obj.page_step = int(data[2])
        await obj.get_items_buttons()
    elif data[1] == "root":
        obj.id = obj.parents[0]["id"]
        obj.parents = [obj.parents[0]]
        await obj.get_items()
    elif data[1] == "itype":
        obj.item_type = data[2]
        await obj.get_items()
    elif data[1] == "cur":
        await deleteMessage(message)
        obj.event.set()
    elif data[1] == "def":
        if obj.token_path != obj.user_token_path:
            id_ = f"sa:{obj.id}" if obj.use_sa else f"tp:{obj.id}"
        else:
            id_ = f"mtp:{obj.id}"
        if id_ != obj.listener.userDict.get("gdrive_id"):
            update_user_ldata(obj.listener.userId, "gdrive_id", id_)
            await obj.get_items_buttons()
            if config_dict["DATABASE_URL"]:
                await DbManager().update_user_data(obj.listener.userId)
    elif data[1] == "owner":
        obj.token_path = "token.pickle"
        obj.use_sa = False
        obj.id = ""
        obj.parents = []
        await obj.list_drives()
    elif data[1] == "user":
        obj.token_path = obj.user_token_path
        obj.use_sa = False
        obj.id = ""
        obj.parents = []
        await obj.list_drives()
    elif data[1] == "sa":
        obj.token_path = "accounts"
        obj.use_sa = True
        obj.id = ""
        obj.parents = []
        await obj.list_drives()
    obj.query_proc = False


class gdriveList(GoogleDriveHelper):
    def __init__(self, listener):
        self.listener = listener
        self._token_user = False
        self._token_owner = False
        self._sa_owner = False
        self._reply_to = None
        self._time = time()
        self._timeout = 240
        self.drives = []
        self.query_proc = False
        self.item_type = "folders"
        self.event = Event()
        self.user_token_path = f"tokens/{self.listener.userId}.pickle"
        self.id = ""
        self.parents = []
        self.list_status = ""
        self.items_list = []
        self.iter_start = 0
        self.page_step = 1
        super().__init__()

    @new_thread
    async def _event_handler(self):
        pfunc = partial(id_updates, obj=self)
        handler = self.listener.client.add_handler(
            CallbackQueryHandler(
                pfunc, filters=regex("^gdq") & user(self.listener.userId)
            ),
            group=-1,
        )
        try:
            await wait_for(self.event.wait(), timeout=self._timeout)
        except:
            self.id = "Timed Out. Task has been cancelled!"
            self.listener.isCancelled = True
            self.event.set()
        finally:
            self.listener.client.remove_handler(*handler)

    async def _send_list_message(self, msg, button):
        if not self.listener.isCancelled:
            if self._reply_to is None:
                self._reply_to = await sendMessage(self.listener.message, msg, button)
            else:
                await editMessage(self._reply_to, msg, button)

    async def get_items_buttons(self):
        items_no = len(self.items_list)
        pages = (items_no + LIST_LIMIT - 1) // LIST_LIMIT
        if items_no <= self.iter_start:
            self.iter_start = 0
        elif self.iter_start < 0 or self.iter_start > items_no:
            self.iter_start = LIST_LIMIT * (pages - 1)
        page = (self.iter_start / LIST_LIMIT) + 1 if self.iter_start != 0 else 1
        buttons = ButtonMaker()
        for index, item in enumerate(
            self.items_list[self.iter_start : LIST_LIMIT + self.iter_start]
        ):
            orig_index = index + self.iter_start
            if item["mimeType"] == self.G_DRIVE_DIR_MIME_TYPE:
                ptype = "fo"
                name = item["name"]
            else:
                ptype = "fi"
                name = f"[{get_readable_file_size(float(item['size']))}] {item['name']}"
            buttons.ibutton(name, f"gdq pa {ptype} {orig_index}")
        if items_no > LIST_LIMIT:
            for i in [1, 2, 4, 6, 10, 30, 50, 100]:
                buttons.ibutton(i, f"gdq ps {i}", position="header")
            buttons.ibutton("Previous", "gdq pre", position="footer")
            buttons.ibutton("Next", "gdq nex", position="footer")
        if self.list_status == "gdd":
            if self.item_type == "folders":
                buttons.ibutton("Files", "gdq itype files", position="footer")
            else:
                buttons.ibutton("Folders", "gdq itype folders", position="footer")
        if self.list_status == "gdu" or len(self.items_list) > 0:
            buttons.ibutton("Choose Current Path", "gdq cur", position="footer")
        if self.list_status == "gdu":
            buttons.ibutton("Set as Default Path", "gdq def", position="footer")
        if (
            len(self.parents) > 1
            and len(self.drives) > 1
            or self._token_user
            and self._token_owner
        ):
            buttons.ibutton("Back", "gdq back pa", position="footer")
        if len(self.parents) > 1:
            buttons.ibutton("Back To Root", "gdq root", position="footer")
        buttons.ibutton("Cancel", "gdq cancel", position="footer")
        button = buttons.build_menu(f_cols=2)
        msg = "Choose Path:" + (
            "\nTransfer Type: <i>Download</i>"
            if self.list_status == "gdd"
            else "\nTransfer Type: <i>Upload</i>"
        )
        if self.list_status == "gdu":
            default_id = (
                self.listener.userDict.get("gdrive_id") or config_dict["GDRIVE_ID"]
            )
            msg += f"\nDefault Gdrive ID: {default_id}" if default_id else ""
        msg += f"\n\nItems: {items_no}"
        if items_no > LIST_LIMIT:
            msg += f" | Page: {int(page)}/{pages} | Page Step: {self.page_step}"
        msg += f"\n\nItem Type: {self.item_type}\nToken Path: {self.token_path}"
        msg += f"\n\nCurrent ID: <code>{self.id}</code>"
        msg += f"\nCurrent Path: <code>{('/').join(i['name'] for i in self.parents)}</code>"
        msg += f"\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        await self._send_list_message(msg, button)

    async def get_items(self, itype=""):
        if itype:
            self.item_type == itype
        elif self.list_status == "gdu":
            self.item_type == "folders"
        try:
            files = self.getFilesByFolderId(self.id, self.item_type)
            if self.listener.isCancelled:
                return
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            self.id = str(err).replace(">", "").replace("<", "")
            self.event.set()
            return
        if len(files) == 0 and itype != self.item_type and self.list_status == "gdd":
            itype = "folders" if self.item_type == "files" else "files"
            self.item_type = itype
            return await self.get_items(itype)
        self.items_list = natsorted(files)
        self.iter_start = 0
        await self.get_items_buttons()

    async def list_drives(self):
        self.service = self.authorize()
        try:
            result = self.service.drives().list(pageSize="100").execute()
        except Exception as e:
            self.id = str(e)
            self.event.set()
            return
        drives = result["drives"]
        if len(drives) == 0 and not self.use_sa:
            self.drives = [{"id": "root", "name": "root"}]
            self.parents = [{"id": "root", "name": "root"}]
            self.id = "root"
            await self.get_items()
        elif len(drives) == 0:
            msg = "Service accounts Doesn't have access to any drive!"
            buttons = ButtonMaker()
            if self._token_user and self._token_owner:
                buttons.ibutton("Back", "gdq back dr", position="footer")
            buttons.ibutton("Cancel", "gdq cancel", position="footer")
            button = buttons.build_menu(2)
            await self._send_list_message(msg, button)
        elif self.use_sa and len(drives) == 1:
            self.id = drives[0]["id"]
            self.drives = [{"id": self.id, "name": drives[0]["name"]}]
            self.parents = [{"id": self.id, "name": drives[0]["name"]}]
            await self.get_items()
        else:
            msg = "Choose Drive:" + (
                "\nTransfer Type: <i>Download</i>"
                if self.list_status == "gdd"
                else "\nTransfer Type: <i>Upload</i>"
            )
            msg += f"\nToken Path: {self.token_path}"
            msg += (
                f"\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
            )
            buttons = ButtonMaker()
            self.drives.clear()
            self.parents.clear()
            if not self.use_sa:
                buttons.ibutton("root", "gdq dr 0")
                self.drives = [{"id": "root", "name": "root"}]
            for index, item in enumerate(drives, start=1):
                self.drives.append({"id": item["id"], "name": item["name"]})
                buttons.ibutton(item["name"], f"gdq dr {index}")
            if self._token_user and self._token_owner:
                buttons.ibutton("Back", "gdq back dr", position="footer")
            buttons.ibutton("Cancel", "gdq cancel", position="footer")
            button = buttons.build_menu(2)
            await self._send_list_message(msg, button)

    async def choose_token(self):
        if (
            self._token_user
            and self._token_owner
            or self._sa_owner
            and self._token_owner
            or self._sa_owner
            and self._token_user
        ):
            msg = "Choose Token:" + (
                "\nTransfer Type: Download"
                if self.list_status == "gdd"
                else "\nTransfer Type: Upload"
            )
            msg += (
                f"\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
            )
            buttons = ButtonMaker()
            if self._token_owner:
                buttons.ibutton("Owner Token", "gdq owner")
            if self._sa_owner:
                buttons.ibutton("Service Accounts", "gdq sa")
            if self._token_user:
                buttons.ibutton("My Token", "gdq user")
            buttons.ibutton("Cancel", "gdq cancel")
            button = buttons.build_menu(2)
            await self._send_list_message(msg, button)
        else:
            if self._token_owner:
                self.token_path = "token.pickle"
                self.use_sa = False
            elif self._token_user:
                self.token_path = self.user_token_path
                self.use_sa = False
            else:
                self.token_path = "accounts"
                self.use_sa = True
            await self.list_drives()

    async def get_pevious_id(self):
        if self.parents:
            self.parents.pop()
            if self.parents:
                self.id = self.parents[-1]["id"]
                await self.get_items()
            else:
                await self.list_drives()
        else:
            await self.list_drives()

    async def get_target_id(self, status, token_path=None):
        self.list_status = status
        future = self._event_handler()
        if token_path is None:
            self._token_user, self._token_owner, self._sa_owner = await gather(
                aiopath.exists(self.user_token_path),
                aiopath.exists("token.pickle"),
                aiopath.exists("accounts"),
            )
            if not self._token_owner and not self._token_user and not self._sa_owner:
                self.event.set()
                return "token.pickle or service accounts are not Exists!"
            await self.choose_token()
        else:
            self.token_path = token_path
            self.use_sa = self.token_path == "accounts"
            await self.list_drives()
        await wrap_future(future)
        if self._reply_to:
            await deleteMessage(self._reply_to)
        if not self.listener.isCancelled:
            if self.token_path == self.user_token_path:
                return f"mtp:{self.id}"
            else:
                return f"sa:{self.id}" if self.use_sa else f"tp:{self.id}"
        return self.id
