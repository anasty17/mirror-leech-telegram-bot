from asyncio import gather

from bot import LOGGER, get_sabnzb_client, nzb_jobs, nzb_listener_lock
from bot.helper.ext_utils.bot_utils import async_to_sync
from bot.helper.ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
    time_to_seconds,
)


async def get_download(client, nzo_id, old_info=None):
    try:
        res = await client.get_downloads(nzo_ids=nzo_id)
        if res["queue"]["slots"]:
            slot = res["queue"]["slots"][0]
            if msg := slot["labels"]:
                LOGGER.warning(" | ".join(msg))
            return slot
        return old_info
    except Exception as e:
        LOGGER.error(f"{e}: Sabnzbd, while getting job info. ID: {nzo_id}")
        return old_info


class SabnzbdStatus:
    def __init__(self, listener, gid, queued=False, status=None):
        self.client = get_sabnzb_client()
        self.queued = queued
        self.listener = listener
        self.cstatus = status
        self._gid = gid
        self._info = None

    async def update(self):
        self._info = await get_download(self.client, self._gid, self._info)

    def progress(self):
        return f"{self._info['percentage']}%"

    def processed_raw(self):
        return (float(self._info["mb"]) - float(self._info["mbleft"])) * 1048576

    def processed_bytes(self):
        return get_readable_file_size(self.processed_raw())

    def speed_raw(self):
        try:
            return int(float(self._info["mb"]) * 1048576) / self.eta_raw()
        except:
            return 0

    def speed(self):
        return f"{get_readable_file_size(self.speed_raw())}/s"

    def name(self):
        return self._info["filename"]

    def size(self):
        return self._info["size"]

    def eta_raw(self):
        return time_to_seconds(self._info["timeleft"])

    def eta(self):
        return get_readable_time(self.eta_raw())

    def status(self):
        async_to_sync(self.update)
        state = self._info["status"]
        if state == "Paused" and self.queued:
            return MirrorStatus.STATUS_QUEUEDL
        elif self.cstatus:
            return self.cstatus
        elif state == "Paused":
            return MirrorStatus.STATUS_PAUSED
        else:
            return MirrorStatus.STATUS_DOWNLOADING

    def task(self):
        return self

    def gid(self):
        return self._gid

    async def cancel_task(self):
        self.listener.isCancelled = True
        await self.update()
        LOGGER.info(f"Cancelling Download: {self.name()}")
        await gather(
            self.listener.onDownloadError("Download stopped by user!"),
            self.client.delete_job(self._gid, delete_files=True),
            self.client.delete_category(f"{self.listener.mid}"),
        )
        await self.client.log_out()
        async with nzb_listener_lock:
            if self._gid in nzb_jobs:
                del nzb_jobs[self._gid]
