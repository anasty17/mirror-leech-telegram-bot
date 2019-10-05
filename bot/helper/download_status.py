from bot import aria2, DOWNLOAD_DIR
from .bot_utils import get_readable_file_size, MirrorStatus


def get_download(gid):
    return aria2.get_download(gid)


class DownloadStatus:

    def __init__(self, gid, message_id):
        self.__gid = gid
        self.__download = get_download(gid)
        self.__uid = message_id
        self.uploaded_bytes = 0
        self.upload_time = 0

    def __update(self):
        self.__download = get_download(self.__gid)

    def progress(self):
        """
        Calculates the progress of the mirror (upload or download)
        :return: returns progress in percentage
        """
        self.__update()
        if self.status() == MirrorStatus.STATUS_UPLOADING:
            return f'{round(self.upload_progress(), 2)}%'
        return self.__download.progress_string()

    def upload_progress(self):
        return self.uploaded_bytes / self.download().total_length * 100

    def __size(self):
        """
        Gets total size of the mirror file/folder
        :return: total size of mirror
        """
        return self.download().total_length

    def __upload_speed(self):
        """
        Calculates upload speed in bytes/second
        :return: Upload speed in Bytes/Seconds
        """
        try:
            return self.uploaded_bytes / self.upload_time
        except ZeroDivisionError:
            return 0

    def speed(self):
        self.__update()
        if self.status() == MirrorStatus.STATUS_UPLOADING:
            return f'{get_readable_file_size(self.__upload_speed())}/s'
        return self.__download.download_speed_string()

    def name(self):
        return self.__download.name

    def path(self):
        return f"{DOWNLOAD_DIR}{self.__uid}"

    def size(self):
        return self.__download.total_length_string()

    def eta(self):
        self.__update()
        if self.status() == MirrorStatus.STATUS_UPLOADING:
            try:
                return f'{round((self.__size() - self.uploaded_bytes) / self.__upload_speed(), 2)} seconds'
            except ZeroDivisionError:
                return '-'
        return self.__download.eta_string()

    def status(self):
        self.__update()
        status = None
        if self.__download.is_waiting:
            status = MirrorStatus.STATUS_WAITING
        elif self.download().is_paused:
            status = MirrorStatus.STATUS_CANCELLED
        elif self.__download.is_complete:
            # If download exists and is complete the it must be uploading
            # otherwise the gid would have been removed from the download_list
            status = MirrorStatus.STATUS_UPLOADING
        elif self.__download.has_failed:
            status = MirrorStatus.STATUS_FAILED
        elif self.__download.is_active:
            status = MirrorStatus.STATUS_DOWNLOADING
        return status

    def download(self):
        self.__update()
        return self.__download

    def uid(self):
        return self.__uid
