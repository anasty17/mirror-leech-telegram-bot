from bot import aria2, DOWNLOAD_DIR
from bot.helper.ext_utils.bot_utils import get_readable_file_size, MirrorStatus, get_readable_time


def get_download(gid):
    return aria2.get_download(gid)


class DownloadStatus:

    def __init__(self, gid, message_id):
        self.upload_name = None
        self.is_archiving = False
        self.__gid = gid
        self.__download = get_download(gid)
        self.__uid = message_id
        self.upload_helper = None

    def __update(self):
        self.__download = get_download(self.__gid)

    def progress(self):
        """
        Calculates the progress of the mirror (upload or download)
        :return: returns progress in percentage
        """
        self.__update()
        if self.upload_helper is not None:
            return f'{round(self.upload_progress(), 2)}%'
        return self.__download.progress_string()

    def upload_progress(self):
        return self.upload_helper.uploaded_bytes / self.download().total_length * 100

    def __size(self):
        """
        Gets total size of the mirror file/folder
        :return: total size of mirror
        """
        return self.download().total_length

    def __upload_speed(self):
        """
        :return: Upload speed in Bytes/Seconds
        """
        return self.upload_helper.speed()

    def speed(self):
        self.__update()
        if self.upload_helper is not None:
            return f'{get_readable_file_size(self.__upload_speed())}/s'
        return self.__download.download_speed_string()

    def name(self):
        if self.upload_name is not None:
            return self.upload_name
        return self.__download.name

    def path(self):
        return f"{DOWNLOAD_DIR}{self.__uid}"

    def size(self):
        return self.__download.total_length_string()

    def eta(self):
        self.__update()
        if self.upload_helper is not None:
            try:
                seconds = (self.__size() - self.upload_helper.uploaded_bytes) / self.__upload_speed()
                return f'{get_readable_time(seconds)}'
            except ZeroDivisionError:
                return '-'
        return self.__download.eta_string()

    def status(self):
        self.__update()
        if self.is_archiving:
            status = MirrorStatus.STATUS_ARCHIVING
        elif self.download().is_waiting:
            status = MirrorStatus.STATUS_WAITING
        elif self.download().is_paused:
            status = MirrorStatus.STATUS_CANCELLED
        elif self.upload_helper is not None:
            status = MirrorStatus.STATUS_UPLOADING
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
