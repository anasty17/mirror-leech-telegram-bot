from httpx import AsyncClient
from html import escape
from urllib.parse import quote

from .. import LOGGER, qbittorrent_client
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import sync_to_async, new_task
from ..helper.ext_utils.status_utils import get_readable_file_size
from ..helper.ext_utils.telegraph_helper import telegraph
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import edit_message, send_message

PLUGINS = []
SITES = None
TELEGRAPH_LIMIT = 300


async def initiate_search_tools():
    qb_plugins = await sync_to_async(qbittorrent_client.search_plugins)
    if Config.SEARCH_PLUGINS:
        globals()["PLUGINS"] = []
        if qb_plugins:
            names = [plugin["name"] for plugin in qb_plugins]
            await sync_to_async(qbittorrent_client.search_uninstall_plugin, names=names)
        await sync_to_async(
            qbittorrent_client.search_install_plugin, Config.SEARCH_PLUGINS
        )
    elif qb_plugins:
        for plugin in qb_plugins:
            await sync_to_async(
                qbittorrent_client.search_uninstall_plugin, names=plugin["name"]
            )
        globals()["PLUGINS"] = []

    if Config.SEARCH_API_LINK:
        global SITES
        try:
            async with AsyncClient() as client:
                response = await client.get(f"{Config.SEARCH_API_LINK}/api/v1/sites")
                data = response.json()
            SITES = {
                str(site): str(site).capitalize() for site in data["supported_sites"]
            }
            SITES["all"] = "All"
        except Exception as e:
            LOGGER.error(
                f"{e} Can't fetching sites from SEARCH_API_LINK make sure use latest version of API"
            )
            SITES = None


async def search(key, site, message, method):
    if method.startswith("api"):
        if method == "apisearch":
            LOGGER.info(f"API Searching: {key} from {site}")
            if site == "all":
                api = f"{Config.SEARCH_API_LINK}/api/v1/all/search?query={key}&limit={Config.SEARCH_LIMIT}"
            else:
                api = f"{Config.SEARCH_API_LINK}/api/v1/search?site={site}&query={key}&limit={Config.SEARCH_LIMIT}"
        elif method == "apitrend":
            LOGGER.info(f"API Trending from {site}")
            if site == "all":
                api = f"{Config.SEARCH_API_LINK}/api/v1/all/trending?limit={Config.SEARCH_LIMIT}"
            else:
                api = f"{Config.SEARCH_API_LINK}/api/v1/trending?site={site}&limit={Config.SEARCH_LIMIT}"
        elif method == "apirecent":
            LOGGER.info(f"API Recent from {site}")
            if site == "all":
                api = f"{Config.SEARCH_API_LINK}/api/v1/all/recent?limit={Config.SEARCH_LIMIT}"
            else:
                api = f"{Config.SEARCH_API_LINK}/api/v1/recent?site={site}&limit={Config.SEARCH_LIMIT}"
        try:
            async with AsyncClient() as client:
                response = await client.get(api)
                search_results = response.json()
            if "error" in search_results or search_results["total"] == 0:
                await edit_message(
                    message,
                    f"No result found for <i>{key}</i>\nTorrent Site:- <i>{SITES.get(site)}</i>",
                )
                return
            msg = f"<b>Found {min(search_results['total'], TELEGRAPH_LIMIT)}</b>"
            if method == "apitrend":
                msg += f" <b>trending result(s)\nTorrent Site:- <i>{SITES.get(site)}</i></b>"
            elif method == "apirecent":
                msg += (
                    f" <b>recent result(s)\nTorrent Site:- <i>{SITES.get(site)}</i></b>"
                )
            else:
                msg += f" <b>result(s) for <i>{key}</i>\nTorrent Site:- <i>{SITES.get(site)}</i></b>"
            search_results = search_results["data"]
        except Exception as e:
            await edit_message(message, str(e))
            return
    else:
        LOGGER.info(f"PLUGINS Searching: {key} from {site}")
        search = await sync_to_async(
            qbittorrent_client.search_start, pattern=key, plugins=site, category="all"
        )
        search_id = search.id
        while True:
            result_status = await sync_to_async(
                qbittorrent_client.search_status, search_id=search_id
            )
            status = result_status[0].status
            if status != "Running":
                break
        dict_search_results = await sync_to_async(
            qbittorrent_client.search_results,
            search_id=search_id,
            limit=TELEGRAPH_LIMIT,
        )
        search_results = dict_search_results.results
        total_results = dict_search_results.total
        if total_results == 0:
            await edit_message(
                message,
                f"No result found for <i>{key}</i>\nTorrent Site:- <i>{site.capitalize()}</i>",
            )
            return
        msg = f"<b>Found {min(total_results, TELEGRAPH_LIMIT)}</b>"
        msg += f" <b>result(s) for <i>{key}</i>\nTorrent Site:- <i>{site.capitalize()}</i></b>"
        await sync_to_async(qbittorrent_client.search_delete, search_id=search_id)
    link = await get_result(search_results, key, message, method)
    buttons = ButtonMaker()
    buttons.url_button("🔎 VIEW", link)
    button = buttons.build_menu(1)
    await edit_message(message, msg, button)


