from asyncio import sleep, TimeoutError
from aiohttp.client_exceptions import ClientError

from ... import LOGGER
from ...core.torrent_manager import TorrentManager, aria2_name


class DirectListener:
    def __init__(self, path, listener, a2c_opt):
        self.listener = listener
        self._path = path
        self._a2c_opt = a2c_opt
        self._proc_bytes = 0
        self._failed = 0
        self.download_task = None
        self.name = self.listener.name

    @property
    def processed_bytes(self):
        if self.download_task:
            return self._proc_bytes + int(self.download_task.get("completedLength", "0"))
        return self._proc_bytes

    @property
    def speed(self):
        return int(self.download_task.get("downloadSpeed", "0")) if self.download_task else 0

    async def download(self, contents):
        self.is_downloading = True
        for content in contents:
            if self.listener.is_cancelled:
                break
            if content["path"]:
                self._a2c_opt["dir"] = f"{self._path}/{content['path']}"
            else:
                self._a2c_opt["dir"] = self._path
            filename = content["filename"]
            self._a2c_opt["out"] = filename
            try:
                gid = await TorrentManager.aria2.addUri(
                    uris=[content["url"]], options=self._a2c_opt, position=0
                )
            except (TimeoutError, ClientError, Exception) as e:
                self._failed += 1
                LOGGER.error(f"Unable to download {filename} due to: {e}")
                continue
            self.download_task = await TorrentManager.aria2.tellStatus(gid)
            while True:
                if self.listener.is_cancelled:
                    if self.download_task:
                        await TorrentManager.aria2_remove(self.download_task)
                    break
                self.download_task = await TorrentManager.aria2.tellStatus(gid)
                if error_message := self.download_task.get("errorMessage"):
                    self._failed += 1
                    LOGGER.error(
                        f"Unable to download {aria2_name(self.download_task)} due to: {error_message}"
                    )
                    await TorrentManager.aria2_remove(self.download_task)
                    break
                elif self.download_task.get("status", "") == "complete":
                    self._proc_bytes += int(self.download_task.get("totalLength", "0"))
                    await TorrentManager.aria2_remove(self.download_task)
                    break
                await sleep(1)
            self.download_task = None
        if self.listener.is_cancelled:
            return
        if self._failed == len(contents):
            await self.listener.on_download_error("All files are failed to download!")
            return
        await self.listener.on_download_complete()
        return

    async def cancel_task(self):
        self.listener.is_cancelled = True
        LOGGER.info(f"Cancelling Download: {self.listener.name}")
        await self.listener.on_download_error("Download Cancelled by User!")
        if self.download_task:
            await TorrentManager.aria2_remove(self.download_task)
