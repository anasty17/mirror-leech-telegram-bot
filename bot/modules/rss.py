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
from ..core.telegram_manager import TgClient
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
SIZE_REGEX = compile(r"(\d+(\.\d+)?\s?(GB|MB|KB|GiB|MiB|KiB))", I)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

RSS_EDIT_HELP = """Send one or more rss titles with new filters or command separated by new line.
Examples:
Title1 -c mirror -up remote:path/subdir -exf none -inf 1080 or 720 -stv true
Title2 -c none -inf none -stv false
Title3 -c mirror -rcf xxx -up xxx -z pswd -stv false
Note: Only what you provide will be edited, the rest will be the same like example 2: exf will stay same as it is.
Timeout: 60 sec. Argument -c for command and arguments"""


def _find_command_filters(flt):
    """Recursively extract CommandFilter instances from a composite filter tree."""
    # Check if this filter has .commands (it's a CommandFilter)
    if hasattr(flt, "commands"):
        yield flt
    # Traverse AndFilter / OrFilter composites
    for attr in ("base", "other"):
        if child := getattr(flt, attr, None):
            yield from _find_command_filters(child)


def _build_command_map() -> dict:
    """Build a mapping from command name -> handler callback by inspecting
    the bot's registered message handlers.

    This stays in sync automatically — any handler registered via
    add_handler() is discovered here.
    """
    from pyrogram.handlers import MessageHandler

    mapping = {}
    for group in TgClient.bot.dispatcher.groups.values():
        for handler in group:
            if not isinstance(handler, MessageHandler):
                continue
            if handler.filters is None:
                continue
            for cmd_filter in _find_command_filters(handler.filters):
                for cmd in cmd_filter.commands:
                    mapping[cmd] = handler.callback
    return mapping


_command_map: dict | None = None


def _get_command_map() -> dict:
    global _command_map
    if _command_map is None:
        _command_map = _build_command_map()
    return _command_map


def _resolve_command(command_str: str):
    """Resolve a command string like 'ql -doc' into its handler function.

    Returns the handler function, or None if not recognized.
    Handles commands with or without CMD_SUFFIX.
    """
    cmd_name = command_str.strip().lstrip("/").split(maxsplit=1)[0]
    mapping = _get_command_map()
    handler = mapping.get(cmd_name)
    if handler is None and Config.CMD_SUFFIX:
        # Try with suffix appended (e.g. user stored "ql" but commands are "qlbot")
        handler = mapping.get(cmd_name + Config.CMD_SUFFIX)
    if handler is None:
        LOGGER.warning(f"RSS: Unknown command '{cmd_name}' (from '{command_str}')")
    return handler


async def _start_rss_download(
    url: str,
    command: str,
    user_id: int,
    rss_chat_id,
    rss_topic_id,
    item_title: str,
) -> None:
    """Send a notification to RSS_CHAT and start the download directly."""
    handler = _resolve_command(command)
    if handler is None:
        LOGGER.error(f"RSS: Cannot start download, unknown command: {command}")
        return

    # Build the command text that the handler will parse.
    # command is like "ql -doc" or "mirror -up remote:path".
    # The handler expects message.text = "/cmd url [args]"
    cmd_text = f"/{command.strip().lstrip('/')}"
    # Insert URL after the command name
    parts = cmd_text.split(maxsplit=1)
    if len(parts) > 1:
        cmd_text = f"{parts[0]} {url} {parts[1]}"
    else:
        cmd_text = f"{parts[0]} {url}"

    # Resolve the user who subscribed to this feed
    try:
        user = await TgClient.bot.get_users(user_id)
    except Exception as e:
        LOGGER.error(
            f"RSS: Failed to get user {user_id}, "
            f"cannot start download for '{item_title}': {e}"
        )
        return

    # Send notification to RSS_CHAT — this also provides the Message object
    # that the download pipeline uses for posting status/results
    notify_text = f"<b>RSS Download Started</b>\n<code>{escape_html(item_title)}</code>"
    msg = await send_rss(notify_text, rss_chat_id, rss_topic_id)
    if isinstance(msg, str):
        LOGGER.error(f"RSS: Failed to send to RSS_CHAT: {msg}")
        return

    # Mutate the message to carry the command text and user identity
    msg.text = cmd_text
    msg.from_user = user
    msg._rss_trigger = True

    # Invoke the same handler function used by the bot's message handlers
    # (e.g., mirror, leech, qb_leech, ytdl, etc.)
    await handler(TgClient.bot, msg)