async def get_result(search_results, key, message, method):
    telegraph_content = []
    if method == "apirecent":
        msg = "<h4>API Recent Results</h4>"
    elif method == "apisearch":
        msg = f"<h4>API Search Result(s) For {key}</h4>"
    elif method == "apitrend":
        msg = "<h4>API Trending Results</h4>"
    else:
        msg = f"<h4>PLUGINS Search Result(s) For {key}</h4>"
    for index, result in enumerate(search_results, start=1):
        if method.startswith("api"):
            try:
                if "name" in result.keys():
                    msg += f"<code><a href='{result['url']}'>{escape(result['name'])}</a></code><br>"
                if "torrents" in result.keys():
                    for subres in result["torrents"]:
                        msg += f"<b>Quality: </b>{subres['quality']} | <b>Type: </b>{subres['type']} | "
                        msg += f"<b>Size: </b>{subres['size']}<br>"
                        if "torrent" in subres.keys():
                            msg += f"<a href='{subres['torrent']}'>Direct Link</a><br>"
                        elif "magnet" in subres.keys():
                            msg += "<b>Share Magnet to</b> "
                            msg += f"<a href='http://t.me/share/url?url={subres['magnet']}'>Telegram</a><br>"
                    msg += "<br>"
                else:
                    msg += f"<b>Size: </b>{result['size']}<br>"
                    try:
                        msg += f"<b>Seeders: </b>{result['seeders']} | <b>Leechers: </b>{result['leechers']}<br>"
                    except:
                        pass
                    if "torrent" in result.keys():
                        msg += f"<a href='{result['torrent']}'>Direct Link</a><br><br>"
                    elif "magnet" in result.keys():
                        msg += "<b>Share Magnet to</b> "
                        msg += f"<a href='http://t.me/share/url?url={quote(result['magnet'])}'>Telegram</a><br><br>"
                    else:
                        msg += "<br>"
            except:
                continue
        else:
            msg += f"<a href='{result.descrLink}'>{escape(result.fileName)}</a><br>"
            msg += f"<b>Size: </b>{get_readable_file_size(result.fileSize)}<br>"
            msg += f"<b>Seeders: </b>{result.nbSeeders} | <b>Leechers: </b>{result.nbLeechers}<br>"
            link = result.fileUrl
            if link.startswith("magnet:"):
                msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={quote(link)}'>Telegram</a><br><br>"
            else:
                msg += f"<a href='{link}'>Direct Link</a><br><br>"

        if len(msg.encode("utf-8")) > 39000:
            telegraph_content.append(msg)
            msg = ""

        if index == TELEGRAPH_LIMIT:
            break

    if msg != "":
        telegraph_content.append(msg)

    await edit_message(
        message, f"<b>Creating</b> {len(telegraph_content)} <b>Telegraph pages.</b>"
    )
    path = [
        (
            await telegraph.create_page(
                title="Mirror-leech-bot Torrent Search", content=content
            )
        )["path"]
        for content in telegraph_content
    ]
    if len(path) > 1:
        await edit_message(
            message, f"<b>Editing</b> {len(telegraph_content)} <b>Telegraph pages.</b>"
        )
        await telegraph.edit_telegraph(path, telegraph_content)
    return f"https://telegra.ph/{path[0]}"


