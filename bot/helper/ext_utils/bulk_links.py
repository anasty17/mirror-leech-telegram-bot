from aiofiles import open as aiopen
from aiofiles.os import remove


def filterLinks(links_list: list, bulk_start: int, bulk_end: int) -> list:
    if bulk_start != 0 and bulk_end != 0:
        links_list = links_list[bulk_start:bulk_end]
    elif bulk_start != 0:
        links_list = links_list[bulk_start:]
    elif bulk_end != 0:
        links_list = links_list[:bulk_end]
    return links_list


def getLinksFromMessage(text: str) -> list:
    links_list = text.split("\n")
    return [item.strip() for item in links_list if len(item) != 0]


async def getLinksFromFile(message) -> list:
    links_list = []
    text_file_dir = await message.download()
    async with aiopen(text_file_dir, "r+") as f:
        lines = await f.readlines()
        links_list.extend(line.strip() for line in lines if len(line) != 0)
    await remove(text_file_dir)
    return links_list


async def extractBulkLinks(message, bulk_start: str, bulk_end: str) -> list:
    bulk_start = int(bulk_start)
    bulk_end = int(bulk_end)
    links_list = []
    if reply_to := message.reply_to_message:
        if (file_ := reply_to.document) and (file_.mime_type == "text/plain"):
            links_list = await getLinksFromFile(reply_to)
        elif text := reply_to.text:
            links_list = getLinksFromMessage(text)
    return filterLinks(links_list, bulk_start, bulk_end) if links_list else links_list