# ======================== Helper Functions ========================


async def fetch_rss(url: str, retries: int = 3) -> str | None:
    """Fetch RSS feed with retries."""
    for attempt in range(retries + 1):
        try:
            async with AsyncClient(
                headers=HEADERS, follow_redirects=True, timeout=60, verify=False
            ) as client:
                res = await client.get(url)
            return res.text
        except Exception:
            if attempt >= retries:
                raise
    return None


def get_entry_link(entry: dict) -> str:
    """Extract link from RSS entry."""
    links = entry.get("links", [])
    if len(links) > 1:
        return links[1].get("href", "")
    if links:
        return links[0].get("href", "")
    return entry.get("link", "")


def get_entry_size(entry: dict) -> int:
    """Extract size from RSS entry."""
    if entry.get("size"):
        return int(entry["size"])
    if summary := entry.get("summary"):
        if matches := SIZE_REGEX.findall(summary):
            return get_size_bytes(matches[0][0])
    return 0


def parse_filters(filter_str: str | None) -> list[list[str]]:
    """Parse filter string into list of filter groups."""
    if not filter_str:
        return []
    return [x.split(" or ") for x in filter_str.split("|")]


def check_filters(item_title: str, data: dict) -> bool:
    """Check if item passes include/exclude filters. Returns True if item should be processed."""
    sensitive = data.get("sensitive", False)

    def matches(term: str, title: str) -> bool:
        if sensitive:
            return term.lower() in title.lower()
        return term in title

    # Check include filters - at least one term in each group must match
    for flist in data["inf"]:
        if all(not matches(term, item_title) for term in flist):
            return False

    # Check exclude filters - if any term matches, exclude
    for flist in data["exf"]:
        if any(matches(term, item_title) for term in flist):
            return False

    return True


def parse_chat_id(chat: int | str) -> tuple[int | str | None, int | str | None]:
    """Parse RSS_CHAT config into chat_id and topic_id."""
    if isinstance(chat, int):
        return chat, None
    if "|" in chat:
        parts = chat.split("|", 1)
        chat_id = int(parts[0]) if parts[0].lstrip("-").isdigit() else parts[0]
        topic_id = int(parts[1]) if parts[1].lstrip("-").isdigit() else parts[1]
        return chat_id, topic_id
    if chat.lstrip("-").isdigit():
        return int(chat), None
    return None, None


def build_back_close_buttons(user_id: int) -> ButtonMaker:
    """Create standard back/close button layout."""
    buttons = ButtonMaker()
    buttons.data_button("Back", f"rss back {user_id}")
    buttons.data_button("Close", f"rss close {user_id}")
    return buttons


def format_feed_info(title: str, data: dict, show_user: bool = False) -> str:
    """Format feed information for display."""
    info = f"\n\n<b>Title:</b> <code>{title}</code>\n"
    info += f"<b>Feed Url:</b> <code>{data['link']}</code>\n"
    info += f"<b>Command:</b> <code>{data['command']}</code>\n"
    info += f"<b>Inf:</b> <code>{data['inf']}</code>\n"
    info += f"<b>Exf:</b> <code>{data['exf']}</code>\n"
    info += f"<b>Sensitive:</b> <code>{data.get('sensitive', False)}</code>\n"
    info += f"<b>Paused:</b> <code>{data['paused']}</code>\n"
    if show_user:
        info += f"<b>User:</b> {data['tag'].replace('@', '', 1)}"
    return info


