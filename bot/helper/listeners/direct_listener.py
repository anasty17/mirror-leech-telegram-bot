from time import sleep

from bot import LOGGER, aria2
from bot.helper.ext_utils.bot_utils import async_to_sync, sync_to_async


class DirectListener:
    def __init__(self, foldername, total_size, path, listener, a2c_opt):
        self.name = foldername
        self.total_size = total_size
        self.__path = path
        self.__listener = listener
        self.__download = None
        self.is_downloading = False
        self.__a2c_opt = a2c_opt
        self.proc_bytes = 0
        self.file_processed_bytes = 0
        self.failed = 0

    @property
    def processed_bytes(self):
        if self.__download:
            return self.file_processed_bytes + self.__download.completed_length
        return self.file_processed_bytes

    @property
    def speed(self):
        return self.__download.download_speed if self.__download else 0

    def download(self, contents):
        self.is_downloading = True
        for content in contents:
            if not self.is_downloading:
                break
            if content['path']:
                self.__a2c_opt['dir'] = f"{self.__path}/{content['path']}"
            else:
                self.__a2c_opt['dir'] = self.__path
            filename = content['filename']
            self.__a2c_opt['out'] = filename
            try:
                self.__download = aria2.add_uris([content['url']], self.__a2c_opt)
            except Exception as e:
                self.failed += 1
                LOGGER.error(f'Unable to download {filename} due to: {e}')
                continue
            self.__download = self.__download.live
            while True:
                if not self.is_downloading:
                    if self.__download:
                        self.__download.remove(True, True)
                    break
                self.__download = self.__download.live
                if error_message:= self.__download.error_message:
                    self.failed += 1
                    LOGGER.error(f'Unable to download {self.__download.name} due to: {error_message}')
                    self.__download.remove(True, True)
                    break
                elif self.__download.is_complete:
                    self.file_processed_bytes += self.__download.completed_length
                    self.__download.remove(True)
                    break
                sleep(1)
            self.__download = None
        if not self.is_downloading:
            return
        if self.failed == len(contents):
            async_to_sync(self.__listener.onDownloadError, 'All files are failed to download!')
            return
        async_to_sync(self.__listener.onDownloadComplete)

    async def cancel_download(self):
        self.is_downloading = False
        LOGGER.info(f"Cancelling Download: {self.name}")
        await self.__listener.onDownloadError("Download Cancelled by User!")
        if self.__download:
            await sync_to_async(self.__download.remove, force=True, files=True)