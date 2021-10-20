import aiohttp
import asyncio
import itertools
import logging

from time import sleep
from telegram import InlineKeyboardMarkup
from telegram.ext import CommandHandler
from telegraph import Telegraph

from bot import dispatcher, LOGGER, telegraph_token, DEFAULT_SEARCH
from bot.helper.telegram_helper.message_utils import editMessage, sendMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper import button_build

logging.getLogger('aiohttp.client').setLevel(logging.ERROR)

telegraph_content = []
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
        link, resCount = getResult(list(search_results), key)
        if link is not None:
            buttons = button_build.ButtonMaker()
            buttons.buildbutton("🔎 VIEW", link)
            msg = f"<b>Found {resCount} result for <i>{key}</i></b>"
            button = InlineKeyboardMarkup(buttons.build_menu(1))
            editMessage(msg, srchmsg, button)
        else:
            editMessage(f"No result found for <i>{key}</i>", srchmsg)
    except IndexError:
        sendMessage("Send a search key along with command", context.bot, update)
    except Exception as e:
        LOGGER.error(str(e))

def getResult(search_results, key):
    path = []
    count = 0
    msg = f"Search Result For {key}<br><br>"
    for result in search_results:
        try:
            msg += f"<code><a href='{result['Url']}'>{result['Name']}</a></code><br>"
            msg += f"<b>Size: </b>{result['Size']}<br>"
            msg += f"<b>Seeders: </b>{result['Seeders']} | <b>Leechers: </b>{result['Leechers']}<br>"
        except:
            pass
        try:
            msg += f"<b>Link: </b>{result['Magnet']}<br>"
        except:
            pass
        try:
            for data in result["Files"]:
                msg += f"<b>Quality: </b><code>{data['Quality']}</code> | " \
                    f"<b>Size: </b>{data['Size']}<br>"
                msg += f"<b>Link: </b><code>{data['Magnet']}</code><br>"
            if result["Files"]:
                msg += "<br>"
        except:
            msg += "<br>"
        count += 1
        if len(msg.encode('utf-8')) > 40000 :
           telegraph_content.append(msg)
           msg = ""

    if msg != "":
        telegraph_content.append(msg)

    if len(telegraph_content) == 0:
        return None

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
    return f"https://telegra.ph/{path[0]}", count

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
        return

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
