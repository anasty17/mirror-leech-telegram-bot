#!/usr/bin/env python3
from asyncio import Lock, sleep
from time import time

from bot import download_dict, download_dict_lock, get_client, LOGGER, QbInterval, config_dict, QbTorrents, qb_listener_lock
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.mirror_utils.status_utils.qbit_status import QbittorrentStatus
from bot.helper.telegram_helper.message_utils import update_all_messages
from bot.helper.ext_utils.bot_utils import get_readable_time, setInterval, getDownloadByGid, new_task, sync_to_async
from bot.helper.ext_utils.fs_utils import clean_unwanted, get_base_name


async def __remove_torrent(client, hash_, tag):
    await sync_to_async(client.torrents_delete, torrent_hashes=hash_, delete_files=True)
    async with qb_listener_lock:
        if tag in QbTorrents:
            del QbTorrents[tag]
    await sync_to_async(client.torrents_delete_tags, tags=tag)
    await sync_to_async(client.auth_log_out)

@new_task
async def __onDownloadError(err, tor, button=None):
    ext_hash = tor.hash
    client = await sync_to_async(get_client)
    LOGGER.info(f"Cancelling Download: {tor.name}")
    await sync_to_async(client.torrents_pause, torrent_hashes=ext_hash)
    await sleep(0.3)
    download = await getDownloadByGid(ext_hash[:12])
    if hasattr(download, 'listener'):
        listener = download.listener()
        await listener.onDownloadError(err, button)
    await __remove_torrent(client, ext_hash, tor.tags)

@new_task
async def __onSeedFinish(tor):
    ext_hash = tor.hash
    client = await sync_to_async(get_client)
    LOGGER.info(f"Cancelling Seed: {tor.name}")
    download = await getDownloadByGid(ext_hash[:12])
    if hasattr(download, 'listener'):
        listener = download.listener()
        await listener.onUploadError(f"Seeding stopped with Ratio: {round(tor.ratio, 3)} and Time: {get_readable_time(tor.seeding_time)}")
    await __remove_torrent(client, ext_hash, tor.tags)

@new_task
async def __stop_duplicate(tor):
    download = await getDownloadByGid(tor.hash[:12])
    if hasattr(download, 'listener'):
        listener = download.listener()
        if listener.select or listener.isLeech or listener.upPath != 'gd':
            return
        LOGGER.info('Checking File/Folder if already in Drive')
        qbname = tor.content_path.rsplit('/', 1)[-1].rsplit('.!qB', 1)[0]
        if listener.isZip:
            qbname = f"{qbname}.zip"
        elif listener.extract:
            try:
                qbname = get_base_name(qbname)
            except:
                qbname = None
        if qbname is not None:
                qbmsg, button = await sync_to_async(GoogleDriveHelper().drive_list, qbname, True)
                if qbmsg:
                    qbmsg = 'File/Folder is already available in Drive.\nHere are the search results:'
                    __onDownloadError(qbmsg, tor, button)

@new_task
async def __onDownloadComplete(tor):
    ext_hash = tor.hash
    tag = tor.tags
    client = await sync_to_async(get_client)
    await sleep(2)
    download = await getDownloadByGid(ext_hash[:12])
    try:
        listener = download.listener()
    except:
        return
    if not listener.seed:
        await sync_to_async(client.torrents_pause, torrent_hashes=ext_hash)
    if listener.select:
        await clean_unwanted(listener.dir)
    await listener.onDownloadComplete()
    if listener.seed:
        async with download_dict_lock:
            if listener.uid in download_dict:
                removed = False
                download_dict[listener.uid] = QbittorrentStatus(listener, True)
            else:
                removed = True
        if removed:
            await __remove_torrent(client, ext_hash, tag)
            return
        async with qb_listener_lock:
            if tag in QbTorrents:
                QbTorrents[tag]['seeding'] = True
            else:
                return
        await update_all_messages()
        LOGGER.info(f"Seeding started: {tor.name} - Hash: {ext_hash}")
        await sync_to_async(client.auth_log_out)
    else:
        await __remove_torrent(client, ext_hash, tag)

async def __qb_listener():
    client = await sync_to_async(get_client)
    async with qb_listener_lock:
        if len(await sync_to_async(client.torrents_info)) == 0:
            QbInterval[0].cancel()
            QbInterval.clear()
            await sync_to_async(client.auth_log_out)
            return
        try:
            for tor_info in await sync_to_async(client.torrents_info):
                tag = tor_info.tags
                if tag not in QbTorrents:
                    continue
                state = tor_info.state
                if state == "metaDL":
                    TORRENT_TIMEOUT = config_dict['TORRENT_TIMEOUT']
                    QbTorrents[tag]['stalled_time'] = time()
                    if TORRENT_TIMEOUT and time() - tor_info.added_on >= TORRENT_TIMEOUT:
                        __onDownloadError("Dead Torrent!", tor_info)
                    else:
                        await sync_to_async(client.torrents_reannounce, torrent_hashes=tor_info.hash)
                elif state == "downloading":
                    QbTorrents[tag]['stalled_time'] = time()
                    if config_dict['STOP_DUPLICATE'] and not QbTorrents[tag]['stop_dup_check']:
                        QbTorrents[tag]['stop_dup_check'] = True
                        __stop_duplicate(tor_info)
                elif state == "stalledDL":
                    TORRENT_TIMEOUT = config_dict['TORRENT_TIMEOUT']
                    if not QbTorrents[tag]['rechecked'] and 0.99989999999999999 < tor_info.progress < 1:
                        msg = f"Force recheck - Name: {tor_info.name} Hash: "
                        msg += f"{tor_info.hash} Downloaded Bytes: {tor_info.downloaded} "
                        msg += f"Size: {tor_info.size} Total Size: {tor_info.total_size}"
                        LOGGER.error(msg)
                        await sync_to_async(client.torrents_recheck, torrent_hashes=tor_info.hash)
                        QbTorrents[tag]['rechecked'] = True
                    elif TORRENT_TIMEOUT and time() - QbTorrents[tag]['stalled_time'] >= TORRENT_TIMEOUT:
                        __onDownloadError("Dead Torrent!", tor_info)
                    else:
                        await sync_to_async(client.torrents_reannounce, torrent_hashes=tor_info.hash)
                elif state == "missingFiles":
                    await sync_to_async(client.torrents_recheck, torrent_hashes=tor_info.hash)
                elif state == "error":
                    __onDownloadError("No enough space for this torrent on device", client, tor_info)
                elif tor_info.completion_on != 0 and not QbTorrents[tag]['uploaded'] and \
                        state not in ['checkingUP', 'checkingDL', 'checkingResumeData']:
                    QbTorrents[tag]['uploaded'] = True
                    __onDownloadComplete(tor_info)
                elif state in ['pausedUP', 'pausedDL'] and QbTorrents[tag]['seeding']:
                    QbTorrents[tag]['seeding'] = False
                    __onSeedFinish(tor_info)
        except Exception as e:
            LOGGER.error(str(e))
        finally:
            await sync_to_async(client.auth_log_out)

async def onDownloadStart(tag):
    async with qb_listener_lock:
        QbTorrents[tag] = {'stalled_time': time(), 'stop_dup_check': False, 'rechecked': False, 'uploaded': False, 'seeding': False}
        if not QbInterval:
            periodic = setInterval(5, __qb_listener)
            QbInterval.append(periodic)