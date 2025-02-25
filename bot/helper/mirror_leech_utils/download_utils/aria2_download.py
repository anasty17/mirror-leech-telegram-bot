from aiofiles.os import remove, path as aiopath
from aiofiles import open as aiopen
from base64 import b64encode
from aiohttp.client_exceptions import ClientError
from asyncio import TimeoutError

from .... import task_dict_lock, task_dict, LOGGER
from ....core.config_manager import Config
from ....core.torrent_manager import TorrentManager, is_metadata, aria2_name
from ...ext_utils.bot_utils import bt_selection_buttons
from ...ext_utils.task_manager import check_running_tasks
from ...mirror_leech_utils.status_utils.aria2_status import Aria2Status
from ...telegram_helper.message_utils import send_status_message, send_message


async def add_aria2_download(listener, dpath, header, ratio, seed_time):
    a2c_opt = {"dir": dpath}
    if listener.name:
        a2c_opt["out"] = listener.name
    if header:
        a2c_opt["header"] = header
    if ratio:
        a2c_opt["seed-ratio"] = ratio
    if seed_time:
        a2c_opt["seed-time"] = seed_time
    if TORRENT_TIMEOUT := Config.TORRENT_TIMEOUT:
        a2c_opt["bt-stop-timeout"] = f"{TORRENT_TIMEOUT}"

    add_to_queue, event = await check_running_tasks(listener)
    if add_to_queue:
        if listener.link.startswith("magnet:"):
            a2c_opt["pause-metadata"] = "true"
        else:
            a2c_opt["pause"] = "true"

    try:
        if await aiopath.exists(listener.link):
            async with aiopen(listener.link, "rb") as tf:
                torrent = await tf.read()
            encoded = b64encode(torrent).decode()
            params = [encoded, [], a2c_opt]
            gid = await TorrentManager.aria2.jsonrpc("addTorrent", params)
            """gid = await TorrentManager.aria2.add_torrent(path=listener.link, options=a2c_opt)"""
        else:
            gid = await TorrentManager.aria2.addUri(
                uris=[listener.link], options=a2c_opt
            )
    except (TimeoutError, ClientError, Exception) as e:
        LOGGER.info(f"Aria2c Download Error: {e}")
        await listener.on_download_error(f"{e}")
        return
    download = await TorrentManager.aria2.tellStatus(gid)
    if download.get("errorMessage"):
        error = str(download["errorMessage"]).replace("<", " ").replace(">", " ")
        LOGGER.info(f"Aria2c Download Error: {error}")
        await TorrentManager.aria2_remove(download)
        await listener.on_download_error(error)
        return
    if await aiopath.exists(listener.link):
        await remove(listener.link)

    name = aria2_name(download)
    async with task_dict_lock:
        task_dict[listener.mid] = Aria2Status(listener, gid, queued=add_to_queue)
    if add_to_queue:
        LOGGER.info(f"Added to Queue/Download: {name}. Gid: {gid}")
        if (
            not listener.select or "bittorrent" not in download
        ) and listener.multi <= 1:
            await send_status_message(listener.message)
    else:
        LOGGER.info(f"Aria2Download started: {name}. Gid: {gid}")

    await listener.on_download_start()

    if (
        not add_to_queue
        and (not listener.select or not Config.BASE_URL)
        and listener.multi <= 1
    ):
        await send_status_message(listener.message)
    elif listener.select and "bittorrent" in download and not is_metadata(download):
        if not add_to_queue:
            await TorrentManager.aria2.forcePause(gid)
        SBUTTONS = bt_selection_buttons(gid)
        msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
        await send_message(listener.message, msg, SBUTTONS)

    if add_to_queue:
        await event.wait()
        if listener.is_cancelled:
            return
        async with task_dict_lock:
            task = task_dict[listener.mid]
            task.queued = False
            await task.update()
            new_gid = task.gid()

        await TorrentManager.aria2.unpause(new_gid)
        LOGGER.info(f"Start Queued Download from Aria2c: {name}. Gid: {new_gid}")