def escape_html(text: str) -> str:
    """Escape < and > for HTML display."""
    return text.replace(">", "").replace("<", "")


# ======================== Menu Functions ========================


async def rss_menu(event) -> tuple[str, list]:
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
        btn_text = "Shutdown Rss" if scheduler.running else "Start Rss"
        btn_data = "shutdown" if scheduler.running else "start"
        buttons.data_button(btn_text, f"rss {btn_data} {user_id}")

    buttons.data_button("Close", f"rss close {user_id}")
    return (
        f"Rss Menu | Users: {len(rss_dict)} | Running: {scheduler.running}",
        buttons.build_menu(2),
    )


async def update_rss_menu(query) -> None:
    msg, button = await rss_menu(query)
    await edit_message(query.message, msg, button)


@new_task
async def get_rss_menu(_, message) -> None:
    msg, button = await rss_menu(message)
    await send_message(message, msg, button)


# ======================== Subscription Functions ========================


async def _process_subscription(
    message, title: str, feed_link: str, args: list, tag: str, user_id: int
) -> str | None:
    """Process a single RSS subscription. Returns message string on success, None on failure."""
    # Parse arguments
    arg_base = {"-c": None, "-inf": None, "-exf": None, "-stv": None}
    if len(args) > 2:
        arg_parser(args[2:], arg_base)

    cmd = arg_base["-c"]
    inf = arg_base["-inf"]
    exf = arg_base["-exf"]
    stv = arg_base["-stv"]
    stv = stv.lower() == "true" if stv is not None else False

    inf_lists = parse_filters(inf)
    exf_lists = parse_filters(exf)

    try:
        html = await fetch_rss(feed_link)
        rss_d = feed_parse(html)

        last_link = ""
        last_title = ""
        size = 0
        feed_title = rss_d.feed.get("title", "Unknown")

        if rss_d.entries:
            entry = rss_d.entries[0]
            last_title = entry["title"]
            last_link = get_entry_link(entry)
            size = get_entry_size(entry)

        # Build response message
        msg = "<b>Subscribed!</b>"
        msg += f"\n<b>Title: </b><code>{title}</code>\n<b>Feed Url: </b>{feed_link}"

        if rss_d.entries:
            msg += f"\n<b>latest record for </b>{feed_title}:"
            msg += f"\nName: <code>{escape_html(last_title)}</code>"
            msg += f"\n<b>Link: </b><code>{last_link}</code>"
            if size:
                msg += f"\nSize: {get_readable_file_size(size)}"
        else:
            msg += "\n<b>Note:</b> Feed is currently empty, will be monitored for new items."

        msg += f"\n<b>Command: </b><code>{cmd}</code>"
        msg += f"\n<b>Filters:-</b>\ninf: <code>{inf}</code>\nexf: <code>{exf}</code>\n<b>sensitive: </b>{stv}"

        # Store subscription
        feed_data = {
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

        async with rss_dict_lock:
            if user_id not in rss_dict:
                rss_dict[user_id] = {}
            rss_dict[user_id][title] = feed_data

        LOGGER.info(
            f"Rss Feed Added: id: {user_id} - title: {title} - link: {feed_link} - c: {cmd} - inf: {inf} - exf: {exf} - stv: {stv}"
        )
        return msg

    except (IndexError, AttributeError) as e:
        await send_message(
            message,
            f"The link: {feed_link} doesn't seem to be a RSS feed or it's region-blocked!\nError: {e}",
        )
    except Exception as e:
        await send_message(message, str(e))
    return None


@new_task
async def rss_sub(_, message, pre_event) -> None:
    user_id = message.from_user.id
    handler_dict[user_id] = False
    tag = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else message.from_user.mention
    )

    result_msg = ""
    for index, item in enumerate(message.text.split("\n"), start=1):
        args = item.split()

        if len(args) < 2:
            await send_message(
                message,
                f"{item}. Wrong Input format. Read help message before adding new subscription!",
            )
            continue

        title = args[0].strip()
        if (user_feeds := rss_dict.get(user_id)) and title in user_feeds:
            await send_message(
                message, f"This title {title} already subscribed! Choose another title!"
            )
            continue

        feed_link = args[1].strip()
        if feed_link.startswith(("-inf", "-exf", "-c")):
            await send_message(
                message, f"Wrong input in line {index}! Add Title! Read the example!"
            )
            continue

        if sub_msg := await _process_subscription(
            message, title, feed_link, args, tag, user_id
        ):
            result_msg += sub_msg

    if result_msg:
        await database.rss_update(user_id)
        await send_message(message, result_msg)
        is_sudo = await CustomFilters.sudo("", message)
        if scheduler.state == 2:
            scheduler.resume()
        elif is_sudo and not scheduler.running:
            add_job()
            scheduler.start()

    await update_rss_menu(pre_event)


