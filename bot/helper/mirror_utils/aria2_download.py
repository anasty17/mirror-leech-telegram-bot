from bot import DOWNLOAD_STATUS_UPDATE_INTERVAL, aria2
from bot.helper.ext_utils.bot_utils import *
from .download_helper import DownloadHelper
from .download_status import DownloadStatus
import threading
from aria2p import API, ClientException
import schedule
import time


class AriaDownloadHelper(DownloadHelper):

    def __init__(self, listener):
        super(AriaDownloadHelper, self).__init__(listener)
        self.__is_torrent = False
        self.gid = None
        self.__scheduler = schedule.every(DOWNLOAD_STATUS_UPDATE_INTERVAL).seconds.do(self.__onDownloadProgress())

    def __updater(self):
        while True:
            with self._resource_lock:
                if self.__scheduler is None:
                    break
            schedule.run_pending()
            time.sleep(1)

    def __onDownloadStarted(self, api, gid):
        with self._resource_lock:
            if self.gid == gid:
                download = api.get_download(gid)
                self.name = download.name
                self.size = download.length
                self._listener.onDownloadStarted()
                self.should_update = True

    def __onDownloadProgress(self):
        with self._resource_lock:
            download = aria2.get_download(self.gid)
            self.progress = download.progress
            self.progress_string = download.progress_string
            self.eta_string = download.eta_string
            self.eta = download.eta

    def __onDownloadComplete(self, api: API, gid):
        with self._resource_lock:
            if self.gid == gid:
                if self.__is_torrent:
                    self.__is_torrent = False
                    self.gid = api.get_download(gid).followed_by_ids[0]
                    LOGGER.info(f'Changed gid from {gid} to {self.gid}')
                else:
                    self._listener.onDownloadComplete()
                    self.__scheduler = None

    def __onDownloadPause(self, api, gid):
        if self.gid == gid:
            self._listener.onDownloadError('Download stopped by user!')

    def __onDownloadStopped(self, api, gid):
        if self.gid == gid:
            self._listener.onDownloadError()

    def __onDownloadError(self, api, gid):
        with self._resource_lock:
            if self.gid == gid:
                download = api.get_download(gid)
                error = download.error_message
                self._listener.onDownloadError(error)

    def add_download(self, link: str, path):
        if is_magnet(link):
            download = aria2.add_magnet(link, {'dir': path})
            self.__is_torrent = True
        else:
            download = aria2.add_uris([link], {'dir': path})
            if download.name.endswith('.torrent'):
                self.__is_torrent = True
        self.gid = download.gid
        aria2.listen_to_notifications(threaded=True, on_download_start=self.__onDownloadStarted,
                                      on_download_error=self.__onDownloadError,
                                      on_download_complete=self.__onDownloadComplete)
        threading.Thread(target=self.__updater).start()

    def cancel_download(self):
        # Returns None if successfully cancelled, else error string
        download = aria2.get_download(self.gid)
        try:
            download.pause(force=True)
        except ClientException:
            return 'Unable to cancel download! Internal error.'
