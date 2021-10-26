import aiohttp
import asyncio
import itertools
from urllib.parse import quote
from time import sleep
from telegram import InlineKeyboardMarkup
from telegram.ext import CommandHandler
from telegraph import Telegraph

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
        search_results = asyncio.run(apiSearch(key, site))
        if site == "all":
            search_results = list(itertools.chain.from_iterable(search_results))
        if isinstance(search_results, list):
            link = getResult(list(search_results), key)
            buttons = button_build.ButtonMaker()
            buttons.buildbutton("🔎 VIEW", link)
            msg = f"<b>Found {len(search_results)} result for <i>{key}</i></b>"
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
    msg = f"Search Result For {key}<br><br>"
    for result in search_results:
        try:
            msg += f"<code><a href='{result['Url']}'>{result['Name']}</a></code><br>"
            if "Files" in result.keys():
                for subres in result['Files']:
                    msg += f"<b>Quality: </b>{subres['Quality']} | <b>Size: </b>{subres['Size']}<br>"
                    try:
                        msg += f"<b>Share</b> link to <a href='http://t.me/share/url?url={subres['Torrent']}'>Telegram</a><br>"
                        msg += f"<b>Link: </b><code>{subres['Torrent']}</code><br>"
                    except KeyError:
                        msg += f"<b>Share</b> Magnet to <a href='http://t.me/share/url?url={quote(subres['Magnet'])}'>Telegram</a><br>"
                        msg += f"<b>Magnet: </b><code>{subres['Magnet']}</code><br>"
            else:
                msg += f"<b>Size: </b>{result['Size']}<br>"
                msg += f"<b>Seeders: </b>{result['Seeders']} | <b>Leechers: </b>{result['Leechers']}<br>"
        except KeyError:
            pass
        try:
            msg += f"<b>Share</b> Magnet to <a href='http://t.me/share/url?url={quote(result['Magnet'])}'>Telegram</a><br>"
            msg += f"<b>Magnet: </b><code>{result['Magnet']}</code><br><br>"
        except KeyError:
            msg += "<br>"
        if len(msg.encode('utf-8')) > 40000 :
           telegraph_content.append(msg)
           msg = ""

    if msg != "":
        telegraph_content.append(msg)

    for content in telegraph_content :
        path.append(Telegraph(access_token=telegraph_token).create_page(
                                                    title = 'Mirror-leech Torrent Search',
                                                    author_name='Mirror-leech',
                                                    author_url='https://github.com/anasty17/mirror-leech-telegram-bot',
                                                    html_content=content
                                                    )['path'])
        sleep(1)
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
        Telegraph(access_token=telegraph_token).edit_page(path = path[prev_page],
                             title = 'Mirror-leech Torrent Search',
                             author_name='Mirror-leech',
                             author_url='https://github.com/anasty17/mirror-leech-telegram-bot',
                             html_content=content)

async def apiSearch(key, site):
    async with aiohttp.ClientSession() as session:
        api = f"https://anasty17.herokuapp.com/api/{site}/{key}"
        try:
            async with session.get(api, timeout=15) as resp:
                results = await resp.json()
        except Exception as err:
            raise err
    return results


search_handler = CommandHandler(BotCommands.SearchCommand, search, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
dispatcher.add_handler(search_handler)
