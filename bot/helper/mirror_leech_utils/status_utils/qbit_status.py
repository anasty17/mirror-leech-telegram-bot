from asyncio import sleep, gather

from .... import LOGGER, qb_torrents, qb_listener_lock
from ....core.torrent_manager import TorrentManager
from ...ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
)


async def get_download(tag, old_info=None):
    try:
        res = (await TorrentManager.qbittorrent.torrents.info(tag=tag))[0]
        return res or old_info
    except Exception as e:
        LOGGER.error(f"{e}: Qbittorrent, while getting torrent info. Tag: {tag}")
        return old_info


class QbittorrentStatus:
    def __init__(self, listener, seeding=False, queued=False):
        self.queued = queued
        self.seeding = seeding
        self.listener = listener
        self._info = None
        self.tool = "qbittorrent"

    async def update(self):
        self._info = await get_download(f"{self.listener.mid}", self._info)

    def progress(self):
        return f"{round(self._info.progress * 100, 2)}%"

    def processed_bytes(self):
        return get_readable_file_size(self._info.downloaded)

    def speed(self):
        return f"{get_readable_file_size(self._info.dlspeed)}/s"

    def name(self):
        if self._info.state in ["metaDL", "checkingResumeData"]:
            return f"[METADATA]{self.listener.name}"
        else:
            return self.listener.name

    def size(self):
        return get_readable_file_size(self._info.size)

    def eta(self):
        return get_readable_time(self._info.eta.total_seconds())

    async def status(self):
        await self.update()
        state = self._info.state
        if state == "queuedDL" or self.queued:
            return MirrorStatus.STATUS_QUEUEDL
        elif state == "queuedUP":
            return MirrorStatus.STATUS_QUEUEUP
        elif state in ["stoppedDL", "stoppedUP"]:
            return MirrorStatus.STATUS_PAUSED
        elif state in ["checkingUP", "checkingDL"]:
            return MirrorStatus.STATUS_CHECK
        elif state in ["stalledUP", "uploading"] and self.seeding:
            return MirrorStatus.STATUS_SEED
        else:
            return MirrorStatus.STATUS_DOWNLOAD

    def seeders_num(self):
        return self._info.num_seeds

    def leechers_num(self):
        return self._info.num_leechs

    def uploaded_bytes(self):
        return get_readable_file_size(self._info.uploaded)

    def seed_speed(self):
        return f"{get_readable_file_size(self._info.upspeed)}/s"

    def ratio(self):
        return f"{round(self._info.ratio, 3)}"

    def seeding_time(self):
        return get_readable_time(int(self._info.seeding_time.total_seconds()))

    def task(self):
        return self

    def gid(self):
        return self.hash()[:12]

    def hash(self):
        return self._info.hash

    async def cancel_task(self):
        self.listener.is_cancelled = True
        await self.update()
        await TorrentManager.qbittorrent.torrents.stop([self._info.hash])
        if not self.seeding:
            if self.queued:
                LOGGER.info(f"Cancelling QueueDL: {self.name()}")
                msg = "task have been removed from queue/download"
            else:
                LOGGER.info(f"Cancelling Download: {self._info.name}")
                msg = "Stopped by user!"
            await sleep(0.3)
            await gather(
                self.listener.on_download_error(msg),
                TorrentManager.qbittorrent.torrents.delete([self._info.hash], True),
                TorrentManager.qbittorrent.torrents.delete_tags(
                    tags=[self._info.tags[0]]
                ),
            )
            async with qb_listener_lock:
                if self._info.tags[0] in qb_torrents:
                    del qb_torrents[self._info.tags[0]]