def api_buttons(user_id, method):
    buttons = ButtonMaker()
    for data, name in SITES.items():
        buttons.data_button(name, f"torser {user_id} {data} {method}")
    buttons.data_button("Cancel", f"torser {user_id} cancel")
    return buttons.build_menu(2)


async def plugin_buttons(user_id):
    buttons = ButtonMaker()
    if not PLUGINS:
        pl = await sync_to_async(qbittorrent_client.search_plugins)
        for name in pl:
            PLUGINS.append(name["name"])
    for siteName in PLUGINS:
        buttons.data_button(
            siteName.capitalize(), f"torser {user_id} {siteName} plugin"
        )
    buttons.data_button("All", f"torser {user_id} all plugin")
    buttons.data_button("Cancel", f"torser {user_id} cancel")
    return buttons.build_menu(2)


@new_task
async def torrent_search(_, message):
    user_id = message.from_user.id
    buttons = ButtonMaker()
    key = message.text.split()
    if SITES is None and not Config.SEARCH_PLUGINS:
        await send_message(
            message, "No API link or search PLUGINS added for this function"
        )
    elif len(key) == 1 and SITES is None:
        await send_message(message, "Send a search key along with command")
    elif len(key) == 1:
        buttons.data_button("Trending", f"torser {user_id} apitrend")
        buttons.data_button("Recent", f"torser {user_id} apirecent")
        buttons.data_button("Cancel", f"torser {user_id} cancel")
        button = buttons.build_menu(2)
        await send_message(message, "Send a search key along with command", button)
    elif SITES is not None and Config.SEARCH_PLUGINS:
        buttons.data_button("Api", f"torser {user_id} apisearch")
        buttons.data_button("Plugins", f"torser {user_id} plugin")
        buttons.data_button("Cancel", f"torser {user_id} cancel")
        button = buttons.build_menu(2)
        await send_message(message, "Choose tool to search:", button)
    elif SITES is not None:
        button = api_buttons(user_id, "apisearch")
        await send_message(message, "Choose site to search | API:", button)
    else:
        button = await plugin_buttons(user_id)
        await send_message(message, "Choose site to search | Plugins:", button)


@new_task
async def torrent_search_update(_, query):
    user_id = query.from_user.id
    message = query.message
    key = message.reply_to_message.text.split(maxsplit=1)
    key = key[1].strip() if len(key) > 1 else None
    data = query.data.split()
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
    elif data[2].startswith("api"):
        await query.answer()
        button = api_buttons(user_id, data[2])
        await edit_message(message, "Choose site:", button)
    elif data[2] == "plugin":
        await query.answer()
        button = await plugin_buttons(user_id)
        await edit_message(message, "Choose site:", button)
    elif data[2] != "cancel":
        await query.answer()
        site = data[2]
        method = data[3]
        if method.startswith("api"):
            if key is None:
                if method == "apirecent":
                    endpoint = "Recent"
                elif method == "apitrend":
                    endpoint = "Trending"
                await edit_message(
                    message,
                    f"<b>Listing {endpoint} Items...\nTorrent Site:- <i>{SITES.get(site)}</i></b>",
                )
            else:
                await edit_message(
                    message,
                    f"<b>Searching for <i>{key}</i>\nTorrent Site:- <i>{SITES.get(site)}</i></b>",
                )
        else:
            await edit_message(
                message,
                f"<b>Searching for <i>{key}</i>\nTorrent Site:- <i>{site.capitalize()}</i></b>",
            )
        await search(key, site, message, method)
    else:
        await query.answer()
        await edit_message(message, "Search has been canceled!")
