import requests
import itertools
import time
import html

from urllib.parse import quote
from telegram import InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler

from bot import dispatcher, LOGGER, SEARCH_API_LINK
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.telegram_helper.message_utils import editMessage, sendMessage, sendMarkup
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper import button_build


SITES = {
    "1337x": "1337x",
    "nyaasi": "NyaaSi",
    "yts": "YTS",
    "piratebay": "PirateBay",
    "torlock": "Torlock",
    "eztv": "EzTvio",
    "tgx": "TorrentGalaxy",
    "rarbg": "Rarbg",
    "ettv": "Ettv",
    "all": "All"
}

SEARCH_LIMIT = 250

def torser(update, context):
    user_id = update.message.from_user.id
    if SEARCH_API_LINK is None:
        return sendMessage("No Torrent Search Api Link. Check readme variables", context.bot, update)
    try:
        key = update.message.text.split(" ", maxsplit=1)[1]
    except IndexError:
        return sendMessage("Send a search key along with command", context.bot, update)
    buttons = button_build.ButtonMaker()
    for data, name in SITES.items():
        buttons.sbutton(name, f"torser {user_id} {data}")
    buttons.sbutton("Cancel", f"torser {user_id} cancel")
    button = InlineKeyboardMarkup(buttons.build_menu(2))
    sendMarkup('Choose site to search.', context.bot, update, button)


def torserbut(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    message = query.message
    key = message.reply_to_message.text.split(" ", maxsplit=1)[1]
    data = query.data
    data = data.split(" ")
    if user_id != int(data[1]):
        query.answer(text="Not Yours!", show_alert=True)
    elif data[2] != "cancel":
        query.answer()
        site = data[2]
        editMessage(f"<b>Searching for <i>{key}</i> Torrent Site:- <i>{SITES.get(site)}</i></b>", message)
        search(key, site, message)
    else:
        query.answer()
        editMessage("Search has been canceled!", message)

def search(key, site, message):
    LOGGER.info(f"Searching: {key} from {site}")
    api = f"{SEARCH_API_LINK}/api/{site}/{key}"
    try:
        resp = requests.get(api)
        search_results = resp.json()
        if site == "all":
            search_results = list(itertools.chain.from_iterable(search_results))
        if isinstance(search_results, list):
            link = getResult(search_results, key, message)
            buttons = button_build.ButtonMaker()
            buttons.buildbutton("🔎 VIEW", link)
            msg = f'<b>Found {min(len(search_results), SEARCH_LIMIT)}</b>'
            msg += f" <b>result for <i>{key}</i> Torrent Site:- <i>{SITES.get(site)}</i></b>"
            button = InlineKeyboardMarkup(buttons.build_menu(1))
            editMessage(msg, message, button)
        else:
            editMessage(f"No result found for <i>{key}</i> Torrent Site:- <i>{SITES.get(site)}</i>", message)
    except Exception as e:
        editMessage(str(e), message)

def getResult(search_results, key, message):
    telegraph_content = []
    msg = f"<h4>Search Result For {key}</h4>"
    for index, result in enumerate(search_results, start=1):
        try:
            msg += f"<code><a href='{result['Url']}'>{html.escape(result['Name'])}</a></code><br>"
            if "Files" in result.keys():
                for subres in result['Files']:
                    msg += f"<b>Quality: </b>{subres['Quality']} | <b>Size: </b>{subres['Size']}<br>"
                    try:
                        msg += f"<b>Share link to</b> <a href='http://t.me/share/url?url={subres['Torrent']}'>Telegram</a><br>"
                        msg += f"<b>Link: </b><code>{subres['Torrent']}</code><br>"
                    except KeyError:
                        msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={subres['Magnet']}'>Telegram</a><br>"
                        msg += f"<b>Magnet: </b><code>{quote(subres['Magnet'])}</code><br>"
            else:
                msg += f"<b>Size: </b>{result['Size']}<br>"
                msg += f"<b>Seeders: </b>{result['Seeders']} | <b>Leechers: </b>{result['Leechers']}<br>"
        except KeyError:
            pass
        try:
            msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={quote(result['Magnet'])}'>Telegram</a><br>"
            msg += f"<b>Magnet: </b><code>{result['Magnet']}</code><br><br>"
        except KeyError:
            msg += "<br>"
        if len(msg.encode('utf-8')) > 40000 :
           telegraph_content.append(msg)
           msg = ""

        if index == SEARCH_LIMIT:
            break

    if msg != "":
        telegraph_content.append(msg)

    editMessage(f"<b>Creating</b> {len(telegraph_content)} <b>Telegraph pages.</b>", message)
    path = [telegraph.create_page(
                title='Mirror-leech-bot Torrent Search',
                content=content
            )["path"] for content in telegraph_content]
    time.sleep(0.5)
    if len(path) > 1:
        editMessage(f"<b>Editing</b> {len(telegraph_content)} <b>Telegraph pages.</b>", message)
        edit_telegraph(path, telegraph_content)
    return f"https://telegra.ph/{path[0]}"

def edit_telegraph(path, telegraph_content):
    nxt_page = 1
    prev_page = 0
    num_of_path = len(path)
    for content in telegraph_content :
        if nxt_page == 1 :
            content += f'<b><a href="https://telegra.ph/{path[nxt_page]}">Next</a></b>'
            nxt_page += 1
        else :
            if prev_page <= num_of_path:
                content += f'<b><a href="https://telegra.ph/{path[prev_page]}">Prev</a></b>'
                prev_page += 1
            if nxt_page < num_of_path:
                content += f'<b> | <a href="https://telegra.ph/{path[nxt_page]}">Next</a></b>'
                nxt_page += 1
        telegraph.edit_page(
            path = path[prev_page],
            title = 'Mirror-leech-bot Torrent Search',
            content=content
        )
    return

torser_handler = CommandHandler(BotCommands.SearchCommand, torser, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
torserbut_handler = CallbackQueryHandler(torserbut, pattern="torser", run_async=True)

dispatcher.add_handler(torser_handler)
dispatcher.add_handler(torserbut_handler)
