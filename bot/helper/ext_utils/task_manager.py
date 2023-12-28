from asyncio import Event, sleep

from bot.helper.mirror_utils.gdrive_utils.search import gdSearch
from bot.helper.ext_utils.files_utils import get_base_name
from bot.helper.ext_utils.bot_utils import sync_to_async, get_telegraph_list
from bot.helper.ext_utils.links_utils import is_gdrive_id
from bot import (
    config_dict,
    queued_dl,
    queued_up,
    non_queued_up,
    non_queued_dl,
    queue_dict_lock,
    LOGGER,
)


async def stop_duplicate_check(listener):
    if (
        isinstance(listener.upDest, int)
        or listener.isLeech
        or listener.select
        or not is_gdrive_id(listener.upDest)
        or listener.upDest.startswith("mtp:")
        and listener.stopDuplicate
        or not listener.stopDuplicate
        or listener.sameDir
    ):
        return False, None
    name = listener.name
    LOGGER.info(f"Checking File/Folder if already in Drive: {name}")
    if listener.compress:
        name = f"{name}.zip"
    elif listener.extract:
        try:
            name = get_base_name(name)
        except:
            name = None
    if name is not None:
        telegraph_content, contents_no = await sync_to_async(
            gdSearch(stopDup=True, noMulti=listener.isClone).drive_list,
            name,
            listener.upDest,
            listener.user_id,
        )
        if telegraph_content:
            msg = f"File/Folder is already available in Drive.\nHere are {contents_no} list results:"
            button = await get_telegraph_list(telegraph_content)
            return msg, button
    return False, None


async def is_queued(mid):
    all_limit = config_dict["QUEUE_ALL"]
    dl_limit = config_dict["QUEUE_DOWNLOAD"]
    event = None
    add_to_queue = False
    if all_limit or dl_limit:
        async with queue_dict_lock:
            dl = len(non_queued_dl)
            up = len(non_queued_up)
            if (
                all_limit and dl + up >= all_limit and (not dl_limit or dl >= dl_limit)
            ) or (dl_limit and dl >= dl_limit):
                add_to_queue = True
                event = Event()
                queued_dl[mid] = event
    return add_to_queue, event


async def start_dl_from_queued(mid):
    queued_dl[mid].set()
    del queued_dl[mid]
    await sleep(0.7)


async def start_up_from_queued(mid):
    queued_up[mid].set()
    del queued_up[mid]
    await sleep(0.7)


async def start_from_queued():
    if all_limit := config_dict["QUEUE_ALL"]:
        dl_limit = config_dict["QUEUE_DOWNLOAD"]
        up_limit = config_dict["QUEUE_UPLOAD"]
        async with queue_dict_lock:
            dl = len(non_queued_dl)
            up = len(non_queued_up)
            all_ = dl + up
            if all_ < all_limit:
                f_tasks = all_limit - all_
                if queued_up and (not up_limit or up < up_limit):
                    for index, mid in enumerate(list(queued_up.keys()), start=1):
                        f_tasks = all_limit - all_
                        await start_up_from_queued(mid)
                        f_tasks -= 1
                        if f_tasks == 0 or (up_limit and index >= up_limit - up):
                            break
                if queued_dl and (not dl_limit or dl < dl_limit) and f_tasks != 0:
                    for index, mid in enumerate(list(queued_dl.keys()), start=1):
                        await start_dl_from_queued(mid)
                        if (dl_limit and index >= dl_limit - dl) or index == f_tasks:
                            break
        return

    if up_limit := config_dict["QUEUE_UPLOAD"]:
        async with queue_dict_lock:
            up = len(non_queued_up)
            if queued_up and up < up_limit:
                f_tasks = up_limit - up
                for index, mid in enumerate(list(queued_up.keys()), start=1):
                    await start_up_from_queued(mid)
                    if index == f_tasks:
                        break
    else:
        async with queue_dict_lock:
            if queued_up:
                for mid in list(queued_up.keys()):
                    await start_up_from_queued(mid)

    if dl_limit := config_dict["QUEUE_DOWNLOAD"]:
        async with queue_dict_lock:
            dl = len(non_queued_dl)
            if queued_dl and dl < dl_limit:
                f_tasks = dl_limit - dl
                for index, mid in enumerate(list(queued_dl.keys()), start=1):
                    await start_dl_from_queued(mid)
                    if index == f_tasks:
                        break
    else:
        async with queue_dict_lock:
            if queued_dl:
                for mid in list(queued_dl.keys()):
                    await start_dl_from_queued(mid)
