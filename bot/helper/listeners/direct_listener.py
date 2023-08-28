from time import sleep, time

from bot import LOGGER, aria2
from bot.helper.ext_utils.bot_utils import async_to_sync, sync_to_async


class DirectListener:
    def __init__(self, foldername, total_size, path, listener, a2c_opt):
        self.name = foldername
        self.total_size = total_size
        self.__path = path
        self.__listener = listener
        self.__downloads = []
        self.is_downloading = False
        self.__a2c_opt = a2c_opt
        self.proc_bytes = 0
        self.__startTime = time()

    @property
    def speed(self):
        try:
            return self.proc_bytes / (time() - self.__startTime)
        except:
            return 0

    @property
    def processed_bytes(self):
        self.proc_bytes = 0
        for download in self.__downloads:
            download = download.live
            self.proc_bytes += download.completed_length
        return self.proc_bytes

    def download(self, contents):
        self.is_downloading = True
        failed = 0
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
                failed += 1
                LOGGER.error(f'Unable to download {filename} due to: {e}')
                continue
            download = download.live
            self.__downloads.append(download)
            while True:
                if error_message:= download.error_message:
                    failed += 1
                    LOGGER.error(f'Unable to download {filename} due to: {error_message}')
                    break
                if download.is_removed:
                    break
                if download.is_complete:
                    break
                if not self.is_downloading:
                    break
                download = download.live
                sleep(1)
        if not self.is_downloading:
            return
        if failed == len(contents):
            self.__remove(True)
            async_to_sync(self.__listener.onDownloadError, 'All files are failed to download!')
            return
        self.__remove()
        async_to_sync(self.__listener.onDownloadComplete)
    
    def __remove(self, files=False):
        for download in self.__downloads:
            try:
                if download.is_removed:
                    continue
                download = download.live
                download.remove(True, files)
            except:
                pass
    
    async def cancel_download(self):
        self.is_downloading = False
        LOGGER.info(f"Cancelling Download: {self.name}")
        await self.__listener.onDownloadError("Download Cancelled by User!")
        await sync_to_async(self.__remove)