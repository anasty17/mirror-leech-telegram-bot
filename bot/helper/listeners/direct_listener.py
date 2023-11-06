from time import sleep

from bot import LOGGER, aria2
from bot.helper.ext_utils.bot_utils import async_to_sync, sync_to_async


class DirectListener:
    def __init__(self, total_size, path, listener, a2c_opt):
        self._path = path
        self._listener = listener
        self._is_cancelled = False
        self._a2c_opt = a2c_opt
        self._proc_bytes = 0
        self._failed = 0
        self.task = None
        self.name = self._listener.name
        self.total_size = total_size

    @property
    def processed_bytes(self):
        if self.task:
            return self._proc_bytes + self.task.completed_length
        return self._proc_bytes

    @property
    def speed(self):
        return self.task.download_speed if self.task else 0

    def download(self, contents):
        self.is_downloading = True
        for content in contents:
            if self._is_cancelled:
                break
            if content["path"]:
                self._a2c_opt["dir"] = f"{self._path}/{content['path']}"
            else:
                self._a2c_opt["dir"] = self._path
            filename = content["filename"]
            self._a2c_opt["out"] = filename
            try:
                self.task = aria2.add_uris([content["url"]], self._a2c_opt, position=0)
            except Exception as e:
                self._failed += 1
                LOGGER.error(f"Unable to download {filename} due to: {e}")
                continue
            self.task = self.task.live
            while True:
                if self._is_cancelled:
                    if self.task:
                        self.task.remove(True, True)
                    break
                self.task = self.task.live
                if error_message := self.task.error_message:
                    self._failed += 1
                    LOGGER.error(
                        f"Unable to download {self.task.name} due to: {error_message}"
                    )
                    self.task.remove(True, True)
                    break
                elif self.task.is_complete:
                    self._proc_bytes += self.task.total_length
                    self.task.remove(True)
                    break
                sleep(1)
            self.task = None
        if self._is_cancelled:
            return
        if self._failed == len(contents):
            async_to_sync(
                self._listener.onDownloadError, "All files are failed to download!"
            )
            return
        async_to_sync(self._listener.onDownloadComplete)

    async def cancel_task(self):
        self._is_cancelled = True
        LOGGER.info(f"Cancelling Download: {self._listener.name}")
        await self._listener.onDownloadError("Download Cancelled by User!")
        if self.task:
            await sync_to_async(self.task.remove, force=True, files=True)