# ======================== Update Functions ========================


async def get_user_id(title: str) -> tuple[bool, int | bool]:
    async with rss_dict_lock:
        return next(
            ((True, user_id) for user_id, feeds in rss_dict.items() if title in feeds),
            (False, False),
        )


@new_task
async def rss_update(_, message, pre_event, state: str) -> None:
    user_id = message.from_user.id
    handler_dict[user_id] = False
    is_sudo = await CustomFilters.sudo("", message)
    updated = []

    for title in message.text.split():
        title = title.strip()
        current_user_id = user_id

        if not rss_dict.get(current_user_id, {}).get(title):
            if is_sudo:
                found, current_user_id = await get_user_id(title)
                if not found:
                    await send_message(message, f"{title} not found!")
                    continue
            else:
                await send_message(message, f"{title} not found!")
                continue

        is_paused = rss_dict[current_user_id][title].get("paused", False)
        if (is_paused and state == "pause") or (not is_paused and state == "resume"):
            await send_message(message, f"{title} already {state}d!")
            continue

        async with rss_dict_lock:
            updated.append(title)
            if state == "unsubscribe":
                del rss_dict[current_user_id][title]
            else:
                rss_dict[current_user_id][title]["paused"] = state == "pause"

        if state == "resume":
            if scheduler.state == 2:
                scheduler.resume()
            elif is_sudo and not scheduler.running:
                add_job()
                scheduler.start()

        if is_sudo and Config.DATABASE_URL and current_user_id != user_id:
            await database.rss_update(current_user_id)

        if not rss_dict.get(current_user_id):
            async with rss_dict_lock:
                del rss_dict[current_user_id]
            await database.rss_delete(current_user_id)
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


# ======================== List Functions ========================


async def rss_list(query, start: int, all_users: bool = False) -> None:
    user_id = query.from_user.id
    buttons = build_back_close_buttons(user_id)
    page = start // 5

    async with rss_dict_lock:
        if all_users:
            list_feed = f"<b>All subscriptions | Page: {page} </b>"
            keys_count = sum(len(v) for v in rss_dict.values())
            count = 0
            for titles in rss_dict.values():
                for title, data in list(titles.items())[start : start + 5]:
                    list_feed += format_feed_info(title, data, show_user=True)
                    count += 1
                    if count >= 5:
                        break
                if count >= 5:
                    break
        else:
            list_feed = f"<b>Your subscriptions | Page: {page} </b>"
            user_feeds = rss_dict.get(user_id, {})
            keys_count = len(user_feeds)
            for title, data in list(user_feeds.items())[start : start + 5]:
                list_feed += format_feed_info(title, data, show_user=False)

    if keys_count > 5:
        for x in range(0, keys_count, 5):
            buttons.data_button(
                f"{x // 5}", f"rss list {user_id} {x}", position="footer"
            )

    button = buttons.build_menu(2)
    if query.message.text.html != list_feed:
        await edit_message(query.message, list_feed, button)


