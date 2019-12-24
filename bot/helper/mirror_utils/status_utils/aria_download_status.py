from bot import aria2, DOWNLOAD_DIR
from bot.helper.ext_utils.bot_utils import get_readable_file_size, MirrorStatus, get_readable_time
from .download_status import DownloadStatus


def get_download(gid):
    return aria2.get_download(gid)


class AriaDownloadStatus(DownloadStatus):

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

    def speed(self):
        self.__update()
        return self.__download.download_speed_string()

    def name(self):
        self.__update()
        return self.__download.name

    def path(self):
        return f"{DOWNLOAD_DIR}{self.__uid}"

    def size(self):
        return self.__download.total_length_string()

    def eta(self):
        self.__update()
        return self.__download.eta_string()

    def status(self):
        self.__update()
        if self.download().is_waiting:
            status = MirrorStatus.STATUS_WAITING
        elif self.download().is_paused:
            status = MirrorStatus.STATUS_CANCELLED
        elif self.__download.has_failed:
            status = MirrorStatus.STATUS_FAILED
        else:
            status = MirrorStatus.STATUS_DOWNLOADING
        return status

    def download(self):
        self.__update()
        return self.__download

    def uid(self):
        return self.__uid
