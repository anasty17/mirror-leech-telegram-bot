from requests import get as rget
from time import sleep
from threading import Thread
from html import escape
from urllib.parse import quote
from telegram import InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler

from bot import dispatcher, LOGGER, SEARCH_API_LINK, SEARCH_PLUGINS, get_client, SEARCH_LIMIT
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.telegram_helper.message_utils import editMessage, sendMessage, sendMarkup
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.bot_utils import get_readable_file_size
from bot.helper.telegram_helper import button_build

if SEARCH_PLUGINS is not None:
    PLUGINS = []
    qbclient = get_client()
    qb_plugins = qbclient.search_plugins()
    if qb_plugins:
        for plugin in qb_plugins:
            qbclient.search_uninstall_plugin(names=plugin['name'])
    qbclient.search_install_plugin(SEARCH_PLUGINS)
    qbclient.auth_log_out()

SITES = {
    "1337x": "1337x",
    "yts": "YTS",
    "tgx": "TorrentGalaxy",
    "torlock": "Torlock",
    "piratebay": "PirateBay",
    "nyaasi": "NyaaSi",
    "zooqle": "Zooqle",
    "kickass": "KickAss",
    "bitsearch": "Bitsearch",
    "glodls": "Glodls",
    "magnetdl": "MagnetDL",
    "limetorrent": "LimeTorrent",
    "torrentfunk": "TorrentFunk",
    "torrentproject": "TorrentProject",
    "libgen": "Libgen",
    "ybt": "YourBittorrent",
    "all": "All"
}

TELEGRAPH_LIMIT = 300


def torser(update, context):
    user_id = update.message.from_user.id
    key = update.message.text.split(" ", maxsplit=1)
    buttons = button_build.ButtonMaker()
    if SEARCH_API_LINK is  None and SEARCH_PLUGINS is None:
        sendMessage("No API link or search PLUGINS added for this function", context.bot, update.message)
    elif len(key) == 1 and SEARCH_API_LINK is None:
        sendMessage("Send a search key along with command", context.bot, update.message)
    elif len(key) == 1:
        buttons.sbutton('Trending', f"torser {user_id} apitrend")
        buttons.sbutton('Recent', f"torser {user_id} apirecent")
        buttons.sbutton("Cancel", f"torser {user_id} cancel")
        button = InlineKeyboardMarkup(buttons.build_menu(2))
        sendMarkup("Send a search key along with command", context.bot, update.message, button)
    elif SEARCH_API_LINK is not None and SEARCH_PLUGINS is not None:
        buttons.sbutton('Api', f"torser {user_id} apisearch")
        buttons.sbutton('Plugins', f"torser {user_id} plugin")
        buttons.sbutton("Cancel", f"torser {user_id} cancel")
        button = InlineKeyboardMarkup(buttons.build_menu(2))
        sendMarkup('Choose tool to search:', context.bot, update.message, button)
    elif SEARCH_API_LINK is not None and SEARCH_PLUGINS is None:
        button = _api_buttons(user_id, "apisearch")
        sendMarkup('Choose site to search:', context.bot, update.message, button)
    elif SEARCH_API_LINK is None and SEARCH_PLUGINS is not None:
        button = _plugin_buttons(user_id)
        sendMarkup('Choose site to search:', context.bot, update.message, button)

