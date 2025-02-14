from time import time

from .... import LOGGER
from ....core.torrent_manager import TorrentManager, aria2_name
from ...ext_utils.status_utils import (
    MirrorStatus,
    get_readable_time,
    get_readable_file_size,
)


async def get_download(gid, old_info=None):
    try:
        res = await TorrentManager.aria2.tellStatus(gid)
        return res or old_info
    except Exception as e:
        LOGGER.error(f"{e}: Aria2c, Error while getting torrent info")
        return old_info


class Aria2Status:
    def __init__(self, listener, gid, seeding=False, queued=False):
        self._gid = gid
        self._download = {}
        self.listener = listener
        self.queued = queued
        self.start_time = 0
        self.seeding = seeding
        self.tool = "aria2"

    async def update(self):
        self._download = await get_download(self._gid, self._download)
        if self._download.get("followedBy", []):
            self._gid = self._download["followedBy"][0]
            self._download = await get_download(self._gid)

    def progress(self):
        try:
            return f"{round(int(self._download.get("completedLength", "0")) / int(self._download.get("totalLength", "0")) * 100, 2)}%"
        except:
            return "0%"

    def processed_bytes(self):
        return get_readable_file_size(int(self._download.get("completedLength", "0")))

    def speed(self):
        return (
            f"{get_readable_file_size(int(self._download.get("downloadSpeed", "0")))}/s"
        )

    def name(self):
        return aria2_name(self._download)

    def size(self):
        return get_readable_file_size(int(self._download.get("totalLength", "0")))

    def eta(self):
        try:
            return get_readable_time(
                (
                    int(self._download.get("totalLength", "0"))
                    - int(self._download.get("completedLength", "0"))
                )
                / int(self._download.get("downloadSpeed", "0"))
            )
        except:
            return "-"

    async def status(self):
        await self.update()
        if self._download.get("status", "") == "waiting" or self.queued:
            if self.seeding:
                return MirrorStatus.STATUS_QUEUEUP
            else:
                return MirrorStatus.STATUS_QUEUEDL
        elif self._download.get("status", "") == "paused":
            return MirrorStatus.STATUS_PAUSED
        elif self._download.get("seeder", "") == "true" and self.seeding:
            return MirrorStatus.STATUS_SEED
        else:
            return MirrorStatus.STATUS_DOWNLOAD

    def seeders_num(self):
        return self._download.get("numSeeders", 0)

    def leechers_num(self):
        return self._download.get("connections", 0)

    def uploaded_bytes(self):
        return get_readable_file_size(int(self._download.get("uploadLength", "0")))

    def seed_speed(self):
        return (
            f"{get_readable_file_size(int(self._download.get("uploadSpeed", "0")))}/s"
        )

    def ratio(self):
        try:
            return round(
                int(self._download.get("uploadLength", "0"))
                / int(self._download.get("completedLength", "0")),
                3,
            )
        except:
            return 0

    def seeding_time(self):
        return get_readable_time(time() - self.start_time)

    def task(self):
        return self

    def gid(self):
        return self._gid

    async def cancel_task(self):
        self.listener.is_cancelled = True
        await self.update()
        await TorrentManager.aria2_remove(self._download)
        if self._download.get("seeder", "") == "true" and self.seeding:
            LOGGER.info(f"Cancelling Seed: {self.name()}")
            await self.listener.on_upload_error(
                f"Seeding stopped with Ratio: {self.ratio()} and Time: {self.seeding_time()}"
            )
        else:
            if self.queued:
                LOGGER.info(f"Cancelling QueueDl: {self.name()}")
                msg = "task have been removed from queue/download"
            else:
                LOGGER.info(f"Cancelling Download: {self.name()}")
                msg = "Stopped by user!"
            await self.listener.on_download_error(msg)
