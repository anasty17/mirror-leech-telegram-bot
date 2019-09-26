from time import sleep
from bot import LOGGER, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL, download_list, aria2
from bot.helper.listeners import *
from urllib.parse import urlparse


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
            download = aria2.add_magnet(link, {'dir': DOWNLOAD_DIR})
            self.__is_torrent = True
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

    def __get_followed_download_gid(self):
        download = self.__get_download()
        if len(download.followed_by_ids) != 0:
            return download.followed_by_ids[0]
        return None

    def __update_download_status(self):
        # TODO: Try to find a way to move this code to mirror.py and send only a
        #   list of Download objects to onDownloadProgress()
        previous = None
        LOGGER.info(self.get_downloads_status_str_list())
        if self.__is_torrent:
            # Waiting for the actual gid
            new_gid = None
            while new_gid is None:
                # Check every few seconds
                sleep(DOWNLOAD_STATUS_UPDATE_INTERVAL)
                new_gid = self.__get_followed_download_gid()
            download_list[self.__listener.update.update_id] = new_gid

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
