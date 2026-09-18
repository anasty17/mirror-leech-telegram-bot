from ast import literal_eval
from aiofiles import open as aiopen
from aiofiles.os import remove, rename, path as aiopath
from aioshutil import rmtree
from asyncio import create_subprocess_exec, sleep, gather
from functools import partial
from io import BytesIO
from os import chmod, getcwd
from pyrogram.filters import create
from pyrogram.handlers import MessageHandler
from time import time

from .. import (
    LOGGER,
    drives_ids,
    drives_names,
    index_urls,
    intervals,
    aria2_options,
    task_dict,
    qbit_options,
    sabnzbd_client,
    nzb_options,
    jd_listener_lock,
    excluded_extensions,
    included_extensions,
    auth_chats,
    sudo_users,
)
from ..helper.ext_utils.bot_utils import SetInterval, new_task
from ..core.config_manager import Config
from ..core.telegram_manager import TgClient
from ..core.torrent_manager import TorrentManager
from ..core.startup import update_qb_options, update_nzb_options, update_variables
from ..helper.ext_utils.db_handler import database
from ..core.jdownloader_booter import jdownloader
from ..helper.ext_utils.task_manager import start_from_queued
from ..helper.mirror_leech_utils.rclone_utils.serve import rclone_serve_booter
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import (
    send_message,
    send_file,
    edit_message,
    update_status_message,
    delete_message,
)
from .rss import add_job
from .search import initiate_search_tools

start = 0
state = "view"
handler_dict = {}
DEFAULT_VALUES = {
    "LEECH_SPLIT_SIZE": TgClient.MAX_SPLIT_SIZE,
    "RSS_DELAY": 600,
    "STATUS_UPDATE_INTERVAL": 15,
    "SEARCH_LIMIT": 0,
    "UPSTREAM_BRANCH": "master",
    "DEFAULT_UPLOAD": "rc",
}


def _safe_literal(value, expected_type=None):
    parsed = literal_eval(value)
    if expected_type is not None and not isinstance(parsed, expected_type):
        raise ValueError(f"Expected {expected_type.__name__}")
    return parsed


async def _start_web_server(port):
    return await create_subprocess_exec(
        "gunicorn",
        "-k",
        "uvicorn.workers.UvicornWorker",
        "-w",
        "1",
        "web.wserver:app",
        "--bind",
        f"0.0.0.0:{int(port)}",
    )


