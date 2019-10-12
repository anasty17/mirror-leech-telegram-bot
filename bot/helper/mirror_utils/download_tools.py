from time import sleep
from bot import DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL, aria2
from .download_status import DownloadStatus
from bot.helper.ext_utils.bot_utils import *
from bot.helper.ext_utils.exceptions import KillThreadException


class DownloadHelper:

    def __init__(self, listener=None):
        self.__listener = listener
        self.__is_torrent = False

    def add_download(self, link: str):
        if is_url(link):
            if link.endswith('.torrent'):
                self.__is_torrent = True
            download = aria2.add_uris([link], {'dir': DOWNLOAD_DIR + str(self.__listener.uid)})
        else:
            download = aria2.add_magnet(link, {'dir': DOWNLOAD_DIR + str(self.__listener.uid)})
            self.__is_torrent = True
        with download_dict_lock:
            download_dict[self.__listener.message.message_id] = DownloadStatus(download.gid,
                                                                               self.__listener.uid)
        self.__listener.onDownloadStarted(link)
        self.__update_download_status()

    def __get_download(self):
        return get_download(self.__listener.uid)

    def __get_followed_download_gid(self):
        download = self.__get_download()
        if len(download.followed_by_ids) != 0:
            return download.followed_by_ids[0]
        return None

    def __update_download_status(self):
        status_list = get_download_status_list()
        index = get_download_index(status_list, self.__get_download().gid)
        # This tracks if message exists or did it get replaced by other status message
        should_update = True
        if self.__is_torrent:
            # Waiting for the actual gid
            new_gid = None
            while new_gid is None:
                download = self.__get_download()
                if download.has_failed:
                    self.__listener.onDownloadError(download.error_message, status_list, index)
                    return
                if download.is_paused:
                    self.__listener.onDownloadError("Download cancelled manually by user", status_list, index)
                    return
                sleep(DOWNLOAD_STATUS_UPDATE_INTERVAL)
                if should_update:
                    try:
                        self.__listener.onDownloadProgress(get_download_status_list(), index)
                    except KillThreadException:
                        should_update = False
                        # Check every few seconds
                new_gid = self.__get_followed_download_gid()
            with download_dict_lock:
                download_dict[self.__listener.message.message_id] = DownloadStatus(new_gid,
                                                                               self.__listener.message.message_id)

        # Start tracking the actual download
        previous = None
        download = self.__get_download()
        while not download.is_complete:
            if download.has_failed:
                self.__listener.onDownloadError(self.__get_download().error_message, status_list, index)
                return
            if download.is_paused:
                self.__listener.onDownloadError("Download has been canceled", status_list, index)
                return
            if should_update:
                status_list = get_download_status_list()
                index = get_download_index(status_list, self.__get_download().gid)
                # TODO: Find a better way to differentiate between 2 list of objects
                progress_str_list = get_download_str()
                if progress_str_list != previous:
                    try:
                        self.__listener.onDownloadProgress(status_list, index)
                    except KillThreadException:
                        should_update = False
                    previous = progress_str_list
            download = self.__get_download()
            sleep(DOWNLOAD_STATUS_UPDATE_INTERVAL)

        self.__listener.onDownloadComplete(status_list, index)
