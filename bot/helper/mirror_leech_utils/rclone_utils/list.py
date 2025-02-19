from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from asyncio import wait_for, Event, gather
from configparser import RawConfigParser
from functools import partial
from json import loads
from pyrogram.filters import regex, user
from pyrogram.handlers import CallbackQueryHandler
from time import time

from .... import LOGGER
from ....core.config_manager import Config
from ...ext_utils.bot_utils import cmd_exec, update_user_ldata, new_task
from ...ext_utils.db_handler import database
from ...ext_utils.status_utils import get_readable_file_size, get_readable_time
from ...telegram_helper.button_build import ButtonMaker
from ...telegram_helper.message_utils import (
    send_message,
    edit_message,
    delete_message,
)

LIST_LIMIT = 6


@new_task
async def path_updates(_, query, obj):
    await query.answer()
    message = query.message
    data = query.data.split()
    if data[1] == "cancel":
        obj.remote = "Task has been cancelled!"
        obj.path = ""
        obj.listener.is_cancelled = True
        obj.event.set()
        await delete_message(message)
        return
    if obj.query_proc:
        return
    obj.query_proc = True
    if data[1] == "pre":
        obj.iter_start -= LIST_LIMIT * obj.page_step
        await obj.get_path_buttons()
    elif data[1] == "nex":
        obj.iter_start += LIST_LIMIT * obj.page_step
        await obj.get_path_buttons()
    elif data[1] == "select":
        obj.select = not obj.select
        await obj.get_path_buttons()
    elif data[1] == "back":
        if data[2] == "re":
            await obj.list_config()
        else:
            await obj.back_from_path()
    elif data[1] == "re":
        # some remotes has space
        data = query.data.split(maxsplit=2)
        obj.remote = data[2]
        await obj.get_path()
    elif data[1] == "clear":
        obj.selected_pathes = set()
        await obj.get_path_buttons()
    elif data[1] == "ds":
        obj.path = f"rclone_select_{time()}.txt"
        async with aiopen(obj.path, "w") as txt_file:
            for f in obj.selected_pathes:
                await txt_file.write(f"{f}\n")
        await delete_message(message)
        obj.event.set()
    elif data[1] == "pa":
        index = int(data[3])
        if obj.select:
            path = obj.path + (
                f"/{obj.path_list[index]['Path']}"
                if obj.path
                else obj.path_list[index]["Path"]
            )
            if path in obj.selected_pathes:
                obj.selected_pathes.remove(path)
            else:
                obj.selected_pathes.add(path)
            await obj.get_path_buttons()
            obj.query_proc = False
            return
        obj.path += (
            f"/{obj.path_list[index]['Path']}"
            if obj.path
            else obj.path_list[index]["Path"]
        )
        if data[2] == "fo":
            await obj.get_path()
        else:
            await delete_message(message)
            obj.event.set()
    elif data[1] == "ps":
        if obj.page_step == int(data[2]):
            obj.query_proc = False
            return
        obj.page_step = int(data[2])
        await obj.get_path_buttons()
    elif data[1] == "root":
        obj.path = ""
        await obj.get_path()
    elif data[1] == "itype":
        obj.item_type = data[2]
        await obj.get_path()
    elif data[1] == "cur":
        await delete_message(message)
        obj.event.set()
    elif data[1] == "def":
        path = (
            f"{obj.remote}{obj.path}"
            if obj.config_path == "rclone.conf"
            else f"mrcc:{obj.remote}{obj.path}"
        )
        if path != obj.listener.user_dict.get("RCLONE_PATH"):
            update_user_ldata(obj.listener.user_id, "RCLONE_PATH", path)
            await obj.get_path_buttons()
            if Config.DATABASE_URL:
                await database.update_user_data(obj.listener.user_id)
    elif data[1] == "owner":
        obj.config_path = "rclone.conf"
        obj.path = ""
        obj.remote = ""
        await obj.list_remotes()
    elif data[1] == "user":
        obj.config_path = obj.user_rcc_path
        obj.path = ""
        obj.remote = ""
        await obj.list_remotes()
    obj.query_proc = False