async def get_buttons(key=None, edit_type=None):
    buttons = ButtonMaker()
    if key is None:
        buttons.data_button("Config Variables", "botset var")
        buttons.data_button("Private Files", "botset private")
        buttons.data_button("Qbit Settings", "botset qbit")
        buttons.data_button("Aria2c Settings", "botset aria")
        buttons.data_button("Sabnzbd Settings", "botset nzb")
        buttons.data_button("JDownloader Sync", "botset syncjd")
        buttons.data_button("Close", "botset close")
        msg = "Bot Settings:"
    elif edit_type is not None:
        if edit_type == "botvar":
            msg = ""
            buttons.data_button("Back", "botset var")
            if key not in ["TELEGRAM_HASH", "TELEGRAM_API", "OWNER_ID", "BOT_TOKEN"]:
                buttons.data_button("Default", f"botset resetvar {key}")
            buttons.data_button("Close", "botset close")
            if key in [
                "CMD_SUFFIX",
                "OWNER_ID",
                "USER_SESSION_STRING",
                "TELEGRAM_HASH",
                "TELEGRAM_API",
                "BOT_TOKEN",
                "TG_PROXY",
            ]:
                msg += "Restart required for this edit to take effect! You will not see the changes in bot vars, the edit will be in database only!\n\n"
            msg += f"Send a valid value for {key}. Current value is '{Config.get(key)}'. Timeout: 60 sec"
        elif edit_type == "ariavar":
            buttons.data_button("Back", "botset aria")
            if key != "newkey":
                buttons.data_button("Empty String", f"botset emptyaria {key}")
            buttons.data_button("Close", "botset close")
            msg = (
                "Send a key with value. Example: https-proxy-user:value. Timeout: 60 sec"
                if key == "newkey"
                else f"Send a valid value for {key}. Current value is '{aria2_options[key]}'. Timeout: 60 sec"
            )
        elif edit_type == "qbitvar":
            buttons.data_button("Back", "botset qbit")
            buttons.data_button("Empty String", f"botset emptyqbit {key}")
            buttons.data_button("Close", "botset close")
            msg = f"Send a valid value for {key}. Current value is '{qbit_options[key]}'. Timeout: 60 sec"
        elif edit_type == "nzbvar":
            buttons.data_button("Back", "botset nzb")
            buttons.data_button("Default", f"botset resetnzb {key}")
            buttons.data_button("Empty String", f"botset emptynzb {key}")
            buttons.data_button("Close", "botset close")
            msg = f"Send a valid value for {key}. Current value is '{nzb_options[key]}'.\nIf the value is list then separate them by space or ,\nExample: .exe,info or .exe .info\nTimeout: 60 sec"
        elif edit_type.startswith("nzbsevar"):
            index = 0 if key == "newser" else int(edit_type.replace("nzbsevar", ""))
            if key == "newser":
                buttons.data_button("Back", "botset nzbserver")
                msg = "Send one server as dictionary {}, like in config.py without []. Timeout: 60 sec"
            else:
                buttons.data_button("Empty", f"botset emptyserkey {index} {key}")
                buttons.data_button("Back", f"botset nzbser{index}")
                msg = f"Send a valid value for {key} in server {Config.USENET_SERVERS[index]['name']}. Current value is {Config.USENET_SERVERS[index][key]}. Timeout: 60 sec"
            buttons.data_button("Close", "botset close")
    elif key == "var":
        conf_dict = Config.get_all()
        for k in list(conf_dict.keys())[start : 10 + start]:
            if k in ["DATABASE_URL", "DATABASE_NAME"] and state != "view":
                continue
            buttons.data_button(k, f"botset botvar {k}")
        buttons.data_button("Edit" if state == "view" else "View", f"botset {'edit' if state == 'view' else 'view'} var")
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        for x in range(0, len(conf_dict), 10):
            buttons.data_button(f"{int(x / 10)}", f"botset start var {x}", position="footer")
        msg = f"Config Variables | Page: {int(start / 10)} | State: {state}"
    elif key == "private":
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        msg = """Send private file: config.py, token.pickle, rclone.conf, accounts.zip, list_drives.txt, cookies.txt, .netrc or any other private file!
To delete private file send only the file name as text message.
Note: Changing .netrc will not take effect for aria2c until restart.
Timeout: 60 sec"""
    elif key == "aria":
        for k in list(aria2_options.keys())[start : 10 + start]:
            if k not in ["checksum", "index-out", "out", "pause", "select-file"]:
                buttons.data_button(k, f"botset ariavar {k}")
        buttons.data_button("Edit" if state == "view" else "View", f"botset {'edit' if state == 'view' else 'view'} aria")
        buttons.data_button("Add new key", "botset ariavar newkey")
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        for x in range(0, len(aria2_options), 10):
            buttons.data_button(f"{int(x / 10)}", f"botset start aria {x}", position="footer")
        msg = f"Aria2c Options | Page: {int(start / 10)} | State: {state}"
    elif key == "qbit":
        for k in list(qbit_options.keys())[start : 10 + start]:
            buttons.data_button(k, f"botset qbitvar {k}")
        buttons.data_button("Edit" if state == "view" else "View", f"botset {'edit' if state == 'view' else 'view'} qbit")
        buttons.data_button("Sync Qbittorrent", "botset syncqbit")
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        for x in range(0, len(qbit_options), 10):
            buttons.data_button(f"{int(x / 10)}", f"botset start qbit {x}", position="footer")
        msg = f"Qbittorrent Options | Page: {int(start / 10)} | State: {state}"
    elif key == "nzb":
        for k in list(nzb_options.keys())[start : 10 + start]:
            buttons.data_button(k, f"botset nzbvar {k}")
        buttons.data_button("Edit" if state == "view" else "View", f"botset {'edit' if state == 'view' else 'view'} nzb")
        buttons.data_button("Servers", "botset nzbserver")
        buttons.data_button("Sync Sabnzbd", "botset syncnzb")
        buttons.data_button("Back", "botset back")
        buttons.data_button("Close", "botset close")
        for x in range(0, len(nzb_options), 10):
            buttons.data_button(f"{int(x / 10)}", f"botset start nzb {x}", position="footer")
        msg = f"Sabnzbd Options | Page: {int(start / 10)} | State: {state}"
    elif key == "nzbserver":
        if Config.USENET_SERVERS:
            for index, k in enumerate(Config.USENET_SERVERS[start : 10 + start], start=start):
                buttons.data_button(k["name"], f"botset nzbser{index}")
        buttons.data_button("Add New", "botset nzbsevar newser")
        buttons.data_button("Back", "botset nzb")
        buttons.data_button("Close", "botset close")
        if len(Config.USENET_SERVERS) > 10:
            for x in range(0, len(Config.USENET_SERVERS), 10):
                buttons.data_button(f"{int(x / 10)}", f"botset start nzbserver {x}", position="footer")
        msg = f"Usenet Servers | Page: {int(start / 10)} | State: {state}"
    elif key.startswith("nzbser"):
        index = int(key.replace("nzbser", ""))
        for k in list(Config.USENET_SERVERS[index].keys())[start : 10 + start]:
            buttons.data_button(k, f"botset nzbsevar{index} {k}")
        buttons.data_button("Edit" if state == "view" else "View", f"botset {'edit' if state == 'view' else 'view'} {key}")
        buttons.data_button("Remove Server", f"botset remser {index}")
        buttons.data_button("Back", "botset nzbserver")
        buttons.data_button("Close", "botset close")
        if len(Config.USENET_SERVERS[index]) > 10:
            for x in range(0, len(Config.USENET_SERVERS[index]), 10):
                buttons.data_button(f"{int(x / 10)}", f"botset start {key} {x}", position="footer")
        msg = f"Server Keys | Page: {int(start / 10)} | State: {state}"

    return msg, buttons.build_menu(1 if key is None else 2)


