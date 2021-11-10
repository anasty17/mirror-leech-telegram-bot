import requests
import itertools
import time

from urllib.parse import quote
from telegram import InlineKeyboardMarkup
from telegram.ext import CommandHandler
from telegraph import Telegraph
from telegraph.exceptions import RetryAfterError

from bot import dispatcher, LOGGER, telegraph_token, DEFAULT_SEARCH
from bot.helper.telegram_helper.message_utils import editMessage, sendMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper import button_build

SITES = ("rarbg ", "1337x ", "yts ", "etzv ", "tgx ", "torlock ", "piratebay ", "nyaasi ", "ettv ", "all ")

def search(update, context):
    try:
        key = update.message.text.split(" ", maxsplit=1)[1]
        if key.lower().startswith(SITES):
            site = key.split(" ")[0]
            key = update.message.text.split(" ", maxsplit=2)[2]
        elif DEFAULT_SEARCH is not None:
            site = DEFAULT_SEARCH
        else:
            site = "all"
        srchmsg = sendMessage("Searching...", context.bot, update)
        LOGGER.info(f"Searching: {key} from {site}")
        api = f"https://z09d8d7c2-z619021a9-gtw.qovery.io/api/{site}/{key}"
        resp = requests.get(api)
        search_results = resp.json()
        if site == "all":
            search_results = list(itertools.chain.from_iterable(search_results))
        if isinstance(search_results, list):
            link = getResult(search_results, key)
            buttons = button_build.ButtonMaker()
            buttons.buildbutton("🔎 VIEW", link)
            search_count = len(search_results)
            if search_count > 200:
                search_count = 200
            msg = f"<b>Found {search_count} result for <i>{key}</i></b>"
            button = InlineKeyboardMarkup(buttons.build_menu(1))
            editMessage(msg, srchmsg, button)
        else:
            editMessage(f"No result found for <i>{key}</i>", srchmsg)
    except IndexError:
        sendMessage("Send a search key along with command", context.bot, update)
    except Exception as e:
        LOGGER.error(str(e))

def getResult(search_results, key):
    telegraph_content = []
    path = []
    msg = f"<h4>Search Result For </h4>{key}<br><br>"
    for index, result in enumerate(search_results, start=1):
        try:
            msg += f"<code><a href='{result['Url']}'>{result['Name']}</a></code><br>"
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
        if index == 200:
            break

    if msg != "":
        telegraph_content.append(msg)

    for content in telegraph_content :
        while True:
            try:
                path.append(Telegraph(access_token=telegraph_token).create_page(
                                                    title = 'Mirror-leech Torrent Search',
                                                    author_name='Mirror-leech',
                                                    author_url='https://github.com/anasty17/mirror-leech-telegram-bot',
                                                    html_content=content
                                                    )['path'])
                break
            except RetryAfterError as t:
                time.sleep(t.retry_after)
    time.sleep(0.5)
    if len(path) > 1:
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
        while True:
            try:
                Telegraph(access_token=telegraph_token).edit_page(path = path[prev_page],
                             title = 'Mirror-leech Torrent Search',
                             author_name='Mirror-leech',
                             author_url='https://github.com/anasty17/mirror-leech-telegram-bot',
                             html_content=content)
                break
            except RetryAfterError as t:
                time.sleep(t.retry_after)
    return


search_handler = CommandHandler(BotCommands.SearchCommand, search, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
dispatcher.add_handler(search_handler)
