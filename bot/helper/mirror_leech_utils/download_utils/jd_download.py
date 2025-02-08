from asyncio import wait_for, Event, sleep
from functools import partial
from pyrogram.filters import regex, user
from pyrogram.handlers import CallbackQueryHandler
from time import time
from aiofiles.os import path as aiopath, remove
from aiofiles import open as aiopen
from base64 import b64encode
from secrets import token_urlsafe
from myjd.exception import MYJDException

from .... import (
    task_dict,
    task_dict_lock,
    LOGGER,
    jd_listener_lock,
    jd_downloads,
)
from ...ext_utils.bot_utils import new_task
from ....core.jdownloader_booter import jdownloader
from ...ext_utils.task_manager import check_running_tasks, stop_duplicate_check
from ...listeners.jdownloader_listener import on_download_start
from ...mirror_leech_utils.status_utils.jdownloader_status import JDownloaderStatus
from ...mirror_leech_utils.status_utils.queue_status import QueueStatus
from ...telegram_helper.button_build import ButtonMaker
from ...telegram_helper.message_utils import (
    send_message,
    send_status_message,
    edit_message,
    delete_message,
)


@new_task
async def configureDownload(_, query, obj):
    data = query.data.split()
    message = query.message
    await query.answer()
    if data[1] == "sdone":
        obj.event.set()
    elif data[1] == "cancel":
        await edit_message(message, "Task has been cancelled.")
        obj.listener.is_cancelled = True
        obj.event.set()


class JDownloaderHelper:
    def __init__(self, listener):
        self._timeout = 600
        self._reply_to = ""
        self.listener = listener
        self.event = Event()

    async def _event_handler(self):
        pfunc = partial(configureDownload, obj=self)
        handler = self.listener.client.add_handler(
            CallbackQueryHandler(
                pfunc, filters=regex("^jdq") & user(self.listener.user_id)
            ),
            group=-1,
        )
        try:
            await wait_for(self.event.wait(), timeout=self._timeout)
        except:
            await edit_message(self._reply_to, "Timed Out. Task has been cancelled!")
            self.listener.is_cancelled = True
            self.event.set()
        finally:
            self.listener.client.remove_handler(*handler)

    async def wait_for_configurations(self):
        buttons = ButtonMaker()
        buttons.url_button("Select", "https://my.jdownloader.org")
        buttons.data_button("Done Selecting", "jdq sdone")
        buttons.data_button("Cancel", "jdq cancel")
        button = buttons.build_menu(2)
        msg = f"Remove the unwanted files or change variants or edit files names from myJdownloader site for <b>{self.listener.name}</b>.\nDon't start it manually!\n\nAfter finish press Done Selecting!\nTimeout: 10 min"
        self._reply_to = await send_message(self.listener.message, msg, button)
        await self._event_handler()
        if not self.listener.is_cancelled:
            await delete_message(self._reply_to)
        return not self.listener.is_cancelled


async def get_online_packages(path, state="grabbing"):
    if state == "grabbing":
        queued_downloads = await jdownloader.device.linkgrabber.query_packages(
            [{"saveTo": True}]
        )
        return [qd["uuid"] for qd in queued_downloads if qd["saveTo"].startswith(path)]
    else:
        download_packages = await jdownloader.device.downloads.query_packages(
            [{"saveTo": True}]
        )
        return [dl["uuid"] for dl in download_packages if dl["saveTo"].startswith(path)]


def trim_path(path):
    path_components = path.split("/")

    trimmed_components = [
        component[:255] if len(component) > 255 else component
        for component in path_components
    ]

    return "/".join(trimmed_components)


async def get_jd_download_directory():
    res = await jdownloader.device.config.get(
        "org.jdownloader.settings.GeneralSettings", None, "DefaultDownloadFolder"
    )
    return f'/{res.strip("/")}/'