async def update_buttons(message, key=None, edit_type=None):
    msg, button = await get_buttons(key, edit_type)
    await edit_message(message, msg, button)


@new_task
async def edit_variable(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = str(message.text)
    try:
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
            if key == "INCOMPLETE_TASK_NOTIFIER" and Config.DATABASE_URL:
                await database.trunc_table("tasks")
        elif key == "STATUS_UPDATE_INTERVAL":
            value = int(value)
            if task_dict and (st := intervals["status"]):
                for cid, intvl in list(st.items()):
                    intvl.cancel()
                    intervals["status"][cid] = SetInterval(value, update_status_message, cid)
        elif key == "TORRENT_TIMEOUT":
            await TorrentManager.change_aria2_option("bt-stop-timeout", value)
            value = int(value)
        elif key == "LEECH_SPLIT_SIZE":
            value = min(int(value), TgClient.MAX_SPLIT_SIZE)
        elif key == "BASE_URL_PORT":
            value = int(value)
            if Config.BASE_URL:
                await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
                await _start_web_server(value)
        elif key == "EXCLUDED_EXTENSIONS":
            excluded_extensions.clear()
            excluded_extensions.extend(["aria2", "!qB"])
            excluded_extensions.extend(x.lstrip(".").strip().lower() for x in value.split())
        elif key == "INCLUDED_EXTENSIONS":
            included_extensions.clear()
            included_extensions.extend(x.lstrip(".").strip().lower() for x in value.split())
        elif key == "GDRIVE_ID":
            if drives_names and drives_names[0] == "Main":
                drives_ids[0] = value
            else:
                drives_names.insert(0, "Main")
                drives_ids.insert(0, value)
                index_urls.insert(0, Config.INDEX_URL)
        elif key == "INDEX_URL":
            if drives_names and drives_names[0] == "Main":
                index_urls[0] = value
        elif key == "AUTHORIZED_CHATS":
            auth_chats.clear()
            for id_ in value.split():
                chat_id, *thread_ids = id_.split("|")
                chat_id = int(chat_id.strip())
                auth_chats[chat_id] = [int(x.strip()) for x in thread_ids] if thread_ids else []
        elif key == "SUDO_USERS":
            sudo_users.clear()
            sudo_users.extend(int(id_.strip()) for id_ in value.split())
        elif value.isdigit():
            value = int(value)
        elif value.startswith("[") and value.endswith("]"):
            value = _safe_literal(value, list)
        elif value.startswith("{") and value.endswith("}"):
            value = _safe_literal(value, dict)
    except (ValueError, SyntaxError) as exc:
        await send_message(message, f"Invalid value: {exc}")
        await update_buttons(pre_message, "var")
        return
    Config.set(key, value)
    await update_buttons(pre_message, "var")
    await delete_message(message)
    await database.update_config({key: value})
    if key in ["SEARCH_PLUGINS", "SEARCH_API_LINK"]:
        await initiate_search_tools()
    elif key in ["QUEUE_ALL", "QUEUE_DOWNLOAD", "QUEUE_UPLOAD"]:
        await start_from_queued()
    elif key in ["RCLONE_SERVE_URL", "RCLONE_SERVE_PORT", "RCLONE_SERVE_USER", "RCLONE_SERVE_PASS"]:
        await rclone_serve_booter()
    elif key in ["JD_EMAIL", "JD_PASS"]:
        await jdownloader.boot()
    elif key == "RSS_DELAY":
        add_job()
    elif key == "USENET_SERVERS":
        for server in value:
            await sabnzbd_client.set_special_config("servers", server)


@new_task
async def edit_aria(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = str(message.text)
    if key == "newkey":
        if ":" not in value:
            await send_message(message, "Use key:value format")
            return
        key, value = [x.strip() for x in value.split(":", 1)]
    elif value.lower() in {"true", "false"}:
        value = value.lower()
    await TorrentManager.change_aria2_option(key, value)
    await update_buttons(pre_message, "aria")
    await delete_message(message)
    await database.update_aria2(key, value)


@new_task
async def edit_qbit(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = str(message.text)
    if value.lower() == "true":
        value = True
    elif value.lower() == "false":
        value = False
    elif key == "max_ratio":
        value = float(value)
    elif value.isdigit():
        value = int(value)
    await TorrentManager.qbittorrent.app.set_preferences({key: value})
    qbit_options[key] = value
    await update_buttons(pre_message, "qbit")
    await delete_message(message)
    await database.update_qbittorrent(key, value)


@new_task
async def edit_nzb(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = str(message.text)
    if value.isdigit():
        value = int(value)
    elif value.startswith("[") and value.endswith("]"):
        try:
            parsed = _safe_literal(value, list)
            value = ",".join(str(x) for x in parsed)
        except (ValueError, SyntaxError) as exc:
            LOGGER.error(exc)
            await send_message(message, f"Invalid list: {exc}")
            await update_buttons(pre_message, "nzb")
            return
    res = await sabnzbd_client.set_config("misc", key, value)
    nzb_options[key] = res["config"]["misc"][key]
    await update_buttons(pre_message, "nzb")
    await delete_message(message)
    await database.update_nzb_config()


@new_task
async def edit_nzb_server(_, message, pre_message, key, index=0):
    handler_dict[message.chat.id] = False
    value = str(message.text)
    if key == "newser":
        try:
            value = _safe_literal(value, dict)
        except (ValueError, SyntaxError):
            await send_message(message, "Invalid dict format!")
            await update_buttons(pre_message, "nzbserver")
            return
        res = await sabnzbd_client.add_server(value)
        if not res["config"]["servers"][0]["host"]:
            await send_message(message, "Invalid server!")
            await update_buttons(pre_message, "nzbserver")
            return
        Config.USENET_SERVERS.append(value)
        await update_buttons(pre_message, "nzbserver")
    else:
        if value.isdigit():
            value = int(value)
        res = await sabnzbd_client.add_server({"name": Config.USENET_SERVERS[index]["name"], key: value})
        if res["config"]["servers"][0][key] == "":
            await send_message(message, "Invalid value")
            return
        Config.USENET_SERVERS[index][key] = value
        await update_buttons(pre_message, f"nzbser{index}")
    await delete_message(message)
    await database.update_config({"USENET_SERVERS": Config.USENET_SERVERS})


async def sync_jdownloader():
    async with jd_listener_lock:
        if not Config.DATABASE_URL or not jdownloader.is_connected:
            return
        await jdownloader.device.system.exit_jd()
    if await aiopath.exists("cfg.zip"):
        await remove("cfg.zip")
    code = await (await create_subprocess_exec("7z", "a", "cfg.zip", "/JDownloader/cfg")).wait()
    if code != 0:
        raise RuntimeError(f"Failed to archive JDownloader config (exit {code})")
    await database.update_private_file("cfg.zip")


@new_task
async def update_private_file(_, message, pre_message):
    handler_dict[message.chat.id] = False
    file_name = None
    if not message.media and (file_name := str(message.text)):
        if await aiopath.isfile(file_name) and file_name != "config.py":
            await remove(file_name)
        if file_name == "accounts.zip":
            if await aiopath.exists("accounts"):
                await rmtree("accounts", ignore_errors=True)
            if await aiopath.exists("rclone_sa"):
                await rmtree("rclone_sa", ignore_errors=True)
            Config.USE_SERVICE_ACCOUNTS = False
            await database.update_config({"USE_SERVICE_ACCOUNTS": False})
        elif file_name in {".netrc", "netrc"}:
            async with aiopen(".netrc", "w"):
                pass
            chmod(".netrc", 0o600)
            await (await create_subprocess_exec("cp", ".netrc", "/root/.netrc")).wait()
        await delete_message(message)
    elif doc := message.document:
        file_name = doc.file_name
        fpath = f"{getcwd()}/{file_name}"
        if await aiopath.exists(fpath):
            await remove(fpath)
        await message.download(file_name=fpath)
        if file_name in {"token.pickle", "rclone.conf", ".netrc", "netrc", "cookies.txt"}:
            chmod(fpath, 0o600)
        if file_name == "accounts.zip":
            if await aiopath.exists("accounts"):
                await rmtree("accounts", ignore_errors=True)
            if await aiopath.exists("rclone_sa"):
                await rmtree("rclone_sa", ignore_errors=True)
            code = await (await create_subprocess_exec("7z", "x", "-o.", "-aoa", "accounts.zip", "accounts/*.json")).wait()
            if code != 0:
                raise RuntimeError(f"Failed to extract accounts.zip (exit {code})")
            await (await create_subprocess_exec("chmod", "-R", "700", "accounts")).wait()
        elif file_name == "list_drives.txt":
            drives_ids.clear()
            drives_names.clear()
            index_urls.clear()
            if Config.GDRIVE_ID:
                drives_names.append("Main")
                drives_ids.append(Config.GDRIVE_ID)
                index_urls.append(Config.INDEX_URL)
            async with aiopen("list_drives.txt", "r+") as f:
                lines = await f.readlines()
                for line_no, line in enumerate(lines, start=1):
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    temp = stripped.split()
                    if len(temp) < 2:
                        LOGGER.warning(f"Skipping malformed list_drives.txt line {line_no}: {stripped}")
                        continue
                    drives_ids.append(temp[1])
                    drives_names.append(temp[0].replace("_", " "))
                    index_urls.append(temp[2] if len(temp) > 2 else "")
        elif file_name in [".netrc", "netrc"]:
            if file_name == "netrc":
                await rename("netrc", ".netrc")
                file_name = ".netrc"
            chmod(".netrc", 0o600)
            await (await create_subprocess_exec("cp", ".netrc", "/root/.netrc")).wait()
        elif file_name == "config.py":
            await load_config()
        if "@github.com" in Config.UPSTREAM_REPO:
            buttons = ButtonMaker()
            buttons.data_button("Yes!", f"botset push {file_name}")
            buttons.data_button("No", "botset close")
            await send_message(message, "Push to UPSTREAM_REPO ?", buttons.build_menu(2))
        else:
            await delete_message(message)
    if not file_name:
        return
    if file_name == "rclone.conf":
        await rclone_serve_booter()
    await update_buttons(pre_message)
    await database.update_private_file(file_name)


async def event_handler(client, query, pfunc, rfunc, document=False):
    chat_id = query.message.chat.id
    handler_dict[chat_id] = True
    start_time = time()

    async def event_filter(_, __, event):
        user = event.from_user or event.sender_chat
        return bool(user.id == query.from_user.id and event.chat.id == chat_id and (event.text or event.document and document))

    handler = client.add_handler(MessageHandler(pfunc, filters=create(event_filter)), group=-1)
    while handler_dict[chat_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[chat_id] = False
            await rfunc()
    client.remove_handler(*handler)


async def _git_push_private(filename):
    if not Config.UPSTREAM_BRANCH or any(ch.isspace() for ch in Config.UPSTREAM_BRANCH):
        raise ValueError("Invalid upstream branch")
    if await aiopath.exists(filename):
        commands = [
            ["git", "add", "-f", "--", filename],
            ["git", "commit", "-sm", "botsettings", "-q"],
            ["git", "push", "origin", Config.UPSTREAM_BRANCH, "-qf"],
        ]
    else:
        commands = [
            ["git", "rm", "-r", "--cached", "--", filename],
            ["git", "commit", "-sm", "botsettings", "-q"],
            ["git", "push", "origin", Config.UPSTREAM_BRANCH, "-qf"],
        ]
    for command in commands:
        code = await (await create_subprocess_exec(*command)).wait()
        if code != 0:
            raise RuntimeError(f"Command failed: {command[0]} {command[1]}")


@new_task
async def edit_bot_settings(client, query):
    data = query.data.split()
    message = query.message
    handler_dict[message.chat.id] = False
    if len(data) < 2:
        await query.answer("Invalid settings action", show_alert=True)
        return
    if data[1] == "close":
        await query.answer()
        await delete_message(message.reply_to_message)
        await delete_message(message)
    elif data[1] == "back":
        await query.answer()
        globals()["start"] = 0
        await update_buttons(message)
    elif data[1] == "syncjd":
        if not Config.JD_EMAIL or not Config.JD_PASS:
            await query.answer("No Email or Password provided!", show_alert=True)
            return
        await query.answer("Synchronization Started. JDownloader will get restarted.", show_alert=True)
        await sync_jdownloader()
    elif data[1] in ["var", "aria", "qbit", "nzb", "nzbserver"] or data[1].startswith("nzbser"):
        if data[1] == "nzbserver":
            globals()["start"] = 0
        await query.answer()
        await update_buttons(message, data[1])
    elif data[1] == "resetvar":
        await query.answer()
        expected_type = type(getattr(Config, data[2]))
        value = {bool: False, int: 0, str: "", list: [], dict: {}}.get(expected_type, "")
        if data[2] in DEFAULT_VALUES:
            value = DEFAULT_VALUES[data[2]]
            if data[2] == "STATUS_UPDATE_INTERVAL" and task_dict and (st := intervals["status"]):
                for key, intvl in list(st.items()):
                    intvl.cancel()
                    intervals["status"][key] = SetInterval(value, update_status_message, key)
        elif data[2] == "EXCLUDED_EXTENSIONS":
            excluded_extensions.clear()
            excluded_extensions.extend(["aria2", "!qB"])
        elif data[2] == "INCLUDED_EXTENSIONS":
            included_extensions.clear()
        elif data[2] == "TORRENT_TIMEOUT":
            await TorrentManager.change_aria2_option("bt-stop-timeout", "0")
            await database.update_aria2("bt-stop-timeout", "0")
        elif data[2] == "BASE_URL":
            await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
        elif data[2] == "BASE_URL_PORT":
            value = 80
            if Config.BASE_URL:
                await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
                await _start_web_server(value)
        elif data[2] == "GDRIVE_ID":
            if drives_names and drives_names[0] == "Main":
                drives_names.pop(0); drives_ids.pop(0); index_urls.pop(0)
        elif data[2] == "INDEX_URL" and drives_names and drives_names[0] == "Main":
            index_urls[0] = ""
        elif data[2] == "INCOMPLETE_TASK_NOTIFIER":
            await database.trunc_table("tasks")
        elif data[2] in ["JD_EMAIL", "JD_PASS"]:
            await (await create_subprocess_exec("pkill", "-9", "-f", "java")).wait()
        elif data[2] == "USENET_SERVERS":
            for server in Config.USENET_SERVERS:
                await sabnzbd_client.delete_config("servers", server["name"])
        elif data[2] == "AUTHORIZED_CHATS":
            auth_chats.clear()
        elif data[2] == "SUDO_USERS":
            sudo_users.clear()
        Config.set(data[2], value)
        await update_buttons(message, "var")
        if data[2] == "DATABASE_URL":
            await database.disconnect()
        await database.update_config({data[2]: value})
        if data[2] in ["SEARCH_PLUGINS", "SEARCH_API_LINK"]:
            await initiate_search_tools()
        elif data[2] in ["QUEUE_ALL", "QUEUE_DOWNLOAD", "QUEUE_UPLOAD"]:
            await start_from_queued()
        elif data[2] in ["RCLONE_SERVE_URL", "RCLONE_SERVE_PORT", "RCLONE_SERVE_USER", "RCLONE_SERVE_PASS"]:
            await rclone_serve_booter()
    elif data[1] == "resetnzb":
        await query.answer(); res = await sabnzbd_client.set_config_default(data[2]); nzb_options[data[2]] = res["config"]["misc"][data[2]]; await update_buttons(message, "nzb"); await database.update_nzb_config()
    elif data[1] == "syncnzb":
        await query.answer("Synchronization Started.", show_alert=True); nzb_options.clear(); await update_nzb_options(); await database.update_nzb_config()
    elif data[1] == "syncqbit":
        await query.answer("Synchronization Started.", show_alert=True); qbit_options.clear(); await update_qb_options(); await database.save_qbit_settings()
    elif data[1] == "emptyaria":
        await query.answer(); aria2_options[data[2]] = ""; await update_buttons(message, "aria"); await TorrentManager.change_aria2_option(data[2], ""); await database.update_aria2(data[2], "")
    elif data[1] == "emptyqbit":
        await query.answer(); await TorrentManager.qbittorrent.app.set_preferences({data[2]: ""}); qbit_options[data[2]] = ""; await update_buttons(message, "qbit"); await database.update_qbittorrent(data[2], "")
    elif data[1] == "emptynzb":
        await query.answer(); res = await sabnzbd_client.set_config("misc", data[2], ""); nzb_options[data[2]] = res["config"]["misc"][data[2]]; await update_buttons(message, "nzb"); await database.update_nzb_config()
    elif data[1] == "remser":
        index = int(data[2]); await sabnzbd_client.delete_config("servers", Config.USENET_SERVERS[index]["name"]); del Config.USENET_SERVERS[index]; await update_buttons(message, "nzbserver"); await database.update_config({"USENET_SERVERS": Config.USENET_SERVERS})
    elif data[1] == "private":
        await query.answer(); await update_buttons(message, "private"); await event_handler(client, query, partial(update_private_file, pre_message=message), partial(update_buttons, message), True)
    elif data[1] == "botvar" and state == "edit":
        await query.answer(); await update_buttons(message, data[2], data[1]); await event_handler(client, query, partial(edit_variable, pre_message=message, key=data[2]), partial(update_buttons, message, "var"))
    elif data[1] == "botvar" and state == "view":
        value = f"{Config.get(data[2])}"; await query.answer((value[:200] if value else "None"), show_alert=True)
    elif data[1] == "ariavar" and (state == "edit" or data[2] == "newkey"):
        await query.answer(); await update_buttons(message, data[2], data[1]); await event_handler(client, query, partial(edit_aria, pre_message=message, key=data[2]), partial(update_buttons, message, "aria"))
    elif data[1] == "ariavar" and state == "view":
        value = f"{aria2_options[data[2]]}"; await query.answer(value[:200] or "None", show_alert=True)
    elif data[1] == "qbitvar" and state == "edit":
        await query.answer(); await update_buttons(message, data[2], data[1]); await event_handler(client, query, partial(edit_qbit, pre_message=message, key=data[2]), partial(update_buttons, message, "qbit"))
    elif data[1] == "qbitvar" and state == "view":
        value = f"{qbit_options[data[2]]}"; await query.answer(value[:200] or "None", show_alert=True)
    elif data[1] == "nzbvar" and state == "edit":
        await query.answer(); await update_buttons(message, data[2], data[1]); await event_handler(client, query, partial(edit_nzb, pre_message=message, key=data[2]), partial(update_buttons, message, "nzb"))
    elif data[1] == "nzbvar" and state == "view":
        value = f"{nzb_options[data[2]]}"; await query.answer(value[:200] or "None", show_alert=True)
    elif data[1] == "emptyserkey":
        await query.answer(); index = int(data[2]); res = await sabnzbd_client.add_server({"name": Config.USENET_SERVERS[index]["name"], data[3]: ""}); Config.USENET_SERVERS[index][data[3]] = res["config"]["servers"][0][data[3]]; await update_buttons(message, f"nzbser{data[2]}"); await database.update_config({"USENET_SERVERS": Config.USENET_SERVERS})
    elif data[1].startswith("nzbsevar") and (state == "edit" or data[2] == "newser"):
        index = 0 if data[2] == "newser" else int(data[1].replace("nzbsevar", "")); await query.answer(); await update_buttons(message, data[2], data[1]); await event_handler(client, query, partial(edit_nzb_server, pre_message=message, key=data[2], index=index), partial(update_buttons, message, f"nzbser{index}" if data[2] != "newser" else "nzbserver"))
    elif data[1].startswith("nzbsevar") and state == "view":
        index = int(data[1].replace("nzbsevar", "")); value = f"{Config.USENET_SERVERS[index][data[2]]}"; await query.answer(value[:200] or "None", show_alert=True)
    elif data[1] == "edit":
        await query.answer(); globals()["state"] = "edit"; await update_buttons(message, data[2])
    elif data[1] == "view":
        await query.answer(); globals()["state"] = "view"; await update_buttons(message, data[2])
    elif data[1] == "start":
        await query.answer(); globals()["start"] = int(data[3]); await update_buttons(message, data[2])
    elif data[1] == "push":
        await query.answer()
        filename = data[2].rsplit(".zip", 1)[0]
        try:
            await _git_push_private(filename)
        except Exception as exc:
            LOGGER.error(f"Private-file push failed: {exc}")
            await query.answer("Git push failed; check logs.", show_alert=True)
            return
        await delete_message(message.reply_to_message)
        await delete_message(message)


@new_task
async def send_bot_settings(_, message):
    handler_dict[message.chat.id] = False
    msg, button = await get_buttons()
    globals()["start"] = 0
    await send_message(message, msg, button)


async def load_config():
    Config.load()
    drives_ids.clear(); drives_names.clear(); index_urls.clear()
    await update_variables()
    if not await aiopath.exists("accounts"):
        Config.USE_SERVICE_ACCOUNTS = False
    if task_dict and (st := intervals["status"]):
        for key, intvl in list(st.items()):
            intvl.cancel()
            intervals["status"][key] = SetInterval(Config.STATUS_UPDATE_INTERVAL, update_status_message, key)
    if Config.TORRENT_TIMEOUT:
        await TorrentManager.change_aria2_option("bt-stop-timeout", f"{Config.TORRENT_TIMEOUT}")
        await database.update_aria2("bt-stop-timeout", f"{Config.TORRENT_TIMEOUT}")
    if not Config.INCOMPLETE_TASK_NOTIFIER:
        await database.trunc_table("tasks")
    await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
    if Config.BASE_URL:
        await _start_web_server(Config.BASE_URL_PORT)
    if Config.DATABASE_URL:
        await database.connect()
        await database.update_config(Config.get_all())
    else:
        await database.disconnect()
    await gather(initiate_search_tools(), start_from_queued(), rclone_serve_booter())
    add_job()
