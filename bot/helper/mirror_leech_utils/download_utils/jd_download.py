from asyncio import wait_for, Event, wrap_future, sleep
from functools import partial
from pyrogram.filters import regex, user
from pyrogram.handlers import CallbackQueryHandler
from time import time
from aiofiles.os import path as aiopath
from aiofiles import open as aiopen
from base64 import b64encode

from bot import (
    task_dict,
    task_dict_lock,
    LOGGER,
    non_queued_dl,
    queue_dict_lock,
    jd_lock,
    jd_downloads,
)
from bot.helper.ext_utils.bot_utils import new_thread, retry_function, new_task
from bot.helper.ext_utils.jdownloader_booter import jdownloader
from bot.helper.ext_utils.task_manager import (
    check_running_tasks,
    stop_duplicate_check,
)
from bot.helper.listeners.jdownloader_listener import onDownloadStart
from bot.helper.mirror_leech_utils.status_utils.jdownloader_status import (
    JDownloaderStatus,
)
from bot.helper.mirror_leech_utils.status_utils.queue_status import QueueStatus
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    sendStatusMessage,
    editMessage,
    deleteMessage,
)


@new_task
async def configureDownload(_, query, obj):
    data = query.data.split()
    message = query.message
    await query.answer()
    if data[1] == "sdone":
        obj.event.set()
    elif data[1] == "cancel":
        await editMessage(message, "Task has been cancelled.")
        obj.listener.isCancelled = True
        obj.event.set()


class JDownloaderHelper:
    def __init__(self, listener):
        self._timeout = 300
        self._reply_to = ""
        self.listener = listener
        self.event = Event()

    @new_thread
    async def _event_handler(self):
        pfunc = partial(configureDownload, obj=self)
        handler = self.listener.client.add_handler(
            CallbackQueryHandler(
                pfunc, filters=regex("^jdq") & user(self.listener.userId)
            ),
            group=-1,
        )
        try:
            await wait_for(self.event.wait(), timeout=self._timeout)
        except:
            await editMessage(self._reply_to, "Timed Out. Task has been cancelled!")
            self.listener.isCancelled = True
            self.event.set()
        finally:
            self.listener.client.remove_handler(*handler)

    async def waitForConfigurations(self):
        future = self._event_handler()
        buttons = ButtonMaker()
        buttons.ubutton("Select", "https://my.jdownloader.org")
        buttons.ibutton("Done Selecting", "jdq sdone")
        buttons.ibutton("Cancel", "jdq cancel")
        button = buttons.build_menu(2)
        msg = f"Disable/Remove the unwanted files or change variants or edit files names from myJdownloader site for <b>{self.listener.name}</b> but don't start it manually!\n\nAfter finish press Done Selecting!\nTimeout: 300s"
        self._reply_to = await sendMessage(self.listener.message, msg, button)
        await wrap_future(future)
        if not self.listener.isCancelled:
            await deleteMessage(self._reply_to)
        return self.listener.isCancelled


