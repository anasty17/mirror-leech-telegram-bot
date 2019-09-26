from time import sleep
from bot import LOGGER, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL, download_list, aria2
from bot.helper.listeners import *
from .download_status import DownloadStatus
from .bot_utils import *


class DownloadHelper:

    def __init__(self, listener: MirrorListeners):
        self.__listener = listener
        self.__is_torrent = False

    def is_url(self, url: str):
        # TODO: Find the proper way to validate the url
        if url.startswith('https://') or url.startswith('http://'):
            return True
        return False

    def is_magnet(self, url: str):
        if "magnet" in url:
            return True
        else:
            return False

    def add_download(self, link: str):
        download = None
        if self.is_url(link):
            download = aria2.add_uris([link], {'dir': DOWNLOAD_DIR + str(self.__listener.update.update_id)})
        elif self.is_magnet(link):
            download = aria2.add_magnet(link, {'dir': DOWNLOAD_DIR + str(self.__listener.update.update_id)})
            self.__is_torrent = True
        else:
            self.__listener.onDownloadError("No download URL or URL malformed")
            return
        download_list[self.__listener.update.update_id] = DownloadStatus(download.gid)
        self.__listener.onDownloadStarted(link)
        self.__update_download_status()

    def __get_download(self):
        return get_download(self.__listener.update.update_id)

    def __get_followed_download_gid(self):
        download = self.__get_download()
        if len(download.followed_by_ids) != 0:
            return download.followed_by_ids[0]
        return None

    def __update_download_status(self):
        status_list = get_download_status_list()
        index = get_download_index(status_list, self.__get_download().gid)
        if self.__is_torrent:
            # Waiting for the actual gid
            new_gid = None
            while new_gid is None:
                # Check every few seconds
                sleep(DOWNLOAD_STATUS_UPDATE_INTERVAL)
                new_gid = self.__get_followed_download_gid()
                self.__listener.onDownloadProgress(get_download_status_list(), index)
            download_list[self.__listener.update.update_id] = DownloadStatus(new_gid)

        # Start tracking the actual download
        previous = None
        while not self.__get_download().is_complete:
            if self.__get_download().has_failed:
                self.__listener.onDownloadError(self.__get_download().error_message)
                break
            # TODO: Find a better way
            progress_str_list = get_download_str_list()
            if progress_str_list != previous:
                self.__listener.onDownloadProgress(status_list,
                                                   get_download_index(status_list, self.__get_download().gid))
                previous = progress_str_list

            sleep(DOWNLOAD_STATUS_UPDATE_INTERVAL)

        self.__listener.onDownloadComplete(status_list, get_download_index(status_list, self.__get_download().gid))
