from asyncio import gather
from json import loads
from secrets import token_urlsafe
from aiofiles.os import remove

from .... import task_dict, task_dict_lock, LOGGER
from ...ext_utils.bot_utils import cmd_exec
from ...ext_utils.task_manager import check_running_tasks, stop_duplicate_check
from ...mirror_leech_utils.rclone_utils.transfer import RcloneTransferHelper
from ...mirror_leech_utils.status_utils.queue_status import QueueStatus
from ...mirror_leech_utils.status_utils.rclone_status import RcloneStatus
from ...telegram_helper.message_utils import send_status_message


async def add_rclone_download(listener, path):
    if listener.link.startswith("mrcc:"):
        listener.link = listener.link.split("mrcc:", 1)[1]
        config_path = f"rclone/{listener.user_id}.conf"
    else:
        config_path = "rclone.conf"

    remote, listener.link = listener.link.split(":", 1)
    listener.link = listener.link.strip("/")
    rclone_select = False
    if listener.link.startswith("rclone_select"):
        rclone_select = True
        rpath = ""
    else:
        rpath = listener.link

    cmd1 = [
        "rclone",
        "lsjson",
        "--fast-list",
        "--stat",
        "--no-mimetype",
        "--no-modtime",
        "--config",
        config_path,
        f"{remote}:{rpath}",
        "-v",
        "--log-systemd",
    ]
    cmd2 = [
        "rclone",
        "size",
        "--fast-list",
        "--json",
        "--config",
        config_path,
        f"{remote}:{rpath}",
        "-v",
        "--log-systemd",
    ]
    if rclone_select:
        cmd2.extend(("--files-from", listener.link))
        res = await cmd_exec(cmd2)
        if res[2] != 0:
            if res[2] != -9:
                msg = f"Error: While getting rclone stat/size. Path: {remote}:{listener.link}. Stderr: {res[1][:4000]}"
                await listener.on_download_error(msg)
            return
        try:
            rsize = loads(res[0])
        except Exception as err:
            await listener.on_download_error(f"RcloneDownload JsonLoad: {err}")
            return
        if not listener.name:
            listener.name = listener.link
        path += listener.name
    else:
        res1, res2 = await gather(cmd_exec(cmd1), cmd_exec(cmd2))
        if res1[2] != 0 or res2[2] != 0:
            if res1[2] != -9:
                err = res1[1] or res2[1]
                msg = f"Error: While getting rclone stat/size. Path: {remote}:{listener.link}. Stderr: {err[:4000]}"
                await listener.on_download_error(msg)
            return
        try:
            rstat = loads(res1[0])
            rsize = loads(res2[0])
        except Exception as err:
            await listener.on_download_error(f"RcloneDownload JsonLoad: {err}")
            return
        if rstat["IsDir"]:
            if not listener.name:
                listener.name = (
                    listener.link.rsplit("/", 1)[-1] if listener.link else remote
                )
            path += listener.name
        else:
            listener.name = listener.link.rsplit("/", 1)[-1]
    listener.size = rsize["bytes"]
    gid = token_urlsafe(12)

    if not rclone_select:
        msg, button = await stop_duplicate_check(listener)
        if msg:
            await listener.on_download_error(msg, button)
            return

    add_to_queue, event = await check_running_tasks(listener)
    if add_to_queue:
        LOGGER.info(f"Added to Queue/Download: {listener.name}")
        async with task_dict_lock:
            task_dict[listener.mid] = QueueStatus(listener, gid, "dl")
        await listener.on_download_start()
        if listener.multi <= 1:
            await send_status_message(listener.message)
        await event.wait()
        if listener.is_cancelled:
            return

    RCTransfer = RcloneTransferHelper(listener)
    async with task_dict_lock:
        task_dict[listener.mid] = RcloneStatus(listener, RCTransfer, gid, "dl")

    if add_to_queue:
        LOGGER.info(f"Start Queued Download with rclone: {listener.link}")
    else:
        await listener.on_download_start()
        if listener.multi <= 1:
            await send_status_message(listener.message)
        LOGGER.info(f"Download with rclone: {listener.link}")

    await RCTransfer.download(remote, config_path, path)
    if rclone_select:
        await remove(listener.link)