async def add_jd_download(listener, path):
    async with jd_lock:
        if jdownloader.device is None:
            await listener.onDownloadError(jdownloader.error)
            return

        try:
            await wait_for(retry_function(jdownloader.device.jd.version), timeout=10)
        except:
            is_connected = await jdownloader.jdconnect()
            if not is_connected:
                await listener.onDownloadError(jdownloader.error)
                return
            jdownloader.boot()
            isDeviceConnected = await jdownloader.connectToDevice()
            if not isDeviceConnected:
                await listener.onDownloadError(jdownloader.error)
                return

        if not jd_downloads:
            await retry_function(jdownloader.device.linkgrabber.clear_list)
            if odl := await retry_function(
                jdownloader.device.downloads.query_packages, [{}]
            ):
                odl_list = [od["uuid"] for od in odl]
                await retry_function(
                    jdownloader.device.downloads.remove_links,
                    package_ids=odl_list,
                )
        elif odl := await retry_function(
            jdownloader.device.linkgrabber.query_packages, [{}]
        ):
            if odl_list := [
                od["uuid"]
                for od in odl
                if od.get("saveTo", "").startswith("/root/Downloads/")
            ]:
                await retry_function(
                    jdownloader.device.linkgrabber.remove_links,
                    package_ids=odl_list,
                )
        if await aiopath.exists(listener.link):
            async with aiopen(listener.link, "rb") as dlc:
                content = await dlc.read()
            content = b64encode(content)
            await retry_function(
                jdownloader.device.linkgrabber.add_container,
                "DLC",
                f";base64,{content.decode()}",
            )
        else:
            await retry_function(
                jdownloader.device.linkgrabber.add_links,
                [
                    {
                        "autoExtract": False,
                        "links": listener.link,
                        "packageName": listener.name or None,
                    }
                ],
            )

        await sleep(0.5)
        while await retry_function(jdownloader.device.linkgrabber.is_collecting):
            pass

        start_time = time()
        online_packages = []
        listener.size = 0
        corrupted_packages = []
        gid = 0
        remove_unknown = False
        name = ""
        error = ""
        while (time() - start_time) < 60:
            queued_downloads = await retry_function(
                jdownloader.device.linkgrabber.query_packages,
                [
                    {
                        "bytesTotal": True,
                        "saveTo": True,
                        "availableOnlineCount": True,
                        "availableTempUnknownCount": True,
                        "availableUnknownCount": True,
                    }
                ],
            )

            if not online_packages and corrupted_packages and error:
                await listener.onDownloadError(error)
                await retry_function(
                    jdownloader.device.linkgrabber.remove_links,
                    package_ids=corrupted_packages,
                )
                return

            for pack in queued_downloads:
                online = pack.get("onlineCount", 1)
                if online == 0:
                    error = f"{pack.get('name', '')}"
                    LOGGER.error(error)
                    corrupted_packages.append(pack["uuid"])
                    continue
                save_to = pack["saveTo"]
                if gid == 0:
                    gid = pack["uuid"]
                    jd_downloads[gid] = {"status": "collect"}
                    if save_to.startswith("/root/Downloads/"):
                        name = save_to.replace("/root/Downloads/", "", 1).split("/", 1)[
                            0
                        ]
                    else:
                        name = save_to.replace(f"{path}/", "", 1).split("/", 1)[0]

                if (
                    pack.get("tempUnknownCount", 0) > 0
                    or pack.get("unknownCount", 0) > 0
                ):
                    remove_unknown = True

                listener.size += pack.get("bytesTotal", 0)
                online_packages.append(pack["uuid"])
                if save_to.startswith("/root/Downloads/"):
                    await retry_function(
                        jdownloader.device.linkgrabber.set_download_directory,
                        save_to.replace("/root/Downloads", path, 1),
                        [pack["uuid"]],
                    )

            if online_packages:
                if listener.join and len(online_packages) > 1:
                    listener.name = listener.sameDir["name"]
                    await retry_function(
                        jdownloader.device.linkgrabber.move_to_new_package,
                        listener.name,
                        f"{path}/{listener.name}",
                        package_ids=online_packages,
                    )
                    continue
                break
        else:
            error = (
                name or "Download Not Added! Maybe some issues in jdownloader or site!"
            )
            await listener.onDownloadError(error)
            if corrupted_packages or online_packages:
                packages_to_remove = corrupted_packages + online_packages
                await retry_function(
                    jdownloader.device.linkgrabber.remove_links,
                    package_ids=packages_to_remove,
                )
            async with jd_lock:
                del jd_downloads[gid]
            return

        jd_downloads[gid]["ids"] = online_packages

        corrupted_links = []
        if remove_unknown:
            links = await retry_function(
                jdownloader.device.linkgrabber.query_links,
                [{"packageUUIDs": online_packages, "availability": True}],
            )
            corrupted_links = [
                link["uuid"]
                for link in links
                if link["availability"].lower() != "online"
            ]
        if corrupted_packages or corrupted_links:
            await retry_function(
                jdownloader.device.linkgrabber.remove_links,
                corrupted_links,
                corrupted_packages,
            )

    listener.name = listener.name or name

    msg, button = await stop_duplicate_check(listener)
    if msg:
        await retry_function(
            jdownloader.device.linkgrabber.remove_links, package_ids=online_packages
        )
        await listener.onDownloadError(msg, button)
        async with jd_lock:
            del jd_downloads[gid]
        return

    if listener.select and await JDownloaderHelper(listener).waitForConfigurations():
        await retry_function(
            jdownloader.device.linkgrabber.remove_links,
            package_ids=online_packages,
        )
        listener.removeFromSameDir()
        return

    add_to_queue, event = await check_running_tasks(listener)
    if add_to_queue:
        LOGGER.info(f"Added to Queue/Download: {listener.name}")
        async with task_dict_lock:
            task_dict[listener.mid] = QueueStatus(listener, f"{gid}", "dl")
        await listener.onDownloadStart()
        if listener.multi <= 1:
            await sendStatusMessage(listener.message)
        await event.wait()
        if listener.isCancelled:
            return
        async with queue_dict_lock:
            non_queued_dl.add(listener.mid)

    await retry_function(
        jdownloader.device.linkgrabber.move_to_downloadlist,
        package_ids=online_packages,
    )

    await sleep(1)

    download_packages = await retry_function(
        jdownloader.device.downloads.query_packages,
        [{"saveTo": True}],
    )
    async with jd_lock:
        packages = []
        for pack in download_packages:
            if pack["saveTo"].startswith(path):
                if not packages:
                    del jd_downloads[gid]
                    gid = pack["uuid"]
                    jd_downloads[gid] = {"status": "down"}
                packages.append(pack["uuid"])
        if packages:
            jd_downloads[gid]["ids"] = packages

    if not packages:
        await listener.onDownloadError("This Download have been removed manually!")
        async with jd_lock:
            del jd_downloads[gid]
        return

    await retry_function(
        jdownloader.device.downloads.force_download,
        package_ids=packages,
    )

    async with task_dict_lock:
        task_dict[listener.mid] = JDownloaderStatus(listener, f"{gid}")

    await onDownloadStart()

    if add_to_queue:
        LOGGER.info(f"Start Queued Download from JDownloader: {listener.name}")
    else:
        LOGGER.info(f"Download with JDownloader: {listener.name}")
        await listener.onDownloadStart()
        if listener.multi <= 1:
            await sendStatusMessage(listener.message)