# ======================== Get/Edit Functions ========================


@new_task
async def rss_get(_, message, pre_event) -> None:
    user_id = message.from_user.id
    handler_dict[user_id] = False
    args = message.text.split()

    if len(args) < 2:
        await send_message(
            message,
            f"{args}. Wrong Input format. You should add number of the items you want to get.",
        )
        await update_rss_menu(pre_event)
        return

    try:
        title, count = args[0], int(args[1])
        data = rss_dict.get(user_id, {}).get(title)

        if not data or count <= 0:
            await send_message(message, "Enter a valid title. Title not found!")
            await update_rss_menu(pre_event)
            return

        msg = await send_message(
            message, f"Getting the last <b>{count}</b> item(s) from {title}"
        )

        try:
            html = await fetch_rss(data["link"])
            rss_d = feed_parse(html)

            item_info = ""
            for i in range(min(count, len(rss_d.entries))):
                entry = rss_d.entries[i]
                link = get_entry_link(entry)
                item_info += (
                    f"<b>Name: </b><code>{escape_html(entry['title'])}</code>\n"
                )
                item_info += f"<b>Link: </b><code>{link}</code>\n\n"

            if len(item_info.encode()) > 4000:
                with BytesIO(item_info.encode()) as out_file:
                    out_file.name = f"rssGet {title} items_no. {count}.txt"
                    await send_file(message, out_file)
                await delete_message(msg)
            else:
                await edit_message(msg, item_info)

        except IndexError:
            LOGGER.error("Parse depth exceeded")
            await edit_message(
                msg, "Parse depth exceeded. Try again with a lower value."
            )
        except Exception as e:
            LOGGER.error(str(e))
            await edit_message(msg, str(e))

    except Exception as e:
        LOGGER.error(str(e))
        await send_message(message, f"Enter a valid value!. {e}")

    await update_rss_menu(pre_event)


@new_task
async def rss_edit(_, message, pre_event) -> None:
    user_id = message.from_user.id
    handler_dict[user_id] = False
    updated = False

    for item in message.text.split("\n"):
        args = item.split()
        if len(args) < 2:
            await send_message(
                message,
                f"{item}. Wrong Input format. Read help message before editing!",
            )
            continue

        title = args[0].strip()
        if not rss_dict.get(user_id, {}).get(title):
            await send_message(message, "Enter a valid title. Title not found!")
            continue

        updated = True
        arg_base = {"-c": None, "-inf": None, "-exf": None, "-stv": None}
        arg_parser(args[1:], arg_base)

        async with rss_dict_lock:
            feed = rss_dict[user_id][title]

            if arg_base["-stv"] is not None:
                feed["sensitive"] = arg_base["-stv"].lower() == "true"

            if arg_base["-c"] is not None:
                feed["command"] = (
                    None if arg_base["-c"].lower() == "none" else arg_base["-c"]
                )

            if arg_base["-inf"] is not None:
                feed["inf"] = (
                    []
                    if arg_base["-inf"].lower() == "none"
                    else parse_filters(arg_base["-inf"])
                )

            if arg_base["-exf"] is not None:
                feed["exf"] = (
                    []
                    if arg_base["-exf"].lower() == "none"
                    else parse_filters(arg_base["-exf"])
                )

    if updated:
        await database.rss_update(user_id)
    await update_rss_menu(pre_event)


@new_task
async def rss_delete(_, message, pre_event) -> None:
    handler_dict[message.from_user.id] = False
    for user in message.text.split():
        user_id = int(user)
        async with rss_dict_lock:
            del rss_dict[user_id]
        await database.rss_delete(user_id)
    await update_rss_menu(pre_event)


