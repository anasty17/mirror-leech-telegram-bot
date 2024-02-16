from time import sleep

from bot import LOGGER, aria2
from bot.helper.ext_utils.bot_utils import async_to_sync, sync_to_async


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
            return self._proc_bytes + self.download_task.completed_length
        return self._proc_bytes

    @property
    def speed(self):
        return self.download_task.download_speed if self.download_task else 0

    def download(self, contents):
        self.is_downloading = True
        for content in contents:
            if self.listener.isCancelled:
                break
            if content["path"]:
                self._a2c_opt["dir"] = f"{self._path}/{content['path']}"
            else:
                self._a2c_opt["dir"] = self._path
            filename = content["filename"]
            self._a2c_opt["out"] = filename
            try:
                self.download_task = aria2.add_uris(
                    [content["url"]], self._a2c_opt, position=0
                )
            except Exception as e:
                self._failed += 1
                LOGGER.error(f"Unable to download {filename} due to: {e}")
                continue
            self.download_task = self.download_task.live
            while True:
                if self.listener.isCancelled:
                    if self.download_task:
                        self.download_task.remove(True, True)
                    break
                self.download_task = self.download_task.live
                if error_message := self.download_task.error_message:
                    self._failed += 1
                    LOGGER.error(
                        f"Unable to download {self.download_task.name} due to: {error_message}"
                    )
                    self.download_task.remove(True, True)
                    break
                elif self.download_task.is_complete:
                    self._proc_bytes += self.download_task.total_length
                    self.download_task.remove(True)
                    break
                sleep(1)
            self.download_task = None
        if self.listener.isCancelled:
            return
        if self._failed == len(contents):
            async_to_sync(
                self.listener.onDownloadError, "All files are failed to download!"
            )
            return
        async_to_sync(self.listener.onDownloadComplete)

    async def cancel_task(self):
        self.listener.isCancelled = True
        LOGGER.info(f"Cancelling Download: {self.listener.name}")
        await self.listener.onDownloadError("Download Cancelled by User!")
        if self.download_task:
            await sync_to_async(self.download_task.remove, force=True, files=True)
