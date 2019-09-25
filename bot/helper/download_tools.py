from time import sleep
from bot import LOGGER, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL, download_list, aria2
from bot.helper.listeners import *
from urllib.parse import urlparse


def is_url(url: str):
    try:
        urlparse(url)
        return True
    except ValueError:
        return False


def is_magnet(url: str):
    if "magnet" in url:
        return True
    else:
        return False


class DownloadHelper:

    def __init__(self, listener: MirrorListeners):
        self.__listener = listener

    def add_download(self, link: str):
        download = None
        if is_url(link):
            download = aria2.add_uris([link], {'dir': DOWNLOAD_DIR + str(self.__listener.update.update_id),
                                                      'max_download_limit': 1})
        elif is_magnet(link):
            download = aria2.add_magnet(link, {'dir': DOWNLOAD_DIR})
        else:
            self.__listener.onDownloadError("No download URL or URL malformed")
            return
        download_list[self.__listener.update.update_id] = download.gid
        self.__listener.onDownloadStarted(link)
        self.__update_download_status()

    def get_downloads_status_str_list(self):
        """
        Generates a human readable string of progress of all the downloads
        :return: list of strings of progress of all the downloads
        """
        str_list = []
        LOGGER.info(download_list)
        for gid in list(download_list.values()):
            download = aria2.get_download(gid)
            str_list.append("<b>" + download.name + "</b>:- "
                            + download.progress_string() + " of "
                            + download.total_length_string()
                            + " at " + download.download_speed_string()
                            + " ,ETA: " + download.eta_string()
                            )
        return str_list

    def __get_download(self):
        return aria2.get_download(download_list[self.__listener.update.update_id])

    def __update_download_status(self):
        # TODO: Try to find a way to move this code to mirror.py and send only a
        #   list of Download objects to onDownloadProgress()
        previous = None
        LOGGER.info(self.get_downloads_status_str_list())
        while not self.__get_download().is_complete:
            if self.__get_download().has_failed:
                self.__listener.onDownloadError(self.__get_download().error_message)
                break
            progress_str_list = self.get_downloads_status_str_list()
            if progress_str_list != previous:
                self.__listener.onDownloadProgress(progress_str_list)
                previous = progress_str_list
            sleep(DOWNLOAD_STATUS_UPDATE_INTERVAL)

        self.__listener.onDownloadComplete(self.__get_download())
