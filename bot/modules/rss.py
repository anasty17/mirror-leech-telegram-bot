from httpx import AsyncClient
from apscheduler.triggers.interval import IntervalTrigger
from asyncio import Lock, sleep
from datetime import datetime, timedelta
from feedparser import parse as feed_parse
from functools import partial
from io import BytesIO
from pyrogram.filters import create
from pyrogram.handlers import MessageHandler
from time import time
from re import compile, I

from .. import scheduler, rss_dict, LOGGER
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import new_task, arg_parser, get_size_bytes
from ..helper.ext_utils.status_utils import get_readable_file_size
from ..helper.ext_utils.db_handler import database
from ..helper.ext_utils.exceptions import RssShutdownException
from ..helper.ext_utils.help_messages import RSS_HELP_MESSAGE
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import (
    send_message,
    edit_message,
    send_rss,
    send_file,
    delete_message,
)

rss_dict_lock = Lock()
handler_dict = {}
size_regex = compile(r"(\d+(\.\d+)?\s?(GB|MB|KB|GiB|MiB|KiB))", I)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def rss_menu(event):
    user_id = event.from_user.id
    buttons = ButtonMaker()
    buttons.data_button("Subscribe", f"rss sub {user_id}")
    buttons.data_button("Subscriptions", f"rss list {user_id} 0")
    buttons.data_button("Get Items", f"rss get {user_id}")
    buttons.data_button("Edit", f"rss edit {user_id}")
    buttons.data_button("Pause", f"rss pause {user_id}")
    buttons.data_button("Resume", f"rss resume {user_id}")
    buttons.data_button("Unsubscribe", f"rss unsubscribe {user_id}")
    if await CustomFilters.sudo("", event):
        buttons.data_button("All Subscriptions", f"rss listall {user_id} 0")
        buttons.data_button("Pause All", f"rss allpause {user_id}")
        buttons.data_button("Resume All", f"rss allresume {user_id}")
        buttons.data_button("Unsubscribe All", f"rss allunsub {user_id}")
        buttons.data_button("Delete User", f"rss deluser {user_id}")
        if scheduler.running:
            buttons.data_button("Shutdown Rss", f"rss shutdown {user_id}")
        else:
            buttons.data_button("Start Rss", f"rss start {user_id}")
    buttons.data_button("Close", f"rss close {user_id}")
    button = buttons.build_menu(2)
    msg = f"Rss Menu | Users: {len(rss_dict)} | Running: {scheduler.running}"
    return msg, button


async def update_rss_menu(query):
    msg, button = await rss_menu(query)
    await edit_message(query.message, msg, button)


@new_task
async def get_rss_menu(_, message):
    msg, button = await rss_menu(message)
    await send_message(message, msg, button)


