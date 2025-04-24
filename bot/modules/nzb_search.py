from xml.etree import ElementTree as ET
from aiohttp import ClientSession

from .. import LOGGER
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.status_utils import get_readable_file_size
from ..helper.ext_utils.telegraph_helper import telegraph
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import edit_message, send_message


@new_task
async def hydra_search(_, message):
    key = message.text.split()
    if len(key) == 1:
        await send_message(
            message,
            "Please provide a search query. Example: `/nzbsearch movie title`.",
        )
        return

    query = " ".join(key[1:]).strip()
    message = await send_message(message, f"Searching for '{query}'...")
    try:
        items = await search_nzbhydra(query)
        if not items:
            await edit_message(message, "No results found.")
            LOGGER.info(f"No results found for search query: {query}")
            return

        page_url = await create_telegraph_page(query, items)
        buttons = ButtonMaker()
        buttons.url_button("Results", page_url)
        button = buttons.build_menu()
        await edit_message(
            message,
            f"Search results for '{query}' are available here",
            button,
        )
    except Exception as e:
        LOGGER.error(f"Error in hydra_search: {e!s}")
        await edit_message(message, "Something went wrong.")


async def search_nzbhydra(query, limit=50):
    search_url = f"{Config.HYDRA_IP}/api"
    params = {
        "apikey": Config.HYDRA_API_KEY,
        "t": "search",
        "q": query,
        "limit": limit,
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    }

    async with ClientSession() as session:
        try:
            async with session.get(
                search_url,
                params=params,
                headers=headers,
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    root = ET.fromstring(content)
                    return root.findall(".//item")

                LOGGER.error(
                    f"Failed to search NZBHydra. Status Code: {response.status}",
                )
                LOGGER.error(f"Response Text: {await response.text()}")
                return None
        except ET.ParseError:
            LOGGER.error("Failed to parse the XML response.")
            return None
        except Exception as e:
            LOGGER.error(f"Error in search_nzbhydra: {e!s}")
            return None


async def create_telegraph_page(query, items):
    content = "<b>Search Results:</b><br><br>"
    sorted_items = sorted(
        [
            (
                int(item.find("size").text) if item.find("size") is not None else 0,
                item,
            )
            for item in items[:100]
        ],
        reverse=True,
        key=lambda x: x[0],
    )

    for idx, (size_bytes, item) in enumerate(sorted_items, 1):
        title = (
            item.find("title").text
            if item.find("title") is not None
            else "No Title Available"
        )
        download_url = (
            item.find("link").text
            if item.find("link") is not None
            else "No Link Available"
        )
        size = get_readable_file_size(size_bytes)

        content += (
            f"{idx}. {title}<br>"
            f"<b><a href='{download_url}'>Download URL</a> | <a href='http://t.me/share/url?url={download_url}'>Share Download URL</a></b><br>"
            f"<b>Size:</b> {size}<br>"
            f"━━━━━━━━━━━━━━━━━━━━━━<br><br>"
        )

    response = await telegraph.create_page(
        title=f"Search Results for '{query}'",
        content=content,
    )
    LOGGER.info(f"Telegraph page created for search: {query}")
    return f"https://telegra.ph/{response['path']}"