# ======================== Event Handler ========================


async def event_handler(client, query, pfunc) -> None:
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


# ======================== Listener Handlers ========================


async def _handle_close(query, user_id: int) -> None:
    await query.answer()
    handler_dict[user_id] = False
    await delete_message(query.message.reply_to_message)
    await delete_message(query.message)


async def _handle_back(query, user_id: int) -> None:
    await query.answer()
    handler_dict[user_id] = False
    await update_rss_menu(query)


async def _handle_sub(client, query, user_id: int) -> None:
    await query.answer()
    handler_dict[user_id] = False
    button = build_back_close_buttons(user_id).build_menu(2)
    await edit_message(query.message, RSS_HELP_MESSAGE, button)
    await event_handler(client, query, partial(rss_sub, pre_event=query))


async def _handle_list(query, user_id: int, data: list[str]) -> None:
    handler_dict[user_id] = False
    if not rss_dict.get(int(data[2])):
        await query.answer(text="No subscriptions!", show_alert=True)
        return
    await query.answer()
    await rss_list(query, int(data[3]))


async def _handle_get(client, query, user_id: int, data: list[str]) -> None:
    handler_dict[user_id] = False
    if not rss_dict.get(int(data[2])):
        await query.answer(text="No subscriptions!", show_alert=True)
        return
    await query.answer()
    button = build_back_close_buttons(user_id).build_menu(2)
    await edit_message(
        query.message,
        "Send one title with value separated by space get last X items.\nTitle Value\nTimeout: 60 sec.",
        button,
    )
    await event_handler(client, query, partial(rss_get, pre_event=query))


async def _handle_feed_action(
    client, query, user_id: int, data: list[str], action: str
) -> None:
    """Handle unsubscribe, pause, resume actions."""
    handler_dict[user_id] = False
    if not rss_dict.get(int(data[2])):
        await query.answer(text="No subscriptions!", show_alert=True)
        return
    await query.answer()

    buttons = ButtonMaker()
    buttons.data_button("Back", f"rss back {user_id}")

    action_buttons = {
        "pause": "Pause AllMyFeeds",
        "resume": "Resume AllMyFeeds",
        "unsubscribe": "Unsub AllMyFeeds",
    }
    action_data = {
        "pause": "uallpause",
        "resume": "uallresume",
        "unsubscribe": "uallunsub",
    }
    buttons.data_button(action_buttons[action], f"rss {action_data[action]} {user_id}")
    buttons.data_button("Close", f"rss close {user_id}")

    await edit_message(
        query.message,
        f"Send one or more rss titles separated by space to {action}.\nTimeout: 60 sec.",
        buttons.build_menu(2),
    )
    await event_handler(
        client, query, partial(rss_update, pre_event=query, state=action)
    )


async def _handle_edit(client, query, user_id: int, data: list[str]) -> None:
    handler_dict[user_id] = False
    if not rss_dict.get(int(data[2])):
        await query.answer(text="No subscriptions!", show_alert=True)
        return
    await query.answer()
    button = build_back_close_buttons(user_id).build_menu(2)
    await edit_message(query.message, RSS_EDIT_HELP, button)
    await event_handler(client, query, partial(rss_edit, pre_event=query))


async def _handle_user_all(query, user_id: int, data: list[str], action: str) -> None:
    """Handle uallpause, uallresume, uallunsub for single user."""
    handler_dict[user_id] = False
    target_user = int(data[2])

    if not rss_dict.get(target_user):
        await query.answer(text="No subscriptions!", show_alert=True)
        return
    await query.answer()

    if action == "unsub":
        async with rss_dict_lock:
            del rss_dict[target_user]
        await database.rss_delete(target_user)
    else:
        paused = action == "pause"
        async with rss_dict_lock:
            for info in rss_dict[target_user].values():
                info["paused"] = paused
        if action == "resume" and scheduler.state == 2:
            scheduler.resume()
        await database.rss_update(target_user)

    await update_rss_menu(query)


