from aiofiles.os import remove, path as aiopath

from bot import (
    aria2,
    task_dict_lock,
    task_dict,
    LOGGER,
    config_dict,
    aria2_options,
    aria2c_global,
    non_queued_dl,
    queue_dict_lock,
)
from bot.helper.ext_utils.bot_utils import bt_selection_buttons, sync_to_async
from bot.helper.ext_utils.task_manager import check_running_tasks
from bot.helper.mirror_leech_utils.status_utils.aria2_status import Aria2Status
from bot.helper.telegram_helper.message_utils import sendStatusMessage, sendMessage


async def add_aria2c_download(listener, dpath, header, ratio, seed_time):
    a2c_opt = {**aria2_options}
    [a2c_opt.pop(k) for k in aria2c_global if k in aria2_options]
    a2c_opt["dir"] = dpath
    if listener.name:
        a2c_opt["out"] = listener.name
    if header:
        a2c_opt["header"] = header
    if ratio:
        a2c_opt["seed-ratio"] = ratio
    if seed_time:
        a2c_opt["seed-time"] = seed_time
    if TORRENT_TIMEOUT := config_dict["TORRENT_TIMEOUT"]:
        a2c_opt["bt-stop-timeout"] = f"{TORRENT_TIMEOUT}"

    add_to_queue, event = await check_running_tasks(listener)
    if add_to_queue:
        if listener.link.startswith("magnet:"):
            a2c_opt["pause-metadata"] = "true"
        else:
            a2c_opt["pause"] = "true"

    try:
        download = (await sync_to_async(aria2.add, listener.link, a2c_opt))[0]
    except Exception as e:
        LOGGER.info(f"Aria2c Download Error: {e}")
        await listener.onDownloadError(f"{e}")
        return
    if await aiopath.exists(listener.link):
        await remove(listener.link)
    if download.error_message:
        error = str(download.error_message).replace("<", " ").replace(">", " ")
        LOGGER.info(f"Aria2c Download Error: {error}")
        await listener.onDownloadError(error)
        return

    gid = download.gid
    name = download.name
    async with task_dict_lock:
        task_dict[listener.mid] = Aria2Status(listener, gid, queued=add_to_queue)
    if add_to_queue:
        LOGGER.info(f"Added to Queue/Download: {name}. Gid: {gid}")
        if (not listener.select or not download.is_torrent) and listener.multi <= 1:
            await sendStatusMessage(listener.message)
    else:
        LOGGER.info(f"Aria2Download started: {name}. Gid: {gid}")

    await listener.onDownloadStart()

    if (
        not add_to_queue
        and (not listener.select or not config_dict["BASE_URL"])
        and listener.multi <= 1
    ):
        await sendStatusMessage(listener.message)
    elif listener.select and download.is_torrent and not download.is_metadata:
        if not add_to_queue:
            await sync_to_async(aria2.client.force_pause, gid)
        SBUTTONS = bt_selection_buttons(gid)
        msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
        await sendMessage(listener.message, msg, SBUTTONS)

    if add_to_queue:
        await event.wait()
        if listener.isCancelled:
            return
        async with queue_dict_lock:
            non_queued_dl.add(listener.mid)
        async with task_dict_lock:
            task = task_dict[listener.mid]
            task.queued = False
            await sync_to_async(task.update)
            new_gid = task.gid()

        await sync_to_async(aria2.client.unpause, new_gid)
        LOGGER.info(f"Start Queued Download from Aria2c: {name}. Gid: {gid}")
