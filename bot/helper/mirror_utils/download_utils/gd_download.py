#!/usr/bin/env python3
from random import SystemRandom
from string import ascii_letters, digits

from bot import download_dict, download_dict_lock, LOGGER, non_queued_dl, queue_dict_lock
from bot.helper.mirror_utils.gdrive_utlis.download import gdDownload
from bot.helper.mirror_utils.gdrive_utlis.count import gdCount
from bot.helper.mirror_utils.status_utils.gdrive_status import GdriveStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.task_manager import is_queued, stop_duplicate_check


async def add_gd_download(link, path, listener, newname):
    drive = gdCount()
    name, mime_type, size, _, _ = await sync_to_async(drive.count, link, listener.user_id)
    if mime_type is None:
        await sendMessage(listener.message, name)
        return

    name = newname or name
    gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))

    msg, button = await stop_duplicate_check(name, listener)
    if msg:
        await sendMessage(listener.message, msg, button)
        return

    added_to_queue, event = await is_queued(listener.uid)
    if added_to_queue:
        LOGGER.info(f"Added to Queue/Download: {name}")
        async with download_dict_lock:
            download_dict[listener.uid] = QueueStatus(
                name, size, gid, listener, 'dl')
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)
        await event.wait()
        async with download_dict_lock:
            if listener.uid not in download_dict:
                return
        from_queue = True
    else:
        from_queue = False

    drive = gdDownload(name, path, listener)
    async with download_dict_lock:
        download_dict[listener.uid] = GdriveStatus(
            drive, size, listener.message, gid, 'dl')

    async with queue_dict_lock:
        non_queued_dl.add(listener.uid)

    if from_queue:
        LOGGER.info(f'Start Queued Download from GDrive: {name}')
    else:
        LOGGER.info(f"Download from GDrive: {name}")
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)

    await sync_to_async(drive.download, link)