def torserbut(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    message = query.message
    key = message.reply_to_message.text.split(" ", maxsplit=1)
    if len(key) > 1:
        key = key[1]
    else:
        key = None
    data = query.data
    data = data.split(" ")
    if user_id != int(data[1]):
        query.answer(text="Not Yours!", show_alert=True)
    elif data[2].startswith('api'):
        query.answer()
        button = _api_buttons(user_id, data[2])
        editMessage('Choose site:', message, button)
    elif data[2] == 'plugin':
        query.answer()
        button = _plugin_buttons(user_id)
        editMessage('Choose site:', message, button)
    elif data[2] != "cancel":
        query.answer()
        site = data[2]
        method = data[3]
        if method.startswith('api'):
            if key is None:
                if method == 'apitrend':
                    endpoint = 'Trending'
                elif method == 'apirecent':
                    endpoint = 'Recent'
                editMessage(f"<b>Listing {endpoint} Items...\nTorrent Site:- <i>{SITES.get(site)}</i></b>", message)
            else:
                editMessage(f"<b>Searching for <i>{key}</i>\nTorrent Site:- <i>{SITES.get(site)}</i></b>", message)
        else:
            editMessage(f"<b>Searching for <i>{key}</i>\nTorrent Site:- <i>{site.capitalize()}</i></b>", message)
        Thread(target=_search, args=(key, site, message, method)).start()
    else:
        query.answer()
        editMessage("Search has been canceled!", message)

def _search(key, site, message, method):
    if method.startswith('api'):
        if method == 'apisearch':
            LOGGER.info(f"API Searching: {key} from {site}")
            if site == 'all':
                api = f"{SEARCH_API_LINK}/api/v1/all/search?query={key}&limit={SEARCH_LIMIT}"
            else:
                api = f"{SEARCH_API_LINK}/api/v1/search?site={site}&query={key}&limit={SEARCH_LIMIT}"
        elif method == 'apitrend':
            LOGGER.info(f"API Trending from {site}")
            if site == 'all':
                api = f"{SEARCH_API_LINK}/api/v1/all/trending?limit={SEARCH_LIMIT}"
            else:
                api = f"{SEARCH_API_LINK}/api/v1/trending?site={site}&limit={SEARCH_LIMIT}"
        elif method == 'apirecent':
            LOGGER.info(f"API Recent from {site}")
            if site == 'all':
                api = f"{SEARCH_API_LINK}/api/v1/all/recent?limit={SEARCH_LIMIT}"
            else:
                api = f"{SEARCH_API_LINK}/api/v1/recent?site={site}&limit={SEARCH_LIMIT}"
        try:
            resp = rget(api)
            search_results = resp.json()
            if "error" in search_results.keys():
                return editMessage(f"No result found for <i>{key}</i>\nTorrent Site:- <i>{SITES.get(site)}</i>", message)
            msg = f"<b>Found {min(search_results['total'], TELEGRAPH_LIMIT)}</b>"
            if method == 'apitrend':
                msg += f" <b>trending result(s)\nTorrent Site:- <i>{SITES.get(site)}</i></b>"
            elif method == 'apirecent':
                msg += f" <b>recent result(s)\nTorrent Site:- <i>{SITES.get(site)}</i></b>"
            else:
                msg += f" <b>result(s) for <i>{key}</i>\nTorrent Site:- <i>{SITES.get(site)}</i></b>"
            search_results = search_results['data']
        except Exception as e:
            return editMessage(str(e), message)
    else:
        LOGGER.info(f"PLUGINS Searching: {key} from {site}")
        client = get_client()
        search = client.search_start(pattern=str(key), plugins=str(site), category='all')
        search_id = search.id
        while True:
            result_status = client.search_status(search_id=search_id)
            status = result_status[0].status
            if status != 'Running':
                break
        dict_search_results = client.search_results(search_id=search_id)
        search_results = dict_search_results.results
        total_results = dict_search_results.total
        if total_results == 0:
            return editMessage(f"No result found for <i>{key}</i>\nTorrent Site:- <i>{site.capitalize()}</i>", message)
        msg = f"<b>Found {min(total_results, TELEGRAPH_LIMIT)}</b>"
        msg += f" <b>result(s) for <i>{key}</i>\nTorrent Site:- <i>{site.capitalize()}</i></b>"
    link = _getResult(search_results, key, message, method)
    buttons = button_build.ButtonMaker()
    buttons.buildbutton("🔎 VIEW", link)
    button = InlineKeyboardMarkup(buttons.build_menu(1))
    editMessage(msg, message, button)
    if not method.startswith('api'):
        client.search_delete(search_id=search_id)

def _getResult(search_results, key, message, method):
    telegraph_content = []
    if method == 'apirecent':
        msg = "<h4>API Recent Results</h4>"
    elif method == 'apisearch':
        msg = f"<h4>API Search Result(s) For {key}</h4>"
    elif method == 'apitrend':
        msg = "<h4>API Trending Results</h4>"
    else:
        msg = f"<h4>PLUGINS Search Result(s) For {key}</h4>"
    for index, result in enumerate(search_results, start=1):
        if method.startswith('api'):
            if 'name' in result.keys():
                msg += f"<code><a href='{result['url']}'>{escape(result['name'])}</a></code><br>"
            if 'torrents' in result.keys():
                for subres in result['torrents']:
                    msg += f"<b>Quality: </b>{subres['quality']} | <b>Type: </b>{subres['type']} | <b>Size: </b>{subres['size']}<br>"
                    if 'torrent' in subres.keys():
                        msg += f"<a href='{subres['torrent']}'>Direct Link</a><br>"
                    elif 'magnet' in subres.keys():
                        msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={subres['magnet']}'>Telegram</a><br>"
                msg += '<br>'
            else:
                msg += f"<b>Size: </b>{result['size']}<br>"
                try:
                    msg += f"<b>Seeders: </b>{result['seeders']} | <b>Leechers: </b>{result['leechers']}<br>"
                except:
                    pass
                if 'torrent' in result.keys():
                    msg += f"<a href='{result['torrent']}'>Direct Link</a><br><br>"
                elif 'magnet' in result.keys():
                    msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={quote(result['magnet'])}'>Telegram</a><br><br>"
        else:
            msg += f"<a href='{result.descrLink}'>{escape(result.fileName)}</a><br>"
            msg += f"<b>Size: </b>{get_readable_file_size(result.fileSize)}<br>"
            msg += f"<b>Seeders: </b>{result.nbSeeders} | <b>Leechers: </b>{result.nbLeechers}<br>"
            link = result.fileUrl
            if link.startswith('magnet:'):
                msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={quote(link)}'>Telegram</a><br><br>"
            else:
                msg += f"<a href='{link}'>Direct Link</a><br><br>"

        if len(msg.encode('utf-8')) > 39000:
           telegraph_content.append(msg)
           msg = ""

        if index == TELEGRAPH_LIMIT:
            break

    if msg != "":
        telegraph_content.append(msg)

    editMessage(f"<b>Creating</b> {len(telegraph_content)} <b>Telegraph pages.</b>", message)
    path = [telegraph.create_page(
                title='Mirror-leech-bot Torrent Search',
                content=content
            )["path"] for content in telegraph_content]
    sleep(0.5)
    if len(path) > 1:
        editMessage(f"<b>Editing</b> {len(telegraph_content)} <b>Telegraph pages.</b>", message)
        telegraph.edit_telegraph(path, telegraph_content)
    return f"https://telegra.ph/{path[0]}"

def _api_buttons(user_id, method):
    buttons = button_build.ButtonMaker()
    for data, name in SITES.items():
        buttons.sbutton(name, f"torser {user_id} {data} {method}")
    buttons.sbutton("Cancel", f"torser {user_id} cancel")
    return InlineKeyboardMarkup(buttons.build_menu(2))

def _plugin_buttons(user_id):
    buttons = button_build.ButtonMaker()
    if not PLUGINS:
        qbclient = get_client()
        pl = qbclient.search_plugins()
        for name in pl:
            PLUGINS.append(name['name'])
        qbclient.auth_log_out()
    for siteName in PLUGINS:
        buttons.sbutton(siteName.capitalize(), f"torser {user_id} {siteName} plugin")
    buttons.sbutton('All', f"torser {user_id} all plugin")
    buttons.sbutton("Cancel", f"torser {user_id} cancel")
    return InlineKeyboardMarkup(buttons.build_menu(2))


torser_handler = CommandHandler(BotCommands.SearchCommand, torser, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
torserbut_handler = CallbackQueryHandler(torserbut, pattern="torser", run_async=True)

dispatcher.add_handler(torser_handler)
dispatcher.add_handler(torserbut_handler)
