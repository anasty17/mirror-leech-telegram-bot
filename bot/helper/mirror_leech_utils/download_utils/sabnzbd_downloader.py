from aiofiles.os import remove, path as aiopath
from asyncio import gather

from bot import (
    task_dict,
    task_dict_lock,
    get_sabnzb_client,
    LOGGER,
    config_dict,
    non_queued_dl,
    queue_dict_lock,
)
from bot.helper.ext_utils.bot_utils import bt_selection_buttons
from bot.helper.ext_utils.task_manager import check_running_tasks
from bot.helper.listeners.nzb_listener import onDownloadStart
from bot.helper.mirror_leech_utils.status_utils.nzb_status import SabnzbdStatus
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    sendStatusMessage,
)


async def add_nzb(listener, path):
    client = get_sabnzb_client()
    if not client.LOGGED_IN:
        res = await client.check_login()
        if not res and (
            not config_dict["USENET_HOST"]
            or not config_dict["USENET_PASSWORD"]
            or not config_dict["USENET_USERNAME"]
        ):
            await listener.onDownloadError(
                "Set USENET_HOST, USENET_USERNAME and USENET_PASSWORD in bsetting or config!"
            )
            return
        else:
            try:
                await client.login(
                    "main",
                    config_dict["USENET_HOST"],
                    config_dict["USENET_USERNAME"],
                    config_dict["USENET_PASSWORD"],
                )
            except Exception as e:
                await listener.onDownloadError(str(e))
                return
    try:
        await client.create_category(f"{listener.mid}", path)
        url = listener.link
        nzbpath = None
        if await aiopath.exists(listener.link):
            url = None
            nzbpath = listener.link
        add_to_queue, event = await check_running_tasks(listener)
        res = await client.add_uri(
            url,
            nzbpath,
            listener.name,
            listener.extract if isinstance(listener.extract, str) else "",
            f"{listener.mid}",
            priority=-2 if add_to_queue else 0,
            pp=3 if listener.extract else 1,
        )
        if not res["status"]:
            await listener.onDownloadError(
                "Not added! Mostly issue in the link",
            )
            return

        job_id = res["nzo_ids"][0]

        downloads = await client.get_downloads(nzo_ids=job_id)
        if not downloads["queue"]["slots"]:
            history = await client.get_history(nzo_ids=job_id)
            if history["history"]["slots"][0]["status"] == "Failed":
                err = (
                    history["slots"][0]["fail_message"]
                    or "Link not added, unknown error!"
                )
                await gather(
                    listener.onDownloadError(err),
                    client.delete_history(job_id, del_files=True),
                )
                return
            name = history["history"]["slots"][0]["name"]
        else:
            name = downloads["queue"]["slots"][0]["filename"]

        async with task_dict_lock:
            task_dict[listener.mid] = SabnzbdStatus(
                listener, job_id, queued=add_to_queue
            )
        await onDownloadStart(job_id)

        if add_to_queue:
            LOGGER.info(f"Added to Queue/Download: {name} - Job_id: {job_id}")
        else:
            LOGGER.info(f"NzbDownload started: {name} - Job_id: {job_id}")

        await listener.onDownloadStart()

        if config_dict["BASE_URL"] and listener.select:
            if not add_to_queue:
                await client.pause_job(job_id)
            SBUTTONS = bt_selection_buttons(job_id)
            msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
            await sendMessage(listener.message, msg, SBUTTONS)
        elif listener.multi <= 1:
            await sendStatusMessage(listener.message)

        if add_to_queue:
            await event.wait()
            if listener.isCancelled:
                return
            async with queue_dict_lock:
                non_queued_dl.add(listener.mid)
            async with task_dict_lock:
                task_dict[listener.mid].queued = False

            await client.resume_job(job_id)
            LOGGER.info(
                f"Start Queued Download from Sabnzbd: {name} - Job_id: {job_id}"
            )
    except Exception as e:
        await listener.onDownloadError(f"{e}")
    finally:
        if nzbpath and await aiopath.exists(listener.link):
            await remove(listener.link)
        await client.log_out()
