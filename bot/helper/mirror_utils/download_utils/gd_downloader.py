#!/usr/bin/env python3
from random import SystemRandom
from string import ascii_letters, digits
from asyncio import Event

from bot import download_dict, download_dict_lock, LOGGER, config_dict, non_queued_dl, non_queued_up, queued_dl, queue_dict_lock
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.mirror_utils.status_utils.gd_download_status import GdDownloadStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.fs_utils import get_base_name
from bot.helper.ext_utils.bot_utils import sync_to_async


async def add_gd_download(link, path, listener, newname):
    drive = GoogleDriveHelper()
    res, size, name, _ = await sync_to_async(drive.helper, link)
    if res != "":
        await sendMessage(listener.message, res)
        return
    if newname:
        name = newname
    if config_dict['STOP_DUPLICATE'] and not listener.isLeech and listener.upPath == 'gd':
        LOGGER.info('Checking File/Folder if already in Drive...')
        if listener.isZip:
            gname = f"{name}.zip"
        elif listener.extract:
            try:
                gname = get_base_name(name)
            except:
                gname = None
        if gname is not None:
            gmsg, button = await sync_to_async(drive.drive_list, gname, True)
            if gmsg:
                msg = "File/Folder is already available in Drive.\nHere are the search results:"
                await sendMessage(listener.message, msg, button)
                return
    gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
    all_limit = config_dict['QUEUE_ALL']
    dl_limit = config_dict['QUEUE_DOWNLOAD']
    from_queue = False
    if all_limit or dl_limit:
        added_to_queue = False
        async with queue_dict_lock:
            dl = len(non_queued_dl)
            up = len(non_queued_up)
            if (all_limit and dl + up >= all_limit and (not dl_limit or dl >= dl_limit)) or (dl_limit and dl >= dl_limit):
                added_to_queue = True
                event = Event()
                queued_dl[listener.uid] = event
        if added_to_queue:
            LOGGER.info(f"Added to Queue/Download: {name}")
            async with download_dict_lock:
                download_dict[listener.uid] = QueueStatus(name, size, gid, listener, 'Dl')
            await listener.onDownloadStart()
            await sendStatusMessage(listener.message)
            await event.wait()
            async with download_dict_lock:
                if listener.uid not in download_dict:
                    return
            from_queue = True
    drive = GoogleDriveHelper(name, path, size, listener)
    async with download_dict_lock:
        download_dict[listener.uid] = GdDownloadStatus(drive, size, listener.message, gid)
    async with queue_dict_lock:
        non_queued_dl.add(listener.uid)
    if not from_queue:
        LOGGER.info(f"Download from GDrive: {name}")
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)
    else:
        LOGGER.info(f'Start Queued Download from GDrive: {name}')
    await sync_to_async(drive.download, link)