async def _handle_all(query, user_id: int, action: str) -> None:
    """Handle allpause, allresume, allunsub for all users."""
    if not rss_dict:
        await query.answer(text="No subscriptions!", show_alert=True)
        return
    await query.answer()

    if action == "unsub":
        async with rss_dict_lock:
            rss_dict.clear()
        await database.trunc_table("rss")
    elif action == "pause":
        async with rss_dict_lock:
            for user_feeds in rss_dict.values():
                for feed in user_feeds.values():
                    feed["paused"] = True
        if scheduler.running:
            scheduler.pause()
        await database.rss_update_all()
    elif action == "resume":
        async with rss_dict_lock:
            for user_feeds in rss_dict.values():
                for feed in user_feeds.values():
                    feed["paused"] = False
        if scheduler.state == 2:
            scheduler.resume()
        elif not scheduler.running:
            add_job()
            scheduler.start()
        await database.rss_update_all()

    await update_rss_menu(query)


async def _handle_deluser(client, query, user_id: int) -> None:
    if not rss_dict:
        await query.answer(text="No subscriptions!", show_alert=True)
        return
    await query.answer()
    button = build_back_close_buttons(user_id).build_menu(2)
    await edit_message(
        query.message,
        "Send one or more user_id separated by space to delete their resources.\nTimeout: 60 sec.",
        button,
    )
    await event_handler(client, query, partial(rss_delete, pre_event=query))


async def _handle_listall(query, data: list[str]) -> None:
    if not rss_dict:
        await query.answer(text="No subscriptions!", show_alert=True)
        return
    await query.answer()
    await rss_list(query, int(data[3]), all_users=True)


async def _handle_shutdown(query) -> None:
    if not scheduler.running:
        await query.answer(text="Already Stopped!", show_alert=True)
        return
    await query.answer()
    scheduler.shutdown(wait=False)
    await sleep(0.5)
    await update_rss_menu(query)


async def _handle_start(query) -> None:
    if scheduler.running:
        await query.answer(text="Already Running!", show_alert=True)
        return
    await query.answer()
    add_job()
    scheduler.start()
    await update_rss_menu(query)


@new_task
async def rss_listener(client, query) -> None:
    user_id = query.from_user.id
    data = query.data.split()
    action = data[1]

    # Permission check
    if int(data[2]) != user_id and not await CustomFilters.sudo("", query):
        await query.answer(
            text="You don't have permission to use these buttons!", show_alert=True
        )
        return

    # Simple actions (handlers manage their own query.answer())
    if action == "close":
        await _handle_close(query, user_id)
    elif action == "back":
        await _handle_back(query, user_id)
    elif action == "sub":
        await _handle_sub(client, query, user_id)
    elif action == "list":
        await _handle_list(query, user_id, data)
    elif action == "get":
        await _handle_get(client, query, user_id, data)
    elif action in ("unsubscribe", "pause", "resume"):
        await _handle_feed_action(client, query, user_id, data, action)
    elif action == "edit":
        await _handle_edit(client, query, user_id, data)
    elif action.startswith("uall"):
        await _handle_user_all(
            query, user_id, data, action[4:]
        )  # Extract pause/resume/unsub
    elif action.startswith("all"):
        await _handle_all(query, user_id, action[3:])  # Extract pause/resume/unsub
    elif action == "deluser":
        await _handle_deluser(client, query, user_id)
    elif action == "listall":
        await _handle_listall(query, data)
    elif action == "shutdown":
        await _handle_shutdown(query)
    elif action == "start":
        await _handle_start(query)


# ======================== RSS Monitor ========================


