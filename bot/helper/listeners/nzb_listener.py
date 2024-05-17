from asyncio import sleep, gather

from bot import (
    Intervals,
    get_sabnzb_client,
    nzb_jobs,
    nzb_listener_lock,
    task_dict_lock,
    LOGGER,
    bot_loop,
)
from bot.helper.ext_utils.bot_utils import new_task
from bot.helper.ext_utils.status_utils import getTaskByGid
from bot.helper.ext_utils.task_manager import stop_duplicate_check


async def _remove_job(client, nzo_id, mid):
    res1, _ = await gather(
        client.delete_history(nzo_id, delete_files=True), client.delete_category(f"{mid}")
    )
    if not res1:
        await client.delete_job(nzo_id, True)
    async with nzb_listener_lock:
        if nzo_id in nzb_jobs:
            del nzb_jobs[nzo_id]
    await client.log_out()


@new_task
async def _onDownloadError(err, nzo_id, button=None):
    task = await getTaskByGid(nzo_id)
    LOGGER.info(f"Cancelling Download: {task.name()}")
    await gather(
        task.listener.onDownloadError(err, button),
        _remove_job(task.client, nzo_id, task.listener.mid),
    )


@new_task
async def _change_status(nzo_id, status):
    task = await getTaskByGid(nzo_id)
    async with task_dict_lock:
        task.cstatus = status


@new_task
async def _stop_duplicate(nzo_id):
    task = await getTaskByGid(nzo_id)
    task.listener.name = task.name()
    if not hasattr(task, "listener"):
        return
    msg, button = await stop_duplicate_check(task.listener)
    if msg:
        _onDownloadError(msg, nzo_id, button)


@new_task
async def _onDownloadComplete(nzo_id):
    task = await getTaskByGid(nzo_id)
    await task.listener.onDownloadComplete()
    if Intervals["stopAll"]:
        return
    await _remove_job(task.client, nzo_id, task.listener.mid)


async def _nzb_listener():
    client = get_sabnzb_client()
    while not Intervals["stopAll"]:
        async with nzb_listener_lock:
            try:
                jobs = (await client.get_history())["history"]["slots"]
                downloads = (await client.get_downloads())["queue"]["slots"]
                if len(nzb_jobs) == 0:
                    Intervals["nzb"] = ""
                    await client.log_out()
                    break
                for job in jobs:
                    nzo_id = job["nzo_id"]
                    if nzo_id not in nzb_jobs:
                        continue
                    if job["status"] == "Completed":
                        if not nzb_jobs[nzo_id]["uploaded"]:
                            nzb_jobs[nzo_id]["uploaded"] = True
                            _onDownloadComplete(nzo_id)
                            nzb_jobs[nzo_id]["status"] = "Completed"
                    elif job["status"] == "Failed":
                        _onDownloadError(job["fail_message"], nzo_id)
                    elif job["status"] in [
                        "QuickCheck",
                        "Verifying",
                        "Repairing",
                        "Fetching",
                        "Moving",
                        "Extracting",
                    ]:
                        if job["status"] != nzb_jobs[nzo_id]["status"]:
                            _change_status(nzo_id, job["status"])
                for dl in downloads:
                    nzo_id = dl["nzo_id"]
                    if nzo_id not in nzb_jobs:
                        continue
                    if (
                        dl["status"] == "Downloading"
                        and not nzb_jobs[nzo_id]["stop_dup_check"]
                        and not dl["filename"].startswith("Trying")
                    ):
                        nzb_jobs[nzo_id]["stop_dup_check"] = True
                        _stop_duplicate(nzo_id)
            except Exception as e:
                LOGGER.error(str(e))
        await sleep(3)


async def onDownloadStart(nzo_id):
    async with nzb_listener_lock:
        nzb_jobs[nzo_id] = {
            "uploaded": False,
            "stop_dup_check": False,
            "status": "Downloading",
        }
        if not Intervals["nzb"]:
            Intervals["nzb"] = bot_loop.create_task(_nzb_listener())
