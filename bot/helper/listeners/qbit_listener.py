from aiofiles.os import remove, path as aiopath
from asyncio import sleep, gather
from time import time

from bot import (
    task_dict,
    task_dict_lock,
    Intervals,
    get_qb_client,
    config_dict,
    QbTorrents,
    qb_listener_lock,
    LOGGER,
    bot_loop,
)
from bot.helper.ext_utils.bot_utils import new_task, sync_to_async
from bot.helper.ext_utils.files_utils import clean_unwanted
from bot.helper.ext_utils.status_utils import get_readable_time, getTaskByGid
from bot.helper.ext_utils.task_manager import stop_duplicate_check
from bot.helper.mirror_leech_utils.status_utils.qbit_status import QbittorrentStatus
from bot.helper.telegram_helper.message_utils import update_status_message


async def _remove_torrent(client, hash_, tag):
    await sync_to_async(client.torrents_delete, torrent_hashes=hash_, delete_files=True)
    async with qb_listener_lock:
        if tag in QbTorrents:
            del QbTorrents[tag]
    await sync_to_async(client.torrents_delete_tags, tags=tag)
    await sync_to_async(client.auth_log_out)


@new_task
async def _onDownloadError(err, tor, button=None):
    LOGGER.info(f"Cancelling Download: {tor.name}")
    ext_hash = tor.hash
    task = await getTaskByGid(ext_hash[:12])
    if not hasattr(task, "client"):
        return
    await gather(
        task.listener.onDownloadError(err, button),
        sync_to_async(task.client.torrents_pause, torrent_hashes=ext_hash),
    )
    await sleep(0.3)
    await _remove_torrent(task.client, ext_hash, tor.tags)


@new_task
async def _onSeedFinish(tor):
    ext_hash = tor.hash
    LOGGER.info(f"Cancelling Seed: {tor.name}")
    task = await getTaskByGid(ext_hash[:12])
    if not hasattr(task, "client"):
        return
    msg = f"Seeding stopped with Ratio: {round(tor.ratio, 3)} and Time: {get_readable_time(tor.seeding_time)}"
    await task.listener.onUploadError(msg)
    await _remove_torrent(task.client, ext_hash, tor.tags)


@new_task
async def _stop_duplicate(tor):
    task = await getTaskByGid(tor.hash[:12])
    if not hasattr(task, "listener"):
        return
    if task.listener.stopDuplicate:
        task.listener.name = tor.content_path.rsplit("/", 1)[-1].rsplit(".!qB", 1)[0]
        msg, button = await stop_duplicate_check(task.listener)
        if msg:
            _onDownloadError(msg, tor, button)


@new_task
async def _onDownloadComplete(tor):
    ext_hash = tor.hash
    tag = tor.tags
    task = await getTaskByGid(ext_hash[:12])
    if not task.listener.seed:
        await sync_to_async(task.client.torrents_pause, torrent_hashes=ext_hash)
    if task.listener.select:
        await clean_unwanted(task.listener.dir)
        path = tor.content_path.rsplit("/", 1)[0]
        res = await sync_to_async(task.client.torrents_files, torrent_hash=ext_hash)
        for f in res:
            if f.priority == 0 and await aiopath.exists(f"{path}/{f.name}"):
                try:
                    await remove(f"{path}/{f.name}")
                except:
                    pass
    await task.listener.onDownloadComplete()
    if Intervals["stopAll"]:
        return
    if task.listener.seed and not task.listener.isCancelled:
        async with task_dict_lock:
            if task.listener.mid in task_dict:
                removed = False
                task_dict[task.listener.mid] = QbittorrentStatus(task.listener, True)
            else:
                removed = True
        if removed:
            await _remove_torrent(task.client, ext_hash, tag)
            return
        async with qb_listener_lock:
            if tag in QbTorrents:
                QbTorrents[tag]["seeding"] = True
            else:
                return
        await update_status_message(task.listener.message.chat.id)
        LOGGER.info(f"Seeding started: {tor.name} - Hash: {ext_hash}")
    else:
        await _remove_torrent(task.client, ext_hash, tag)


async def _qb_listener():
    client = get_qb_client()
    while True:
        async with qb_listener_lock:
            try:
                torrents = await sync_to_async(client.torrents_info)
                if len(torrents) == 0:
                    Intervals["qb"] = ""
                    await sync_to_async(client.auth_log_out)
                    break
                for tor_info in torrents:
                    tag = tor_info.tags
                    if tag not in QbTorrents:
                        continue
                    state = tor_info.state
                    if state == "metaDL":
                        TORRENT_TIMEOUT = config_dict["TORRENT_TIMEOUT"]
                        QbTorrents[tag]["stalled_time"] = time()
                        if (
                            TORRENT_TIMEOUT
                            and time() - tor_info.added_on >= TORRENT_TIMEOUT
                        ):
                            _onDownloadError("Dead Torrent!", tor_info)
                        else:
                            await sync_to_async(
                                client.torrents_reannounce, torrent_hashes=tor_info.hash
                            )
                    elif state == "downloading":
                        QbTorrents[tag]["stalled_time"] = time()
                        if not QbTorrents[tag]["stop_dup_check"]:
                            QbTorrents[tag]["stop_dup_check"] = True
                            _stop_duplicate(tor_info)
                    elif state == "stalledDL":
                        TORRENT_TIMEOUT = config_dict["TORRENT_TIMEOUT"]
                        if (
                            not QbTorrents[tag]["rechecked"]
                            and 0.99989999999999999 < tor_info.progress < 1
                        ):
                            msg = f"Force recheck - Name: {tor_info.name} Hash: "
                            msg += f"{tor_info.hash} Downloaded Bytes: {tor_info.downloaded} "
                            msg += f"Size: {tor_info.size} Total Size: {tor_info.total_size}"
                            LOGGER.warning(msg)
                            await sync_to_async(
                                client.torrents_recheck, torrent_hashes=tor_info.hash
                            )
                            QbTorrents[tag]["rechecked"] = True
                        elif (
                            TORRENT_TIMEOUT
                            and time() - QbTorrents[tag]["stalled_time"]
                            >= TORRENT_TIMEOUT
                        ):
                            _onDownloadError("Dead Torrent!", tor_info)
                        else:
                            await sync_to_async(
                                client.torrents_reannounce, torrent_hashes=tor_info.hash
                            )
                    elif state == "missingFiles":
                        await sync_to_async(
                            client.torrents_recheck, torrent_hashes=tor_info.hash
                        )
                    elif state == "error":
                        _onDownloadError(
                            "No enough space for this torrent on device", tor_info
                        )
                    elif (
                        tor_info.completion_on != 0
                        and not QbTorrents[tag]["uploaded"]
                        and state
                        not in ["checkingUP", "checkingDL", "checkingResumeData"]
                    ):
                        QbTorrents[tag]["uploaded"] = True
                        _onDownloadComplete(tor_info)
                    elif (
                        state in ["pausedUP", "pausedDL"] and QbTorrents[tag]["seeding"]
                    ):
                        QbTorrents[tag]["seeding"] = False
                        _onSeedFinish(tor_info)
                        await sleep(0.5)
            except Exception as e:
                LOGGER.error(str(e))
        await sleep(3)


async def onDownloadStart(tag):
    async with qb_listener_lock:
        QbTorrents[tag] = {
            "stalled_time": time(),
            "stop_dup_check": False,
            "rechecked": False,
            "uploaded": False,
            "seeding": False,
        }
        if not Intervals["qb"]:
            Intervals["qb"] = bot_loop.create_task(_qb_listener())
