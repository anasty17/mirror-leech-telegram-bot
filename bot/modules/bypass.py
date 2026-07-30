from re import sub as re_sub

from aiofiles import open as aiopen
from aiofiles.os import remove, path as aiopath

from ..helper.ext_utils.bot_utils import sync_to_async, new_task
from ..helper.ext_utils.exceptions import DirectDownloadLinkException
from ..helper.mirror_leech_utils.download_utils.bypass_dispatcher import bypass_scrape
from ..helper.telegram_helper.message_utils import (
    delete_message,
    edit_message,
    send_file,
    send_message,
)


def _slug(title):
    s = re_sub(r"[^a-zA-Z0-9_-]+", "", title.replace(" ", "_"))[:60]
    return s or "bypass"


@new_task
async def bypass_scrape_cmd(_, message):
    args = message.text.split(maxsplit=2)
    link = args[1] if len(args) > 1 else ""
    keyword = args[2].strip() if len(args) > 2 else ""
    if not link and (reply_to := message.reply_to_message):
        link = reply_to.text.split(maxsplit=1)[0].strip()

    if not link:
        await send_message(
            message,
            "Send a thread URL with the command or reply to a message with the URL.\n"
            "<code>/bypass &lt;url&gt; [keyword]</code>",
        )
        return

    status = await send_message(message, "⏳ Scraping thread...")
    try:
        title, links = await sync_to_async(bypass_scrape, link, keyword)
    except DirectDownloadLinkException as e:
        await edit_message(status, str(e))
        return

    if not links:
        await edit_message(status, "❌ No links found.")
        return

    path = f"{_slug(title)}_links.txt"
    async with aiopen(path, "w") as f:
        await f.write("\n".join(links))

    summary = f"📊 <b>{title}</b>\n🔗 {len(links)} links"
    if keyword:
        summary += f" (filter: <code>{keyword}</code>)"
    await send_file(message, path, caption=summary)
    await delete_message(status)
    if await aiopath.exists(path):
        await remove(path)
