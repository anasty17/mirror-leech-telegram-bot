from time import time

from .... import LOGGER, jd_listener_lock, jd_downloads
from ...ext_utils.bot_utils import async_to_sync
from ...ext_utils.jdownloader_booter import jdownloader
from ...ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
)


def _get_combined_info(result, old_info):
    name = result[0].get("name")
    hosts = result[0].get("hosts")
    bytesLoaded = 0
    bytesTotal = 0
    speed = 0
    status = ""
    for res in result:
        if res.get("enabled"):
            st = res.get("status", "")
            if st and st.lower() != "finished":
                status = st
            bytesLoaded += res.get("bytesLoaded", 0)
            bytesTotal += res.get("bytesTotal", 0)
            speed += res.get("speed", 0)
    try:
        if not speed:
            speed = (bytesLoaded - old_info.get("bytesLoaded", 0)) / (
                time() - old_info.get("last_update", 0)
            )
        eta = (bytesTotal - bytesLoaded) / speed
    except:
        eta = 0
    return {
        "name": name,
        "status": status,
        "speed": speed,
        "eta": eta,
        "hosts": hosts,
        "bytesLoaded": bytesLoaded,
        "bytesTotal": bytesTotal,
        "last_update": time(),
    }


async def get_download(gid, old_info):
    try:
        result = await jdownloader.device.downloads.query_packages(
            [
                {
                    "bytesLoaded": True,
                    "bytesTotal": True,
                    "enabled": True,
                    "packageUUIDs": jd_downloads[gid]["ids"],
                    "maxResults": -1,
                    "running": True,
                    "speed": True,
                    "eta": True,
                    "status": True,
                    "hosts": True,
                }
            ]
        )
        return _get_combined_info(result, old_info) if len(result) > 1 else result[0]
    except:
        return old_info


class JDownloaderStatus:
    def __init__(self, listener, gid):
        self.listener = listener
        self._gid = gid
        self._info = {}

    async def _update(self):
        self._info = await get_download(self._gid, self._info)

    def progress(self):
        try:
            return f"{round((self._info.get('bytesLoaded', 0) / self._info.get('bytesTotal', 0)) * 100, 2)}%"
        except:
            return "0%"

    def processed_bytes(self):
        return get_readable_file_size(self._info.get("bytesLoaded", 0))

    def speed(self):
        return f"{get_readable_file_size(self._info.get('speed', 0))}/s"

    def name(self):
        return self._info.get("name") or self.listener.name

    def size(self):
        return get_readable_file_size(self._info.get("bytesTotal", 0))

    def eta(self):
        return get_readable_time(eta) if (eta := self._info.get("eta", False)) else "-"

    def status(self):
        async_to_sync(self._update)
        state = self._info.get("status", "jdlimit").capitalize()
        if len(state) == 0:
            if self._info.get("bytesLoaded", 0) == 0:
                return MirrorStatus.STATUS_QUEUEDL
            else:
                return MirrorStatus.STATUS_DOWNLOAD
        return MirrorStatus.STATUS_QUEUEDL if state == "Jdlimit" else state

    def task(self):
        return self

    def gid(self):
        return self._gid

    async def cancel_task(self):
        self.listener.is_cancelled = True
        LOGGER.info(f"Cancelling Download: {self.name()}")
        await jdownloader.device.downloads.remove_links(
            package_ids=jd_downloads[self._gid]["ids"]
        )
        async with jd_listener_lock:
            del jd_downloads[self._gid]
        await self.listener.on_download_error("Cancelled by user!")
