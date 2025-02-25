from aiofiles.os import remove, path as aiopath
from aiofiles import open as aiopen
from asyncio import sleep, TimeoutError
from aioqbt.api import AddFormBuilder
from aiohttp.client_exceptions import ClientError

from .... import (
    task_dict,
    task_dict_lock,
    LOGGER,
    qb_torrents,
)
from ....core.config_manager import Config
from ....core.torrent_manager import TorrentManager
from ...ext_utils.bot_utils import bt_selection_buttons
from ...ext_utils.task_manager import check_running_tasks
from ...listeners.qbit_listener import on_download_start
from ...mirror_leech_utils.status_utils.qbit_status import QbittorrentStatus
from ...telegram_helper.message_utils import (
    send_message,
    delete_message,
    send_status_message,
)

"""
Only v1 torrents
#from hashlib import sha1
#from base64 import b16encode, b32decode
#from bencoding import bencode, bdecode
#from re import search as re_search
def _get_hash_magnet(mgt: str):
    hash_ = re_search(r'(?<=xt=urn:btih:)[a-zA-Z0-9]+', mgt).group(0)
    if len(hash_) == 32:
        hash_ = b16encode(b32decode(hash_.upper())).decode()
    return hash_

def _get_hash_file(fpath):
    with open(fpath, "rb") as f:
        decodedDict = bdecode(f.read())
        return sha1(bencode(decodedDict[b'info'])).hexdigest()
"""


async def add_qb_torrent(listener, path, ratio, seed_time):
    try:
        form = AddFormBuilder.with_client(TorrentManager.qbittorrent)
        if await aiopath.exists(listener.link):
            async with aiopen(listener.link, "rb") as f:
                data = await f.read()
                form = form.include_file(data)
        else:
            form = form.include_url(listener.link)
        form = form.savepath(path).tags([f"{listener.mid}"])
        add_to_queue, event = await check_running_tasks(listener)
        if add_to_queue:
            form = form.stopped(add_to_queue)
        if ratio:
            form = form.ratio_limit(ratio)
        if seed_time:
            form = form.seeding_time_limit(int(seed_time))
        try:
            await TorrentManager.qbittorrent.torrents.add(form.build())
        except (ClientError, TimeoutError, Exception) as e:
            LOGGER.error(
                f"{e}. {listener.mid}. Already added torrent or unsupported link/file type!"
            )
            await listener.on_download_error(
                f"{e}. {listener.mid}. Already added torrent or unsupported link/file type!"
            )
            return
        tor_info = await TorrentManager.qbittorrent.torrents.info(tag=f"{listener.mid}")
        if len(tor_info) == 0:
            while True:
                if add_to_queue and event.is_set():
                    add_to_queue = False
                tor_info = await TorrentManager.qbittorrent.torrents.info(
                    tag=f"{listener.mid}"
                )
                if len(tor_info) > 0:
                    break
                await sleep(1)
        tor_info = tor_info[0]
        listener.name = tor_info.name
        ext_hash = tor_info.hash

        async with task_dict_lock:
            task_dict[listener.mid] = QbittorrentStatus(listener, queued=add_to_queue)
        await on_download_start(f"{listener.mid}")

        if add_to_queue:
            LOGGER.info(f"Added to Queue/Download: {tor_info.name} - Hash: {ext_hash}")
        else:
            LOGGER.info(f"QbitDownload started: {tor_info.name} - Hash: {ext_hash}")

        await listener.on_download_start()

        if Config.BASE_URL and listener.select:
            if listener.link.startswith("magnet:"):
                metamsg = "Downloading Metadata, wait then you can select files. Use torrent file to avoid this wait."
                meta = await send_message(listener.message, metamsg)
                while True:
                    tor_info = await TorrentManager.qbittorrent.torrents.info(
                        tag=f"{listener.mid}"
                    )
                    if len(tor_info) == 0:
                        await delete_message(meta)
                        return
                    try:
                        tor_info = tor_info[0]
                        if tor_info.state not in [
                            "metaDL",
                            "checkingResumeData",
                            "stoppedDL",
                        ]:
                            await delete_message(meta)
                            break
                    except:
                        await delete_message(meta)
                        return

            ext_hash = tor_info.hash
            if not add_to_queue:
                await TorrentManager.qbittorrent.torrents.stop([ext_hash])
            SBUTTONS = bt_selection_buttons(ext_hash)
            msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
            await send_message(listener.message, msg, SBUTTONS)
        elif listener.multi <= 1:
            await send_status_message(listener.message)

        if event is not None:
            if not event.is_set():
                await event.wait()
                if listener.is_cancelled:
                    return
                async with task_dict_lock:
                    task_dict[listener.mid].queued = False
                LOGGER.info(
                    f"Start Queued Download from Qbittorrent: {tor_info.name} - Hash: {ext_hash}"
                )
            await on_download_start(f"{listener.mid}")
            await TorrentManager.qbittorrent.torrents.start([ext_hash])
    except (ClientError, TimeoutError, Exception) as e:
        if f"{listener.mid}" in qb_torrents:
            del qb_torrents[f"{listener.mid}"]
        await listener.on_download_error(f"{e}")
    finally:
        if await aiopath.exists(listener.link):
            await remove(listener.link)