async def _process_feed_entry(
    entry: dict,
    feed_count: int,
    title: str,
    data: dict,
    user: int,
    rss_chat_id: int | str | None,
    rss_topic_id: int | str | None,
) -> bool:
    """Process a single feed entry. Returns True to continue, False to break."""
    try:
        await sleep(10)
    except Exception:
        raise RssShutdownException("Rss Monitor Stopped!")

    try:
        item_title = entry["title"]
        url = get_entry_link(entry)

        # Check if we've reached the last known item
        if data["last_feed"] == url or data["last_title"] == item_title:
            return False

        size = get_entry_size(entry)
    except IndexError:
        LOGGER.warning(
            f"Reached Max index no. {feed_count} for this feed: {title}. Maybe you need to use less RSS_DELAY to not miss some torrents"
        )
        return False

    # Apply filters
    if not check_filters(item_title, data):
        return True

    # Handle feed item
    if command := data["command"]:
        # Auto-download mode: start download directly
        if size and Config.RSS_SIZE_LIMIT and Config.RSS_SIZE_LIMIT < size:
            return True
        await _start_rss_download(
            url=url,
            command=command,
            user_id=user,
            rss_chat_id=rss_chat_id,
            rss_topic_id=rss_topic_id,
            item_title=item_title,
        )
    else:
        # Info-only mode: just post item details to RSS_CHAT
        feed_msg = f"<b>Name: </b><code>{escape_html(item_title)}</code>"
        feed_msg += f"\n\n<b>Link: </b><code>{url}</code>"
        if size:
            feed_msg += f"\n<b>Size: </b>{get_readable_file_size(size)}"
        feed_msg += f"\n<b>Tag: </b><code>{data['tag']}</code> <code>{user}</code>"
        await send_rss(feed_msg, rss_chat_id, rss_topic_id)
    return True


async def _process_feed(
    user: int,
    title: str,
    data: dict,
    rss_chat_id: int | str | None,
    rss_topic_id: int | str | None,
) -> bool:
    """Process a single RSS feed. Returns True if feed was active (not paused)."""
    if data["paused"]:
        return False

    html = await fetch_rss(data["link"])
    rss_d = feed_parse(html)
    if not rss_d.entries:
        LOGGER.warning(
            f"No entries found for > Feed Title: {title} - Feed Link: {data['link']}"
        )
        return True

    entry0 = rss_d.entries[0]
    last_link = get_entry_link(entry0)
    last_title = entry0.get("title", "")

    # No new items
    if data["last_feed"] == last_link or data["last_title"] == last_title:
        return True

    # Process new entries
    for feed_count, entry in enumerate(rss_d.entries):
        should_continue = await _process_feed_entry(
            entry, feed_count, title, data, user, rss_chat_id, rss_topic_id
        )
        if not should_continue:
            break

    # Update last seen
    async with rss_dict_lock:
        if user in rss_dict and rss_dict[user].get(title):
            rss_dict[user][title].update(
                {"last_feed": last_link, "last_title": last_title}
            )

    await database.rss_update(user)
    LOGGER.info(f"Feed Name: {title}")
    LOGGER.info(f"Last item: {last_link}")
    return True


async def rss_monitor() -> None:
    chat = Config.RSS_CHAT
    if not chat:
        LOGGER.warning("RSS_CHAT not configured! Shutting down rss scheduler...")
        scheduler.shutdown(wait=False)
        return

    if not rss_dict:
        scheduler.pause()
        return

    rss_chat_id, rss_topic_id = parse_chat_id(chat)
    all_paused = True

    for user, items in list(rss_dict.items()):
        for title, data in items.items():
            try:
                if await _process_feed(user, title, data, rss_chat_id, rss_topic_id):
                    all_paused = False
            except RssShutdownException as ex:
                LOGGER.info(ex)
                return
            except Exception as e:
                LOGGER.error(f"{e} - Feed Name: {title} - Feed Link: {data['link']}")

    if all_paused:
        scheduler.pause()


# ======================== Scheduler Setup ========================


def add_job() -> None:
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
