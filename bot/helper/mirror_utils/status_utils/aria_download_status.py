from bot import aria2, DOWNLOAD_DIR, LOGGER
from bot.helper.ext_utils.bot_utils import MirrorStatus
from .status import Status

def get_download(gid):
    return aria2.get_download(gid)


class AriaDownloadStatus(Status):

    def __init__(self, gid, listener):
        super().__init__()
        self.__gid = gid
        self.__download = get_download(self.__gid)
        self.__uid = listener.uid
        self.__listener = listener
        self.message = listener.message

    def __update(self):
        self.__download = get_download(self.__gid)
        if self.__download.followed_by_ids:
            self.__gid = self.__download.followed_by_ids[0]

    def progress(self):
        """
        Calculates the progress of the mirror (upload or download)
        :return: returns progress in percentage
        """
        return self.__download.progress_string()

    def size_raw(self):
        """
        Gets total size of the mirror file/folder
        :return: total size of mirror
        """
        return self.aria_download().total_length

    def processed_bytes(self):
        return self.aria_download().completed_length

    def speed(self):
        return self.aria_download().download_speed_string()

    def name(self):
        return self.aria_download().name

    def path(self):
        return f"{DOWNLOAD_DIR}{self.__uid}"

    def size(self):
        return self.aria_download().total_length_string()

    def eta(self):
        return self.aria_download().eta_string()

    def status(self):
        download = self.aria_download()
        if download.is_waiting:
            return MirrorStatus.STATUS_WAITING
        elif download.has_failed:
            return MirrorStatus.STATUS_FAILED
        else:
            return MirrorStatus.STATUS_DOWNLOADING

    def aria_download(self):
        self.__update()
        return self.__download

    def download(self):
        return self

    def getListener(self):
        return self.__listener

    def uid(self):
        return self.__uid

    def gid(self):
        self.__update()
        return self.__gid

    def cancel_download(self):
        LOGGER.info(f"Cancelling Download: {self.name()}")
        download = self.aria_download()
        if download.is_waiting:
            self.__listener.onDownloadError("Cancelled by user")
            aria2.remove([download], force=True)
            return
        if len(download.followed_by_ids) != 0:
            downloads = aria2.get_downloads(download.followed_by_ids)
            self.__listener.onDownloadError('Download stopped by user!')
            aria2.remove(downloads, force=True)
            aria2.remove([download], force=True)
            return
        self.__listener.onDownloadError('Download stopped by user!')
        aria2.remove([download], force=True)
