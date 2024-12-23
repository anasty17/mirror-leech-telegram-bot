from aiofiles.os import remove, path as aiopath
from asyncio import sleep
from time import time

from ... import aria2, task_dict_lock, task_dict, LOGGER, intervals
from ...core.config_manager import Config
from ..ext_utils.bot_utils import loop_thread, bt_selection_buttons, sync_to_async
from ..ext_utils.files_utils import clean_unwanted
from ..ext_utils.status_utils import get_task_by_gid
from ..ext_utils.task_manager import stop_duplicate_check
from ..mirror_leech_utils.status_utils.aria2_status import Aria2Status
from ..telegram_helper.message_utils import (
    send_message,
    delete_message,
    update_status_message,
)


@loop_thread
async def _on_download_started(api, gid):
    download = await sync_to_async(api.get_download, gid)
    if download.options.follow_torrent == "false":
        return
    if download.is_metadata:
        LOGGER.info(f"onDownloadStarted: {gid} METADATA")
        await sleep(1)
        if task := await get_task_by_gid(gid):
            task.listener.is_torrent = True
            if task.listener.select:
                metamsg = "Downloading Metadata, wait then you can select files. Use torrent file to avoid this wait."
                meta = await send_message(task.listener.message, metamsg)
                while True:
                    await sleep(0.5)
                    if download.is_removed or download.followed_by_ids:
                        await delete_message(meta)
                        break
                    await sync_to_async(download.update)
        return
    else:
        LOGGER.info(f"onDownloadStarted: {download.name} - Gid: {gid}")
        await sleep(1)

    await sleep(2)
    if task := await get_task_by_gid(gid):
        download = await sync_to_async(api.get_download, gid)
        await sync_to_async(download.update)
        task.listener.name = download.name
        msg, button = await stop_duplicate_check(task.listener)
        if msg:
            await task.listener.on_download_error(msg, button)
            await sync_to_async(api.remove, [download], force=True, files=True)
            return


@loop_thread
async def _on_download_complete(api, gid):
    try:
        download = await sync_to_async(api.get_download, gid)
    except:
        return
    if download.options.follow_torrent == "false":
        return
    if download.followed_by_ids:
        new_gid = download.followed_by_ids[0]
        LOGGER.info(f"Gid changed from {gid} to {new_gid}")
        if task := await get_task_by_gid(new_gid):
            task.listener.is_torrent = True
            if Config.BASE_URL and task.listener.select:
                if not task.queued:
                    await sync_to_async(api.client.force_pause, new_gid)
                SBUTTONS = bt_selection_buttons(new_gid)
                msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
                await send_message(task.listener.message, msg, SBUTTONS)
    elif download.is_torrent:
        if task := await get_task_by_gid(gid):
            task.listener.is_torrent = True
            if hasattr(task, "seeding") and task.seeding:
                LOGGER.info(f"Cancelling Seed: {download.name} onDownloadComplete")
                await task.listener.on_upload_error(
                    f"Seeding stopped with Ratio: {task.ratio()} and Time: {task.seeding_time()}"
                )
                await sync_to_async(api.remove, [download], force=True, files=True)
    else:
        LOGGER.info(f"onDownloadComplete: {download.name} - Gid: {gid}")
        if task := await get_task_by_gid(gid):
            await task.listener.on_download_complete()
            if intervals["stopAll"]:
                return
            await sync_to_async(api.remove, [download], force=True, files=True)


@loop_thread
async def _on_bt_download_complete(api, gid):
    seed_start_time = time()
    await sleep(1)
    download = await sync_to_async(api.get_download, gid)
    LOGGER.info(f"onBtDownloadComplete: {download.name} - Gid: {gid}")
    if task := await get_task_by_gid(gid):
        task.listener.is_torrent = True
        if task.listener.select:
            res = download.files
            for file_o in res:
                f_path = file_o.path
                if not file_o.selected and await aiopath.exists(f_path):
                    try:
                        await remove(f_path)
                    except:
                        pass
            await clean_unwanted(download.dir)
        if task.listener.seed:
            try:
                await sync_to_async(
                    api.set_options, {"max-upload-limit": "0"}, [download]
                )
            except Exception as e:
                LOGGER.error(
                    f"{e} You are not able to seed because you added global option seed-time=0 without adding specific seed_time for this torrent GID: {gid}"
                )
        else:
            try:
                await sync_to_async(api.client.force_pause, gid)
            except Exception as e:
                LOGGER.error(f"{e} GID: {gid}")
        await task.listener.on_download_complete()
        if intervals["stopAll"]:
            return
        await sync_to_async(download.update)
        if task.listener.seed and download.is_complete and await get_task_by_gid(gid):
            LOGGER.info(f"Cancelling Seed: {download.name}")
            await task.listener.on_upload_error(
                f"Seeding stopped with Ratio: {task.ratio()} and Time: {task.seeding_time()}"
            )
            await sync_to_async(api.remove, [download], force=True, files=True)
        elif (
            task.listener.seed
            and download.is_complete
            and not await get_task_by_gid(gid)
        ):
            pass
        elif task.listener.seed and not task.listener.is_cancelled:
            async with task_dict_lock:
                if task.listener.mid not in task_dict:
                    await sync_to_async(api.remove, [download], force=True, files=True)
                    return
                task_dict[task.listener.mid] = Aria2Status(task.listener, gid, True)
                task_dict[task.listener.mid].start_time = seed_start_time
            LOGGER.info(f"Seeding started: {download.name} - Gid: {gid}")
            await update_status_message(task.listener.message.chat.id)
        else:
            await sync_to_async(api.remove, [download], force=True, files=True)


@loop_thread
async def _on_download_stopped(_, gid):
    await sleep(4)
    if task := await get_task_by_gid(gid):
        await task.listener.on_download_error("Dead torrent!")


@loop_thread
async def _on_download_error(api, gid):
    await sleep(1)
    LOGGER.info(f"onDownloadError: {gid}")
    error = "None"
    try:
        download = await sync_to_async(api.get_download, gid)
        if download.options.follow_torrent == "false":
            return
        error = download.error_message
        LOGGER.info(f"Download Error: {error}")
    except:
        pass
    if task := await get_task_by_gid(gid):
        await task.listener.on_download_error(error)


def start_aria2_listener():
    aria2.listen_to_notifications(
        threaded=False,
        on_download_start=_on_download_started,
        on_download_error=_on_download_error,
        on_download_stop=_on_download_stopped,
        on_download_complete=_on_download_complete,
        on_bt_download_complete=_on_bt_download_complete,
        timeout=60,
    )