class RcloneList:
    def __init__(self, listener):
        self._rc_user = False
        self._rc_owner = False
        self._sections = []
        self._reply_to = None
        self._time = time()
        self._timeout = 240
        self.listener = listener
        self.remote = ""
        self.query_proc = False
        self.item_type = "--dirs-only"
        self.event = Event()
        self.user_rcc_path = f"rclone/{self.listener.user_id}.conf"
        self.config_path = ""
        self.path = ""
        self.list_status = ""
        self.path_list = []
        self.iter_start = 0
        self.page_step = 1
        self.select = False
        self.selected_pathes = set()

    async def _event_handler(self):
        pfunc = partial(path_updates, obj=self)
        handler = self.listener.client.add_handler(
            CallbackQueryHandler(
                pfunc, filters=regex("^rcq") & user(self.listener.user_id)
            ),
            group=-1,
        )
        try:
            await wait_for(self.event.wait(), timeout=self._timeout)
        except:
            self.path = ""
            self.remote = "Timed Out. Task has been cancelled!"
            self.listener.is_cancelled = True
            self.event.set()
        finally:
            self.listener.client.remove_handler(*handler)

    async def _send_list_message(self, msg, button):
        if not self.listener.is_cancelled:
            if self._reply_to is None:
                self._reply_to = await send_message(self.listener.message, msg, button)
            else:
                await edit_message(self._reply_to, msg, button)

    async def get_path_buttons(self):
        items_no = len(self.path_list)
        pages = (items_no + LIST_LIMIT - 1) // LIST_LIMIT
        if items_no <= self.iter_start:
            self.iter_start = 0
        elif self.iter_start < 0 or self.iter_start > items_no:
            self.iter_start = LIST_LIMIT * (pages - 1)
        page = (self.iter_start / LIST_LIMIT) + 1 if self.iter_start != 0 else 1
        buttons = ButtonMaker()
        for index, idict in enumerate(
            self.path_list[self.iter_start : LIST_LIMIT + self.iter_start]
        ):
            orig_index = index + self.iter_start
            name = idict["Path"]
            if name in self.selected_pathes or any(
                p.strip().endswith(f"/{name}") for p in self.selected_pathes
            ):
                name = f"✅ {name}"
            if idict["IsDir"]:
                ptype = "fo"
            else:
                ptype = "fi"
                name = f"[{get_readable_file_size(idict['Size'])}] {name}"
            buttons.data_button(name, f"rcq pa {ptype} {orig_index}")
        if items_no > LIST_LIMIT:
            for i in [1, 2, 4, 6, 10, 30, 50, 100]:
                buttons.data_button(i, f"rcq ps {i}", position="header")
            buttons.data_button("Previous", "rcq pre", position="footer")
            buttons.data_button("Next", "rcq nex", position="footer")
        if self.list_status == "rcd":
            if self.item_type == "--dirs-only":
                buttons.data_button(
                    "Files", "rcq itype --files-only", position="footer"
                )
            else:
                buttons.data_button(
                    "Folders", "rcq itype --dirs-only", position="footer"
                )
        if self.list_status == "rcu" or len(self.path_list) > 0:
            buttons.data_button("Choose Current Path", "rcq cur", position="footer")
        if self.list_status == "rcd":
            buttons.data_button(
                f"Select: {'Enabled' if self.select else 'Disabled'}",
                "rcq select",
                position="footer",
            )
        if len(self.selected_pathes) > 1:
            buttons.data_button("Done With Selection", "rcq ds", position="footer")
            buttons.data_button("Clear Selection", "rcq clear", position="footer")
        if self.list_status == "rcu":
            buttons.data_button("Set as Default Path", "rcq def", position="footer")
        if self.path or len(self._sections) > 1 or self._rc_user and self._rc_owner:
            buttons.data_button("Back", "rcq back pa", position="footer")
        if self.path:
            buttons.data_button("Back To Root", "rcq root", position="footer")
        buttons.data_button("Cancel", "rcq cancel", position="footer")
        button = buttons.build_menu(f_cols=2)
        msg = "Choose Path:" + (
            "\nTransfer Type: <i>Download</i>"
            if self.list_status == "rcd"
            else "\nTransfer Type: <i>Upload</i>"
        )
        if self.list_status == "rcu":
            default_path = Config.RCLONE_PATH
            msg += f"\nDefault Rclone Path: {default_path}" if default_path else ""
        msg += f"\n\nItems: {items_no}"
        if items_no > LIST_LIMIT:
            msg += f" | Page: {int(page)}/{pages} | Page Step: {self.page_step}"
        msg += f"\n\nItem Type: {self.item_type}\nConfig Path: {self.config_path}"
        msg += f"\nCurrent Path: <code>{self.remote}{self.path}</code>"
        msg += f"\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
        await self._send_list_message(msg, button)

    async def get_path(self, itype=""):
        if self.list_status == "rcu":
            self.item_type = "--dirs-only"
        elif itype:
            self.item_type = itype
        cmd = [
            "rclone",
            "lsjson",
            self.item_type,
            "--fast-list",
            "--no-mimetype",
            "--no-modtime",
            "--config",
            self.config_path,
            f"{self.remote}{self.path}",
            "-v",
            "--log-systemd",
        ]
        if self.listener.is_cancelled:
            return
        res, err, code = await cmd_exec(cmd)
        if code in [0, -9]:
            result = loads(res)
            if (
                len(result) == 0
                and itype != self.item_type
                and self.list_status == "rcd"
            ):
                itype = (
                    "--dirs-only"
                    if self.item_type == "--files-only"
                    else "--files-only"
                )
                self.item_type = itype
                await self.get_path(itype)
            else:
                self.path_list = sorted(result, key=lambda x: x["Path"])
                self.iter_start = 0
                await self.get_path_buttons()
        else:
            LOGGER.error(
                f"While rclone listing. Path: {self.remote}{self.path}. Stderr: {err}"
            )
            self.remote = err[:4000]
            self.path = ""
            self.event.set()

    async def list_remotes(self):
        config = RawConfigParser()
        async with aiopen(self.config_path, "r") as f:
            contents = await f.read()
            config.read_string(contents)
        if config.has_section("combine"):
            config.remove_section("combine")
        self._sections = config.sections()
        if len(self._sections) == 1:
            self.remote = f"{self._sections[0]}:"
            await self.get_path()
        else:
            msg = "Choose Rclone remote:" + (
                "\nTransfer Type: <i>Download</i>"
                if self.list_status == "rcd"
                else "\nTransfer Type: <i>Upload</i>"
            )
            msg += f"\nConfig Path: {self.config_path}"
            msg += (
                f"\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
            )
            buttons = ButtonMaker()
            for remote in self._sections:
                buttons.data_button(remote, f"rcq re {remote}:")
            if self._rc_user and self._rc_owner:
                buttons.data_button("Back", "rcq back re", position="footer")
            buttons.data_button("Cancel", "rcq cancel", position="footer")
            button = buttons.build_menu(2)
            await self._send_list_message(msg, button)

    async def list_config(self):
        if self._rc_user and self._rc_owner:
            msg = "Choose Rclone config:" + (
                "\nTransfer Type: Download"
                if self.list_status == "rcd"
                else "\nTransfer Type: Upload"
            )
            msg += (
                f"\nTimeout: {get_readable_time(self._timeout - (time() - self._time))}"
            )
            buttons = ButtonMaker()
            buttons.data_button("Owner Config", "rcq owner")
            buttons.data_button("My Config", "rcq user")
            buttons.data_button("Cancel", "rcq cancel")
            button = buttons.build_menu(2)
            await self._send_list_message(msg, button)
        else:
            self.config_path = "rclone.conf" if self._rc_owner else self.user_rcc_path
            await self.list_remotes()

    async def back_from_path(self):
        if self.path:
            path = self.path.rsplit("/", 1)
            self.path = path[0] if len(path) > 1 else ""
            await self.get_path()
        elif len(self._sections) > 1:
            await self.list_remotes()
        else:
            await self.list_config()

    async def get_rclone_path(self, status, config_path=None):
        self.list_status = status
        if config_path is None:
            self._rc_user, self._rc_owner = await gather(
                aiopath.exists(self.user_rcc_path), aiopath.exists("rclone.conf")
            )
            if not self._rc_owner and not self._rc_user:
                self.event.set()
                return "Rclone Config not Exists!"
            await self.list_config()
        else:
            self.config_path = config_path
            await self.list_remotes()
        await self._event_handler()
        await delete_message(self._reply_to)
        if self.config_path != "rclone.conf" and not self.listener.is_cancelled:
            return f"mrcc:{self.remote}{self.path}"
        return f"{self.remote}{self.path}"
