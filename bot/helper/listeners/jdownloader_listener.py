from asyncio import sleep, wait_for

from bot import intervals, jd_lock, jd_downloads, LOGGER
from ..ext_utils.bot_utils import new_task, retry_function
from ..ext_utils.jdownloader_booter import jdownloader
from ..ext_utils.status_utils import get_task_by_gid


@new_task
async def update_download(gid, value):
    try:
        async with jd_lock:
            del value["ids"][0]
            new_gid = value["ids"][0]
            jd_downloads[new_gid] = value
        if task := await get_task_by_gid(f"{gid}"):
            task._gid = new_gid
        async with jd_lock:
            del jd_downloads[gid]
    except:
        pass


@new_task
async def remove_download(gid):
    if intervals["stopAll"]:
        return
    await retry_function(
        jdownloader.device.downloads.remove_links,
        package_ids=[gid],
    )
    if task := await get_task_by_gid(f"{gid}"):
        await task.listener.on_download_error("Download removed manually!")
        async with jd_lock:
            del jd_downloads[gid]


@new_task
async def _on_download_complete(gid):
    if task := await get_task_by_gid(f"{gid}"):
        if task.listener.select:
            async with jd_lock:
                await retry_function(
                    jdownloader.device.downloads.cleanup,
                    "DELETE_DISABLED",
                    "REMOVE_LINKS_AND_DELETE_FILES",
                    "SELECTED",
                    package_ids=jd_downloads[gid]["ids"],
                )
        await task.listener.on_download_complete()
        if intervals["stopAll"]:
            return
        async with jd_lock:
            if gid in jd_downloads:
                await retry_function(
                    jdownloader.device.downloads.remove_links,
                    package_ids=jd_downloads[gid]["ids"],
                )
                del jd_downloads[gid]


@new_task
async def _jd_listener():
    while True:
        await sleep(3)
        async with jd_lock:
            if len(jd_downloads) == 0:
                intervals["jd"] = ""
                break
            try:
                await wait_for(
                    retry_function(jdownloader.device.jd.version), timeout=10
                )
            except:
                is_connected = await jdownloader.jdconnect()
                if not is_connected:
                    LOGGER.error(jdownloader.error)
                    continue
                jdownloader.boot()
                isDeviceConnected = await jdownloader.connectToDevice()
                if not isDeviceConnected:
                    continue
            try:
                packages = await jdownloader.device.downloads.query_packages(
                    [{"finished": True}]
                )
            except:
                continue
            finished = [
                pack["uuid"] for pack in packages if pack.get("finished", False)
            ]
            all_packages = [pack["uuid"] for pack in packages]
            for k, v in list(jd_downloads.items()):
                if v["status"] == "down" and k not in all_packages:
                    cdi = jd_downloads[k]["ids"]
                    if len(cdi) > 1:
                        update_download(k, v)
                    else:
                        remove_download(k)
                else:
                    for index, pid in enumerate(v["ids"]):
                        if pid not in all_packages:
                            del jd_downloads[k]["ids"][index]

            for gid in finished:
                if gid in jd_downloads and jd_downloads[gid]["status"] == "down":
                    is_finished = all(
                        did in finished for did in jd_downloads[gid]["ids"]
                    )
                    if is_finished:
                        jd_downloads[gid]["status"] = "done"
                        _on_download_complete(gid)


async def on_download_start():
    async with jd_lock:
        if not intervals["jd"]:
            intervals["jd"] = await _jd_listener()
