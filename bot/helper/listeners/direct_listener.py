from time import sleep

from bot import LOGGER, aria2
from bot.helper.ext_utils.bot_utils import async_to_sync


class DirectListener:
    def __init__(self, foldername, total_size, path, listener, a2c_opt):
        self.name = foldername
        self.total_size = total_size
        self.__path = path
        self.__listener = listener
        self.__downloads = []
        self.is_downloading = False
        self.is_finished = False
        self.__a2c_opt = a2c_opt
        self.proc_bytes = 0
        self.file_processed_bytes = 0
        self.failed = 0
        self.speed = 0

    @property
    def processed_bytes(self):
        return self.proc_bytes

    def progress(self):
        self.proc_bytes = self.file_processed_bytes
        should_remove = []
        self.speed = 0
        for i, download in enumerate(self.__downloads):
            download = download.live
            self.speed += download.download_speed
            self.proc_bytes += download.completed_length
            if error_message:= download.error_message:
                self.failed += 1
                LOGGER.error(f'Unable to download {download.name} due to: {error_message}')
                download.remove(True, True)
                should_remove.append(i)
            elif download.is_complete:
                self.file_processed_bytes += download.completed_length
                download.remove(True)
                should_remove.append(i)
        if should_remove:
            for i in should_remove:
                del self.__downloads[i]
        if not self.__downloads:
            self.is_finished = True

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
                download = aria2.add_uris([content['url']], self.__a2c_opt)
            except Exception as e:
                self.failed += 1
                LOGGER.error(f'Unable to download {filename} due to: {e}')
                continue
            download = download.live
            self.__downloads.append(download)
        while not self.is_finished and self.is_downloading:
            self.progress()
            sleep(3)
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
        if self.__downloads:
            for download in self.__downloads:
                download = download.live
                download.remove(True, True)