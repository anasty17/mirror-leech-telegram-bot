from bot import aria2, DOWNLOAD_DIR
from bot.helper.ext_utils.bot_utils import MirrorStatus
from .status import Status


def get_download(gid):
    return aria2.get_download(gid)


class AriaDownloadStatus(Status):

    def __init__(self, gid, listener):
        super().__init__()
        self.upload_name = None
        self.is_archiving = False
        self.__gid = gid
        self.__download = get_download(gid)
        self.__uid = listener.uid
        self._listener = listener
        self.last = None
        self.is_waiting = False

    def __update(self):
        self.__download = get_download(self.__gid)

    def progress(self):
        """
        Calculates the progress of the mirror (upload or download)
        :return: returns progress in percentage
        """
        self.__update()
        return self.__download.progress_string()

    def size_raw(self):
        """
        Gets total size of the mirror file/folder
        :return: total size of mirror
        """
        return self.download().total_length

    def processed_bytes(self):
        return self.download().completed_length

    def speed(self):
        return self.download().download_speed_string()

    def name(self):
        return self.download().name

    def path(self):
        return f"{DOWNLOAD_DIR}{self.__uid}"

    def size(self):
        return self.download().total_length_string()

    def eta(self):
        return self.download().eta_string()

    def status(self):
        download = self.download()
        if download.is_waiting:
            status = MirrorStatus.STATUS_WAITING
        elif download.is_paused:
            status = MirrorStatus.STATUS_CANCELLED
        elif download.has_failed:
            status = MirrorStatus.STATUS_FAILED
        else:
            status = MirrorStatus.STATUS_DOWNLOADING
        return status

    def download(self):
        self.__update()
        return self.__download

    def uid(self):
        return self.__uid
