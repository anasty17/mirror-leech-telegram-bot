from asyncio import gather

from .... import LOGGER, sabnzbd_client, nzb_jobs, nzb_listener_lock
from ...ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
    time_to_seconds,
)


async def get_download(nzo_id, old_info=None):
    try:
        queue = await sabnzbd_client.get_downloads(nzo_ids=nzo_id)
        if res := queue["queue"]["slots"]:
            slot = res[0]
            if msg := slot["labels"]:
                LOGGER.warning(" | ".join(msg))
            return slot
        else:
            history = await sabnzbd_client.get_history(nzo_ids=nzo_id)
            if res := history["history"]["slots"]:
                slot = res[0]
                if slot["status"] == "Verifying":
                    percentage = slot["action_line"].split("Verifying: ")[-1].split("/")
                    percentage = round(
                        (int(percentage[0]) / int(percentage[1])) * 100, 2
                    )
                    old_info["percentage"] = percentage
                elif slot["status"] == "Repairing":
                    action = slot["action_line"].split("Repairing: ")[-1].split()
                    percentage = action[0].strip("%")
                    eta = action[2]
                    old_info["percentage"] = percentage
                    old_info["timeleft"] = eta
                elif slot["status"] == "Extracting":
                    action = slot["action_line"].split("Unpacking: ")[-1].split()
                    percentage = action[0].split("/")
                    percentage = round(
                        (int(percentage[0]) / int(percentage[1])) * 100, 2
                    )
                    eta = action[2]
                    old_info["percentage"] = percentage
                    old_info["timeleft"] = eta
                old_info["status"] = slot["status"]
        return old_info
    except Exception as e:
        LOGGER.error(f"{e}: Sabnzbd, while getting job info. ID: {nzo_id}")
        return old_info


class SabnzbdStatus:
    def __init__(self, listener, gid, queued=False):
        self.queued = queued
        self.listener = listener
        self._gid = gid
        self._info = None
        self.tool = "sabnzbd"

    async def update(self):
        self._info = await get_download(self._gid, self._info)

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
        return int(time_to_seconds(self._info["timeleft"]))

    def eta(self):
        return get_readable_time(self.eta_raw())

    async def status(self):
        await self.update()
        state = self._info["status"]
        if state == "Paused" and self.queued:
            return MirrorStatus.STATUS_QUEUEDL
        elif state in [
            "QuickCheck",
            "Verifying",
            "Repairing",
            "Fetching",
            "Moving",
            "Extracting",
        ]:
            return state
        else:
            return MirrorStatus.STATUS_DOWNLOAD

    def task(self):
        return self

    def gid(self):
        return self._gid

    async def cancel_task(self):
        self.listener.is_cancelled = True
        await self.update()
        LOGGER.info(f"Cancelling Download: {self.name()}")
        await gather(
            self.listener.on_download_error("Stopped by user!"),
            sabnzbd_client.delete_job(self._gid, delete_files=True),
            sabnzbd_client.delete_category(f"{self.listener.mid}"),
            sabnzbd_client.delete_history(self._gid, delete_files=True),
        )
        async with nzb_listener_lock:
            if self._gid in nzb_jobs:
                del nzb_jobs[self._gid]
