from secrets import token_urlsafe

from bot import task_dict, task_dict_lock, LOGGER, non_queued_dl, queue_dict_lock
from bot.helper.mirror_utils.gdrive_utils.download import gdDownload
from bot.helper.mirror_utils.gdrive_utils.count import gdCount
from bot.helper.mirror_utils.status_utils.gdrive_status import GdriveStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.task_manager import is_queued, stop_duplicate_check


async def add_gd_download(listener, path):
    drive = gdCount()
    name, mime_type, size, _, _ = await sync_to_async(
        drive.count, listener.link, listener.user_id
    )
    if mime_type is None:
        await sendMessage(listener.message, name)
        return

    listener.name = listener.name or name
    gid = token_urlsafe(12)

    msg, button = await stop_duplicate_check(listener)
    if msg:
        await sendMessage(listener.message, msg, button)
        return

    add_to_queue, event = await is_queued(listener.mid)
    if add_to_queue:
        LOGGER.info(f"Added to Queue/Download: {listener.name}")
        async with task_dict_lock:
            task_dict[listener.mid] = QueueStatus(listener, size, gid, "dl")
        await listener.onDownloadStart()
        if listener.multi <= 1:
            await sendStatusMessage(listener.message)
        await event.wait()
        async with task_dict_lock:
            if listener.mid not in task_dict:
                return
        from_queue = True
    else:
        from_queue = False

    drive = gdDownload(listener, path)
    async with task_dict_lock:
        task_dict[listener.mid] = GdriveStatus(listener, drive, size, gid, "dl")

    async with queue_dict_lock:
        non_queued_dl.add(listener.mid)

    if from_queue:
        LOGGER.info(f"Start Queued Download from GDrive: {listener.name}")
    else:
        LOGGER.info(f"Download from GDrive: {listener.name}")
        await listener.onDownloadStart()
        if listener.multi <= 1:
            await sendStatusMessage(listener.message)

    await sync_to_async(drive.download)
