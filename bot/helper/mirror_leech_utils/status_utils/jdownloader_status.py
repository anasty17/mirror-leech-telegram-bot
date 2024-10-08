from bot import LOGGER, jd_lock, jd_downloads
from ...ext_utils.bot_utils import retry_function, async_to_sync
from ...ext_utils.jdownloader_booter import jdownloader
from ...ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
)


def _get_combined_info(result):
    name = result[0].get("name")
    hosts = result[0].get("hosts")
    bytesLoaded = 0
    bytesTotal = 0
    speed = 0
    status = ""
    for res in result:
        st = res.get("status", "").lower()
        if st and st != "finished":
            status = st
        bytesLoaded += res.get("bytesLoaded", 0)
        bytesTotal += res.get("bytesTotal", 0)
        speed += res.get("speed", 0)
    if len(status) == 0:
        status = "UnknownError Check Web Interface"
    try:
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
                    "speed": True,
                    "eta": True,
                    "status": True,
                    "hosts": True,
                }
            ]
        )
        return _get_combined_info(result) if len(result) > 1 else result[0]
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
        state = self._info.get("status", "jdlimit")
        if len(state) == 0:
            return "UnknownError Check Web Interface"
        return MirrorStatus.STATUS_QUEUEDL if state == "jdlimit" else state

    def task(self):
        return self

    def gid(self):
        return self._gid

    async def cancel_task(self):
        self.listener.is_cancelled = True
        LOGGER.info(f"Cancelling Download: {self.name()}")
        await retry_function(
            jdownloader.device.downloads.remove_links,
            package_ids=jd_downloads[self._gid]["ids"],
        )
        async with jd_lock:
            del jd_downloads[self._gid]
        await self.listener.on_download_error("Download cancelled by user!")