@new_task
async def rss_sub(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention
    msg = ""
    items = message.text.split("\n")
    for index, item in enumerate(items, start=1):
        args = item.split()
        if len(args) < 2:
            await send_message(
                message,
                f"{item}. Wrong Input format. Read help message before adding new subcription!",
            )
            continue
        title = args[0].strip()
        if (user_feeds := rss_dict.get(user_id, False)) and title in user_feeds:
            await send_message(
                message, f"This title {title} already subscribed! Choose another title!"
            )
            continue
        feed_link = args[1].strip()
        if feed_link.startswith(("-inf", "-exf", "-c")):
            await send_message(
                message,
                f"Wrong input in line {index}! Add Title! Read the example!",
            )
            continue
        inf_lists = []
        exf_lists = []
        if len(args) > 2:
            arg_base = {"-c": None, "-inf": None, "-exf": None, "-stv": None}
            arg_parser(args[2:], arg_base)
            cmd = arg_base["-c"]
            inf = arg_base["-inf"]
            exf = arg_base["-exf"]
            stv = arg_base["-stv"]
            if stv is not None:
                stv = stv.lower() == "true"
            if inf is not None:
                filters_list = inf.split("|")
                for x in filters_list:
                    y = x.split(" or ")
                    inf_lists.append(y)
            if exf is not None:
                filters_list = exf.split("|")
                for x in filters_list:
                    y = x.split(" or ")
                    exf_lists.append(y)
        else:
            inf = None
            exf = None
            cmd = None
            stv = False
        try:
            async with AsyncClient(
                headers=headers, follow_redirects=True, timeout=60, verify=False
            ) as client:
                res = await client.get(feed_link)
            html = res.text
            rss_d = feed_parse(html)
            last_title = rss_d.entries[0]["title"]
            if rss_d.entries[0].get("size"):
                size = int(rss_d.entries[0]["size"])
            elif rss_d.entries[0].get("summary"):
                summary = rss_d.entries[0]["summary"]
                matches = size_regex.findall(summary)
                sizes = [match[0] for match in matches]
                size = get_size_bytes(sizes[0])
            else:
                size = 0
            msg += "<b>Subscribed!</b>"
            msg += f"\n<b>Title: </b><code>{title}</code>\n<b>Feed Url: </b>{feed_link}"
            msg += f"\n<b>latest record for </b>{rss_d.feed.title}:"
            msg += (
                f"\nName: <code>{last_title.replace('>', '').replace('<', '')}</code>"
            )
            try:
                last_link = rss_d.entries[0]["links"][1]["href"]
            except IndexError:
                last_link = rss_d.entries[0]["link"]
            msg += f"\n<b>Link: </b><code>{last_link}</code>"
            if size:
                msg += f"\nSize: {get_readable_file_size(size)}"
            msg += f"\n<b>Command: </b><code>{cmd}</code>"
            msg += f"\n<b>Filters:-</b>\ninf: <code>{inf}</code>\nexf: <code>{exf}</code>\n<b>sensitive: </b>{stv}"
            async with rss_dict_lock:
                if rss_dict.get(user_id, False):
                    rss_dict[user_id][title] = {
                        "link": feed_link,
                        "last_feed": last_link,
                        "last_title": last_title,
                        "inf": inf_lists,
                        "exf": exf_lists,
                        "paused": False,
                        "command": cmd,
                        "sensitive": stv,
                        "tag": tag,
                    }
                else:
                    rss_dict[user_id] = {
                        title: {
                            "link": feed_link,
                            "last_feed": last_link,
                            "last_title": last_title,
                            "inf": inf_lists,
                            "exf": exf_lists,
                            "paused": False,
                            "command": cmd,
                            "sensitive": stv,
                            "tag": tag,
                        }
                    }
            LOGGER.info(
                f"Rss Feed Added: id: {user_id} - title: {title} - link: {feed_link} - c: {cmd} - inf: {inf} - exf: {exf} - stv {stv}"
            )
        except (IndexError, AttributeError) as e:
            emsg = f"The link: {feed_link} doesn't seem to be a RSS feed or it's region-blocked!"
            await send_message(message, emsg + "\nError: " + str(e))
        except Exception as e:
            await send_message(message, str(e))
    if msg:
        await database.rss_update(user_id)
        await send_message(message, msg)
        is_sudo = await CustomFilters.sudo("", message)
        if scheduler.state == 2:
            scheduler.resume()
        elif is_sudo and not scheduler.running:
            add_job()
            scheduler.start()
    await update_rss_menu(pre_event)


async def get_user_id(title):
    async with rss_dict_lock:
        return next(
            (
                (True, user_id)
                for user_id, feed in rss_dict.items()
                if feed["title"] == title
            ),
            (False, False),
        )


@new_task
async def rss_update(_, message, pre_event, state):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    titles = message.text.split()
    is_sudo = await CustomFilters.sudo("", message)
    updated = []
    for title in titles:
        title = title.strip()
        if not (res := rss_dict[user_id].get(title, False)):
            if is_sudo:
                res, user_id = await get_user_id(title)
            if not res:
                user_id = message.from_user.id
                await send_message(message, f"{title} not found!")
                continue
        istate = rss_dict[user_id][title].get("paused", False)
        if istate and state == "pause" or not istate and state == "resume":
            await send_message(message, f"{title} already {state}d!")
            continue
        async with rss_dict_lock:
            updated.append(title)
            if state == "unsubscribe":
                del rss_dict[user_id][title]
            elif state == "pause":
                rss_dict[user_id][title]["paused"] = True
            elif state == "resume":
                rss_dict[user_id][title]["paused"] = False
        if state == "resume":
            if scheduler.state == 2:
                scheduler.resume()
            elif is_sudo and not scheduler.running:
                add_job()
                scheduler.start()
        if is_sudo and Config.DATABASE_URL and user_id != message.from_user.id:
            await database.rss_update(user_id)
        if not rss_dict[user_id]:
            async with rss_dict_lock:
                del rss_dict[user_id]
            await database.rss_delete(user_id)
            if not rss_dict:
                await database.trunc_table("rss")
    if updated:
        LOGGER.info(f"Rss link with Title(s): {updated} has been {state}d!")
        await send_message(
            message,
            f"Rss links with Title(s): <code>{updated}</code> has been {state}d!",
        )
        if rss_dict.get(user_id):
            await database.rss_update(user_id)
    await update_rss_menu(pre_event)


async def rss_list(query, start, all_users=False):
    user_id = query.from_user.id
    buttons = ButtonMaker()
    if all_users:
        list_feed = f"<b>All subscriptions | Page: {int(start / 5)} </b>"
        async with rss_dict_lock:
            keysCount = sum(len(v.keys()) for v in rss_dict.values())
            index = 0
            for titles in rss_dict.values():
                for index, (title, data) in enumerate(
                    list(titles.items())[start : 5 + start]
                ):
                    list_feed += f"\n\n<b>Title:</b> <code>{title}</code>\n"
                    list_feed += f"<b>Feed Url:</b> <code>{data['link']}</code>\n"
                    list_feed += f"<b>Command:</b> <code>{data['command']}</code>\n"
                    list_feed += f"<b>Inf:</b> <code>{data['inf']}</code>\n"
                    list_feed += f"<b>Exf:</b> <code>{data['exf']}</code>\n"
                    list_feed += f"<b>Sensitive:</b> <code>{data.get('sensitive', False)}</code>\n"
                    list_feed += f"<b>Paused:</b> <code>{data['paused']}</code>\n"
                    list_feed += f"<b>User:</b> {data['tag'].replace('@', '', 1)}"
                    index += 1
                    if index == 5:
                        break
    else:
        list_feed = f"<b>Your subscriptions | Page: {int(start / 5)} </b>"
        async with rss_dict_lock:
            keysCount = len(rss_dict.get(user_id, {}).keys())
            for title, data in list(rss_dict[user_id].items())[start : 5 + start]:
                list_feed += f"\n\n<b>Title:</b> <code>{title}</code>\n<b>Feed Url: </b><code>{data['link']}</code>\n"
                list_feed += f"<b>Command:</b> <code>{data['command']}</code>\n"
                list_feed += f"<b>Inf:</b> <code>{data['inf']}</code>\n"
                list_feed += f"<b>Exf:</b> <code>{data['exf']}</code>\n"
                list_feed += (
                    f"<b>Sensitive:</b> <code>{data.get('sensitive', False)}</code>\n"
                )
                list_feed += f"<b>Paused:</b> <code>{data['paused']}</code>\n"
    buttons.data_button("Back", f"rss back {user_id}")
    buttons.data_button("Close", f"rss close {user_id}")
    if keysCount > 5:
        for x in range(0, keysCount, 5):
            buttons.data_button(
                f"{int(x / 5)}", f"rss list {user_id} {x}", position="footer"
            )
    button = buttons.build_menu(2)
    if query.message.text.html == list_feed:
        return
    await edit_message(query.message, list_feed, button)


@new_task
async def rss_get(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    args = message.text.split()
    if len(args) < 2:
        await send_message(
            message,
            f"{args}. Wrong Input format. You should add number of the items you want to get. Read help message before adding new subcription!",
        )
        await update_rss_menu(pre_event)
        return
    try:
        title = args[0]
        count = int(args[1])
        data = rss_dict[user_id].get(title, False)
        if data and count > 0:
            try:
                msg = await send_message(
                    message, f"Getting the last <b>{count}</b> item(s) from {title}"
                )
                async with AsyncClient(
                    headers=headers, follow_redirects=True, timeout=60, verify=False
                ) as client:
                    res = await client.get(data["link"])
                html = res.text
                rss_d = feed_parse(html)
                item_info = ""
                for item_num in range(count):
                    try:
                        link = rss_d.entries[item_num]["links"][1]["href"]
                    except IndexError:
                        link = rss_d.entries[item_num]["link"]
                    item_info += f"<b>Name: </b><code>{rss_d.entries[item_num]['title'].replace('>', '').replace('<', '')}</code>\n"
                    item_info += f"<b>Link: </b><code>{link}</code>\n\n"
                item_info_ecd = item_info.encode()
                if len(item_info_ecd) > 4000:
                    with BytesIO(item_info_ecd) as out_file:
                        out_file.name = f"rssGet {title} items_no. {count}.txt"
                        await send_file(message, out_file)
                    await delete_message(msg)
                else:
                    await edit_message(msg, item_info)
            except IndexError as e:
                LOGGER.error(str(e))
                await edit_message(
                    msg, "Parse depth exceeded. Try again with a lower value."
                )
            except Exception as e:
                LOGGER.error(str(e))
                await edit_message(msg, str(e))
        else:
            await send_message(message, "Enter a valid title. Title not found!")
    except Exception as e:
        LOGGER.error(str(e))
        await send_message(message, f"Enter a valid value!. {e}")
    await update_rss_menu(pre_event)


@new_task
async def rss_edit(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    items = message.text.split("\n")
    updated = False
    for item in items:
        args = item.split()
        title = args[0].strip()
        if len(args) < 2:
            await send_message(
                message,
                f"{item}. Wrong Input format. Read help message before editing!",
            )
            continue
        elif not rss_dict[user_id].get(title, False):
            await send_message(message, "Enter a valid title. Title not found!")
            continue
        updated = True
        inf_lists = []
        exf_lists = []
        arg_base = {"-c": None, "-inf": None, "-exf": None, "-stv": None}
        arg_parser(args[1:], arg_base)
        cmd = arg_base["-c"]
        inf = arg_base["-inf"]
        exf = arg_base["-exf"]
        stv = arg_base["-stv"]
        async with rss_dict_lock:
            if stv is not None:
                stv = stv.lower() == "true"
                rss_dict[user_id][title]["sensitive"] = stv
            if cmd is not None:
                if cmd.lower() == "none":
                    cmd = None
                rss_dict[user_id][title]["command"] = cmd
            if inf is not None:
                if inf.lower() != "none":
                    filters_list = inf.split("|")
                    for x in filters_list:
                        y = x.split(" or ")
                        inf_lists.append(y)
                rss_dict[user_id][title]["inf"] = inf_lists
            if exf is not None:
                if exf.lower() != "none":
                    filters_list = exf.split("|")
                    for x in filters_list:
                        y = x.split(" or ")
                        exf_lists.append(y)
                rss_dict[user_id][title]["exf"] = exf_lists
    if updated:
        await database.rss_update(user_id)
    await update_rss_menu(pre_event)


@new_task
async def rss_delete(_, message, pre_event):
    handler_dict[message.from_user.id] = False
    users = message.text.split()
    for user in users:
        user = int(user)
        async with rss_dict_lock:
            del rss_dict[user]
        await database.rss_delete(user)
    await update_rss_menu(pre_event)


async def event_handler(client, query, pfunc):
    user_id = query.from_user.id
    handler_dict[user_id] = True
    start_time = time()

    async def event_filter(_, __, event):
        user = event.from_user or event.sender_chat
        return bool(
            user.id == user_id and event.chat.id == query.message.chat.id and event.text
        )

    handler = client.add_handler(MessageHandler(pfunc, create(event_filter)), group=-1)
    while handler_dict[user_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[user_id] = False
            await update_rss_menu(query)
    client.remove_handler(*handler)


@new_task
async def rss_listener(client, query):
    user_id = query.from_user.id
    message = query.message
    data = query.data.split()
    if int(data[2]) != user_id and not await CustomFilters.sudo("", query):
        await query.answer(
            text="You don't have permission to use these buttons!", show_alert=True
        )
    elif data[1] == "close":
        await query.answer()
        handler_dict[user_id] = False
        await delete_message(message.reply_to_message)
        await delete_message(message)
    elif data[1] == "back":
        await query.answer()
        handler_dict[user_id] = False
        await update_rss_menu(query)
    elif data[1] == "sub":
        await query.answer()
        handler_dict[user_id] = False
        buttons = ButtonMaker()
        buttons.data_button("Back", f"rss back {user_id}")
        buttons.data_button("Close", f"rss close {user_id}")
        button = buttons.build_menu(2)
        await edit_message(message, RSS_HELP_MESSAGE, button)
        pfunc = partial(rss_sub, pre_event=query)
        await event_handler(client, query, pfunc)
    elif data[1] == "list":
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            start = int(data[3])
            await rss_list(query, start)
    elif data[1] == "get":
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.data_button("Back", f"rss back {user_id}")
            buttons.data_button("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            await edit_message(
                message,
                "Send one title with value separated by space get last X items.\nTitle Value\nTimeout: 60 sec.",
                button,
            )
            pfunc = partial(rss_get, pre_event=query)
            await event_handler(client, query, pfunc)
    elif data[1] in ["unsubscribe", "pause", "resume"]:
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.data_button("Back", f"rss back {user_id}")
            if data[1] == "pause":
                buttons.data_button("Pause AllMyFeeds", f"rss uallpause {user_id}")
            elif data[1] == "resume":
                buttons.data_button("Resume AllMyFeeds", f"rss uallresume {user_id}")
            elif data[1] == "unsubscribe":
                buttons.data_button("Unsub AllMyFeeds", f"rss uallunsub {user_id}")
            buttons.data_button("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            await edit_message(
                message,
                f"Send one or more rss titles separated by space to {data[1]}.\nTimeout: 60 sec.",
                button,
            )
            pfunc = partial(rss_update, pre_event=query, state=data[1])
            await event_handler(client, query, pfunc)
    elif data[1] == "edit":
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.data_button("Back", f"rss back {user_id}")
            buttons.data_button("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            msg = """Send one or more rss titles with new filters or command separated by new line.
Examples:
Title1 -c mirror -up remote:path/subdir -exf none -inf 1080 or 720 -stv true
Title2 -c none -inf none -stv false
Title3 -c mirror -rcf xxx -up xxx -z pswd -stv false
Note: Only what you provide will be edited, the rest will be the same like example 2: exf will stay same as it is.
Timeout: 60 sec. Argument -c for command and arguments
            """
            await edit_message(message, msg, button)
            pfunc = partial(rss_edit, pre_event=query)
            await event_handler(client, query, pfunc)
    elif data[1].startswith("uall"):
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
            return
        await query.answer()
        if data[1].endswith("unsub"):
            async with rss_dict_lock:
                del rss_dict[int(data[2])]
            await database.rss_delete(int(data[2]))
            await update_rss_menu(query)
        elif data[1].endswith("pause"):
            async with rss_dict_lock:
                for title in list(rss_dict[int(data[2])].keys()):
                    rss_dict[int(data[2])][title]["paused"] = True
            await database.rss_update(int(data[2]))
        elif data[1].endswith("resume"):
            async with rss_dict_lock:
                for title in list(rss_dict[int(data[2])].keys()):
                    rss_dict[int(data[2])][title]["paused"] = False
            if scheduler.state == 2:
                scheduler.resume()
            await database.rss_update(int(data[2]))
        await update_rss_menu(query)
    elif data[1].startswith("all"):
        if len(rss_dict) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
            return
        await query.answer()
        if data[1].endswith("unsub"):
            async with rss_dict_lock:
                rss_dict.clear()
            await database.trunc_table("rss")
            await update_rss_menu(query)
        elif data[1].endswith("pause"):
            async with rss_dict_lock:
                for user in list(rss_dict.keys()):
                    for title in list(rss_dict[user].keys()):
                        rss_dict[int(data[2])][title]["paused"] = True
            if scheduler.running:
                scheduler.pause()
            await database.rss_update_all()
        elif data[1].endswith("resume"):
            async with rss_dict_lock:
                for user in list(rss_dict.keys()):
                    for title in list(rss_dict[user].keys()):
                        rss_dict[int(data[2])][title]["paused"] = False
            if scheduler.state == 2:
                scheduler.resume()
            elif not scheduler.running:
                add_job()
                scheduler.start()
            await database.rss_update_all()
    elif data[1] == "deluser":
        if len(rss_dict) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.data_button("Back", f"rss back {user_id}")
            buttons.data_button("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            msg = "Send one or more user_id separated by space to delete their resources.\nTimeout: 60 sec."
            await edit_message(message, msg, button)
            pfunc = partial(rss_delete, pre_event=query)
            await event_handler(client, query, pfunc)
    elif data[1] == "listall":
        if not rss_dict:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            start = int(data[3])
            await rss_list(query, start, all_users=True)
    elif data[1] == "shutdown":
        if scheduler.running:
            await query.answer()
            scheduler.shutdown(wait=False)
            await sleep(0.5)
            await update_rss_menu(query)
        else:
            await query.answer(text="Already Stopped!", show_alert=True)
    elif data[1] == "start":
        if not scheduler.running:
            await query.answer()
            add_job()
            scheduler.start()
            await update_rss_menu(query)
        else:
            await query.answer(text="Already Running!", show_alert=True)


async def rss_monitor():
    chat = Config.RSS_CHAT
    if not chat:
        LOGGER.warning("RSS_CHAT not added! Shutting down rss scheduler...")
        scheduler.shutdown(wait=False)
        return
    if len(rss_dict) == 0:
        scheduler.pause()
        return
    all_paused = True
    rss_topic_id = rss_chat_id = None
    if isinstance(chat, int):
        rss_chat_id = chat
    elif "|" in chat:
        rss_chat_id, rss_topic_id = list(
            map(
                lambda x: int(x) if x.lstrip("-").isdigit() else x,
                chat.split("|", 1),
            )
        )
    elif chat.lstrip("-").isdigit():
        rss_chat_id = int(chat)
    for user, items in list(rss_dict.items()):
        for title, data in items.items():
            try:
                if data["paused"]:
                    continue
                tries = 0
                while True:
                    try:
                        async with AsyncClient(
                            headers=headers,
                            follow_redirects=True,
                            timeout=60,
                            verify=False,
                        ) as client:
                            res = await client.get(data["link"])
                        html = res.text
                        break
                    except:
                        tries += 1
                        if tries > 3:
                            raise
                        continue
                rss_d = feed_parse(html)
                try:
                    last_link = rss_d.entries[0]["links"][1]["href"]
                except IndexError:
                    last_link = rss_d.entries[0]["link"]
                finally:
                    all_paused = False
                last_title = rss_d.entries[0]["title"]
                if data["last_feed"] == last_link or data["last_title"] == last_title:
                    continue
                feed_count = 0
                while True:
                    try:
                        await sleep(10)
                    except:
                        raise RssShutdownException("Rss Monitor Stopped!")
                    try:
                        item_title = rss_d.entries[feed_count]["title"]
                        try:
                            url = rss_d.entries[feed_count]["links"][1]["href"]
                        except IndexError:
                            url = rss_d.entries[feed_count]["link"]
                        if data["last_feed"] == url or data["last_title"] == item_title:
                            break
                        if rss_d.entries[feed_count].get("size"):
                            size = int(rss_d.entries[feed_count]["size"])
                        elif rss_d.entries[feed_count].get("summary"):
                            summary = rss_d.entries[feed_count]["summary"]
                            matches = size_regex.findall(summary)
                            sizes = [match[0] for match in matches]
                            size = get_size_bytes(sizes[0])
                        else:
                            size = 0
                    except IndexError:
                        LOGGER.warning(
                            f"Reached Max index no. {feed_count} for this feed: {title}. Maybe you need to use less RSS_DELAY to not miss some torrents"
                        )
                        break
                    parse = True
                    for flist in data["inf"]:
                        if (
                            data.get("sensitive", False)
                            and all(x.lower() not in item_title.lower() for x in flist)
                        ) or (
                            not data.get("sensitive", False)
                            and all(x not in item_title for x in flist)
                        ):
                            parse = False
                            feed_count += 1
                            break
                    if not parse:
                        continue
                    for flist in data["exf"]:
                        if (
                            data.get("sensitive", False)
                            and any(x.lower() in item_title.lower() for x in flist)
                        ) or (
                            not data.get("sensitive", False)
                            and any(x in item_title for x in flist)
                        ):
                            parse = False
                            feed_count += 1
                            break
                    if not parse:
                        continue
                    if command := data["command"]:
                        if (
                            size
                            and Config.RSS_SIZE_LIMIT
                            and Config.RSS_SIZE_LIMIT < size
                        ):
                            feed_count += 1
                            continue
                        cmd = command.split(maxsplit=1)
                        cmd.insert(1, url)
                        feed_msg = " ".join(cmd)
                        if not feed_msg.startswith("/"):
                            feed_msg = f"/{feed_msg}"
                    else:
                        feed_msg = f"<b>Name: </b><code>{item_title.replace('>', '').replace('<', '')}</code>"
                        feed_msg += f"\n\n<b>Link: </b><code>{url}</code>"
                        if size:
                            feed_msg += f"\n<b>Size: </b>{get_readable_file_size(size)}"
                    feed_msg += (
                        f"\n<b>Tag: </b><code>{data['tag']}</code> <code>{user}</code>"
                    )
                    await send_rss(feed_msg, rss_chat_id, rss_topic_id)
                    feed_count += 1
                async with rss_dict_lock:
                    if user not in rss_dict or not rss_dict[user].get(title, False):
                        continue
                    rss_dict[user][title].update(
                        {"last_feed": last_link, "last_title": last_title}
                    )
                await database.rss_update(user)
                LOGGER.info(f"Feed Name: {title}")
                LOGGER.info(f"Last item: {last_link}")
            except RssShutdownException as ex:
                LOGGER.info(ex)
                break
            except Exception as e:
                LOGGER.error(f"{e} - Feed Name: {title} - Feed Link: {data['link']}")
                continue
    if all_paused:
        scheduler.pause()


def add_job():
    scheduler.add_job(
        rss_monitor,
        trigger=IntervalTrigger(seconds=Config.RSS_DELAY),
        id="0",
        name="RSS",
        misfire_grace_time=15,
        max_instances=1,
        next_run_time=datetime.now() + timedelta(seconds=20),
        replace_existing=True,
    )


add_job()
scheduler.start()
