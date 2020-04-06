from bot import aria2
from bot.helper.ext_utils.bot_utils import *
from .download_helper import DownloadHelper
from bot.helper.mirror_utils.status_utils.aria_download_status import AriaDownloadStatus
from bot.helper.telegram_helper.message_utils import *
import threading
from aria2p import API


class AriaDownloadHelper(DownloadHelper):

    def __init__(self, listener):
        super().__init__()
        self.gid = None
        self.__listener = listener
        self._resource_lock = threading.RLock()

    def __onDownloadStarted(self, api, gid):
        with self._resource_lock:
            if self.gid == gid:
                download = api.get_download(gid)
                self.name = download.name
                update_all_messages()

    def __onDownloadComplete(self, api: API, gid):
        with self._resource_lock:
            if self.gid == gid:
                download = api.get_download(gid)
                if download.followed_by_ids:
                    self.gid = download.followed_by_ids[0]
                    with download_dict_lock:
                        download_dict[self.__listener.uid] = AriaDownloadStatus(self, self.__listener)
                    if download.is_torrent:
                        download_dict[self.__listener.uid].is_torrent = True
                    update_all_messages()
                    LOGGER.info(f'Changed gid from {gid} to {self.gid}')
                else:
                    self.__listener.onDownloadComplete()

    def __onDownloadPause(self, api, gid):
        if self.gid == gid:
            LOGGER.info("Called onDownloadPause")
            self.__listener.onDownloadError('Download stopped by user!')

    def __onDownloadStopped(self, api, gid):
        if self.gid == gid:
            LOGGER.info("Called on_download_stop")
            self.__listener.onDownloadError('Download stopped by user!')

    def __onDownloadError(self, api, gid):
        with self._resource_lock:
            if self.gid == gid:
                download = api.get_download(gid)
                error = download.error_message
                LOGGER.info(f"Download Error: {error}")
                self.__listener.onDownloadError(error)

    def add_download(self, link: str, path):
        if is_magnet(link):
            download = aria2.add_magnet(link, {'dir': path})
        else:
            download = aria2.add_uris([link], {'dir': path})
        self.gid = download.gid
        with download_dict_lock:
            download_dict[self.__listener.uid] = AriaDownloadStatus(self, self.__listener)
        if download.error_message:
            self.__listener.onDownloadError(download.error_message)
            return
        LOGGER.info(f"Started: {self.gid} DIR:{download.dir} ")
        aria2.listen_to_notifications(threaded=True, on_download_start=self.__onDownloadStarted,
                                      on_download_error=self.__onDownloadError,
                                      on_download_pause=self.__onDownloadPause,
                                      on_download_stop=self.__onDownloadStopped,
                                      on_download_complete=self.__onDownloadComplete)

    def cancel_download(self):
        download = aria2.get_download(self.gid)
        if download.is_waiting:
            aria2.remove([download])
            self.__listener.onDownloadError("Cancelled by user")
            return
        if len(download.followed_by_ids) != 0:
            downloads = aria2.get_downloads(download.followed_by_ids)
            aria2.pause(downloads)
        aria2.pause([download])
