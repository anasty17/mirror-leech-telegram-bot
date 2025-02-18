from aiofiles.os import remove, path as aiopath
from asyncio import gather, sleep
from sabnzbdapi.exception import NotLoggedIn, LoginFailed

from .... import (
    task_dict,
    task_dict_lock,
    sabnzbd_client,
    LOGGER,
)
from ....core.config_manager import Config
from ...ext_utils.task_manager import check_running_tasks
from ...listeners.nzb_listener import on_download_start
from ...ext_utils.db_handler import database
from ...ext_utils.bot_utils import bt_selection_buttons
from ...mirror_leech_utils.status_utils.nzb_status import SabnzbdStatus
from ...telegram_helper.message_utils import (
    send_status_message,
    send_message,
    delete_message,
)


async def add_servers():
    res = await sabnzbd_client.check_login()
    if res and (servers := res["servers"]):
        sabnzbd_client.LOGGED_IN = True
        tasks = []
        servers_hosts = [x["host"] for x in servers]
        for server in list(Config.USENET_SERVERS):
            if server["host"] not in servers_hosts:
                tasks.append(sabnzbd_client.add_server(server))
                Config.USENET_SERVERS.append(server)
        if Config.DATABASE_URL:
            tasks.append(
                database.update_config({"USENET_SERVERS": Config.USENET_SERVERS})
            )
        if tasks:
            try:
                await gather(*tasks)
            except LoginFailed as e:
                raise e
    elif not res and (
        Config.USENET_SERVERS
        and (
            not Config.USENET_SERVERS[0]["host"]
            or not Config.USENET_SERVERS[0]["username"]
            or not Config.USENET_SERVERS[0]["password"]
        )
        or not Config.USENET_SERVERS
    ):
        sabnzbd_client.LOGGED_IN = False
        raise NotLoggedIn("Set USENET_SERVERS in bsetting or config!")
    else:
        if tasks := [
            sabnzbd_client.add_server(server) for server in Config.USENET_SERVERS
        ]:
            try:
                await gather(*tasks)
                sabnzbd_client.LOGGED_IN = True
            except LoginFailed as e:
                if len(tasks) == 1:
                    sabnzbd_client.LOGGED_IN = False
                raise e


async def add_nzb(listener, path):
    if not sabnzbd_client.LOGGED_IN:
        try:
            await add_servers()
        except Exception as e:
            await listener.on_download_error(str(e))
            return
    try:
        await sabnzbd_client.create_category(f"{listener.mid}", path)
        url = listener.link
        nzbpath = None
        if await aiopath.exists(listener.link):
            url = None
            nzbpath = listener.link
        add_to_queue, event = await check_running_tasks(listener)
        res = await sabnzbd_client.add_uri(
            url,
            nzbpath,
            listener.name,
            listener.extract if isinstance(listener.extract, str) else "",
            f"{listener.mid}",
            priority=-2 if add_to_queue else 0,
            pp=3 if listener.extract else 1,
        )
        if not res["status"]:
            await listener.on_download_error(
                "Not added! Mostly issue in the link",
            )
            return

        job_id = res["nzo_ids"][0]

        await sleep(0.5)

        downloads = await sabnzbd_client.get_downloads(nzo_ids=job_id)
        if not downloads["queue"]["slots"]:
            await sleep(1)
            history = await sabnzbd_client.get_history(nzo_ids=job_id)
            if err := history["history"]["slots"][0]["fail_message"]:
                await gather(
                    listener.on_download_error(err),
                    sabnzbd_client.delete_history(job_id, delete_files=True),
                )
                return
            name = history["history"]["slots"][0]["name"]
        else:
            name = downloads["queue"]["slots"][0]["filename"]

        async with task_dict_lock:
            task_dict[listener.mid] = SabnzbdStatus(
                listener, job_id, queued=add_to_queue
            )
        await on_download_start(job_id)

        if add_to_queue:
            LOGGER.info(f"Added to Queue/Download: {name} - Job_id: {job_id}")
        else:
            LOGGER.info(f"NzbDownload started: {name} - Job_id: {job_id}")

        await listener.on_download_start()

        if Config.BASE_URL and listener.select:
            if url and name.startswith("Trying"):
                metamsg = "Fetching URL, wait then you can select files. Use nzb file to avoid this wait."
                meta = await send_message(listener.message, metamsg)
                while True:
                    nzb_info = await sabnzbd_client.get_downloads(nzo_ids=job_id)
                    if nzb_info["queue"]["slots"]:
                        if not nzb_info["queue"]["slots"][0]["filename"].startswith(
                            "Trying"
                        ):
                            await delete_message(meta)
                            break
                    else:
                        await delete_message(meta)
                        return
                    await sleep(1)
            if not add_to_queue:
                await sabnzbd_client.pause_job(job_id)
            SBUTTONS = bt_selection_buttons(job_id)
            msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
            await send_message(listener.message, msg, SBUTTONS)
        elif listener.multi <= 1:
            await send_status_message(listener.message)

        if add_to_queue:
            await event.wait()
            if listener.is_cancelled:
                return
            async with task_dict_lock:
                task_dict[listener.mid].queued = False

            await sabnzbd_client.resume_job(job_id)
            LOGGER.info(
                f"Start Queued Download from Sabnzbd: {name} - Job_id: {job_id}"
            )
    except Exception as e:
        await listener.on_download_error(f"{e}")
    finally:
        if nzbpath and await aiopath.exists(listener.link):
            await remove(listener.link)