async def add_jd_download(listener, path):
    try:
        async with jd_listener_lock:
            gid = token_urlsafe(12)
            if not jdownloader.is_connected:
                raise MYJDException(jdownloader.error)

            default_path = await get_jd_download_directory()
            if not jd_downloads:
                await jdownloader.device.linkgrabber.clear_list()
                if odl := await jdownloader.device.downloads.query_packages([{}]):
                    odl_list = [od["uuid"] for od in odl]
                    await jdownloader.device.downloads.remove_links(
                        package_ids=odl_list
                    )
            elif odl := await jdownloader.device.linkgrabber.query_packages([{}]):
                if odl_list := [
                    od["uuid"]
                    for od in odl
                    if od.get("saveTo", "").startswith(default_path)
                ]:
                    await jdownloader.device.linkgrabber.remove_links(
                        package_ids=odl_list
                    )

            jd_downloads[gid] = {"status": "collect", "path": path}

            if await aiopath.exists(listener.link):
                async with aiopen(listener.link, "rb") as dlc:
                    content = await dlc.read()
                content = b64encode(content)
                await jdownloader.device.linkgrabber.add_container(
                    "DLC", f";base64,{content.decode()}"
                )
            else:
                await jdownloader.device.linkgrabber.add_links(
                    [
                        {
                            "autoExtract": False,
                            "links": listener.link,
                            "packageName": listener.name or None,
                        }
                    ],
                )

            await sleep(1)
            while await jdownloader.device.linkgrabber.is_collecting():
                pass
            start_time = time()
            online_packages = []
            corrupted_packages = []
            remove_unknown = False
            name = ""
            error = ""
            while (time() - start_time) < 60:
                queued_downloads = await jdownloader.device.linkgrabber.query_packages(
                    [
                        {
                            "bytesTotal": True,
                            "saveTo": True,
                            "availableOnlineCount": True,
                            "availableOfflineCount": True,
                            "availableTempUnknownCount": True,
                            "availableUnknownCount": True,
                        }
                    ],
                )

                if not online_packages and corrupted_packages and error:
                    await jdownloader.device.linkgrabber.remove_links(
                        package_ids=corrupted_packages,
                    )
                    raise MYJDException(error)

                for pack in queued_downloads:
                    if pack.get("onlineCount", 1) == 0:
                        error = f"{pack.get('name', '')}"
                        LOGGER.error(error)
                        corrupted_packages.append(pack["uuid"])
                        continue
                    save_to = pack["saveTo"]
                    if not name:
                        if save_to.startswith(default_path):
                            name = save_to.replace(default_path, "", 1).split("/", 1)[0]
                        else:
                            name = save_to.replace(f"{path}/", "", 1).split("/", 1)[0]
                        name = name[:255]

                    if (
                        pack.get("tempUnknownCount", 0) > 0
                        or pack.get("unknownCount", 0) > 0
                        or pack.get("offlineCount", 0) > 0
                    ):
                        remove_unknown = True

                    listener.size += pack.get("bytesTotal", 0)
                    online_packages.append(pack["uuid"])
                    if save_to.startswith(default_path):
                        save_to = trim_path(save_to)
                        await jdownloader.device.linkgrabber.set_download_directory(
                            save_to.replace(default_path, f"{path}/", 1),
                            [pack["uuid"]],
                        )

                if online_packages:
                    if listener.join and len(online_packages) > 1:
                        listener.name = "Joined Packages"
                        await jdownloader.device.linkgrabber.move_to_new_package(
                            listener.name,
                            f"{path}/{listener.name}",
                            package_ids=online_packages,
                        )
                        continue
                    break
            else:
                error = (
                    name
                    or "Download Not Added! Maybe some issues in jdownloader or site!"
                )
                if corrupted_packages or online_packages:
                    packages_to_remove = corrupted_packages + online_packages
                    await jdownloader.device.linkgrabber.remove_links(
                        package_ids=packages_to_remove,
                    )
                raise MYJDException(error)

            jd_downloads[gid]["ids"] = online_packages

            corrupted_links = []
            if remove_unknown:
                links = await jdownloader.device.linkgrabber.query_links(
                    [{"packageUUIDs": online_packages, "availability": True}],
                )
                corrupted_links = [
                    link["uuid"]
                    for link in links
                    if link["availability"].lower() != "online"
                ]
            if corrupted_packages or corrupted_links:
                await jdownloader.device.linkgrabber.remove_links(
                    corrupted_links,
                    corrupted_packages,
                )

        listener.name = listener.name or name

        msg, button = await stop_duplicate_check(listener)
        if msg:
            await jdownloader.device.linkgrabber.remove_links(
                package_ids=online_packages
            )
            await listener.on_download_error(msg, button)
            async with jd_listener_lock:
                del jd_downloads[gid]
            return

        if listener.select:
            if not await JDownloaderHelper(listener).wait_for_configurations():
                await jdownloader.device.linkgrabber.remove_links(
                    package_ids=online_packages
                )
                await listener.remove_from_same_dir()
                async with jd_listener_lock:
                    del jd_downloads[gid]
                return
            else:
                online_packages = await get_online_packages(path)
                if not online_packages:
                    raise MYJDException(
                        "Select: This Download have been removed manually!"
                    )
                async with jd_listener_lock:
                    jd_downloads[gid]["ids"] = online_packages

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

            online_packages = await get_online_packages(path)
            if not online_packages:
                raise MYJDException("Queue: This Download have been removed manually!")
            async with jd_listener_lock:
                jd_downloads[gid]["ids"] = online_packages

        await jdownloader.device.linkgrabber.move_to_downloadlist(
            package_ids=online_packages
        )

        await sleep(0.5)

        online_packages = await get_online_packages(path, "down")
        if not online_packages:
            online_packages = await get_online_packages(path)
            if not online_packages:
                raise MYJDException(
                    "Linkgrabber: This Download have been removed manually!"
                )
            await jdownloader.device.linkgrabber.move_to_downloadlist(
                package_ids=online_packages
            )
            await sleep(0.5)
            online_packages = await get_online_packages(path, "down")
        if not online_packages:
            raise MYJDException(
                "Download List: This Download have been removed manually!"
            )

        async with jd_listener_lock:
            jd_downloads[gid]["status"] = "down"
            jd_downloads[gid]["ids"] = online_packages

        await jdownloader.device.downloads.force_download(package_ids=online_packages)

        async with task_dict_lock:
            task_dict[listener.mid] = JDownloaderStatus(listener, gid)

        await on_download_start()

        if add_to_queue:
            LOGGER.info(f"Start Queued Download from JDownloader: {listener.name}")
        else:
            LOGGER.info(f"Download with JDownloader: {listener.name}")
            await listener.on_download_start()
            if listener.multi <= 1:
                await send_status_message(listener.message)
    except (Exception, MYJDException) as e:
        await listener.on_download_error(f"{e}".strip())
        async with jd_listener_lock:
            if gid in jd_downloads:
                del jd_downloads[gid]
        return
    finally:
        if await aiopath.exists(listener.link):
            await remove(listener.link)

    await sleep(2)

    links = await jdownloader.device.downloads.query_links(
        [
            {
                "packageUUIDs": online_packages,
                "status": True,
            }
        ],
    )
    links_to_remove = []
    force_download = False
    for dlink in links:
        if dlink.get("status", "") == "Invalid download directory":
            force_download = True
            new_name, ext = dlink["name"].rsplit(".", 1)
            new_name = new_name[: 250 - len(f".{ext}".encode())]
            new_name = f"{new_name}.{ext}"
            await jdownloader.device.downloads.rename_link(dlink["uuid"], new_name)
        elif dlink.get("status", "") == "HLS stream broken?":
            links_to_remove.append(dlink["uuid"])

    if links_to_remove:
        await jdownloader.device.downloads.remove_links(links_to_remove)
    if force_download:
        await jdownloader.device.downloads.force_download(package_ids=online_packages)
