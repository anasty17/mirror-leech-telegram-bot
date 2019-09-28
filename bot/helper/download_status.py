from bot import aria2, download_dict, DOWNLOAD_DIR


def get_download(gid):
    return aria2.get_download(gid)


class DownloadStatus:
    STATUS_UPLOADING = "Uploading"
    STATUS_DOWNLOADING = "Downloading"
    STATUS_WAITING = "Queued"
    STATUS_FAILED = "Failed. Cleaning download"
    STATUS_CANCELLED = "Cancelled"

    def __init__(self, gid, message_id):
        self.__gid = gid
        self.__download = get_download(gid)
        self.__uid = message_id

    def __update(self):
        self.__download = get_download(self.__gid)

    def progress(self):
        self.__update()
        return self.__download.progress_string()

    def speed(self):
        self.__update()
        return self.__download.download_speed_string()

    def name(self):
        return self.__download.name

    def path(self):
        return "{}{}".format(DOWNLOAD_DIR, self.__uid)

    def size(self):
        return self.__download.total_length_string()

    def eta(self):
        self.__update()
        return self.__download.eta_string()

    def status(self):
        self.__update()
        status = None
        if self.__download.is_waiting:
            status = DownloadStatus.STATUS_WAITING
        elif self.download().is_paused:
            status = DownloadStatus.STATUS_CANCELLED
        elif self.__download.is_complete:
            # If download exists and is complete the it must be uploading
            # otherwise the gid would have been removed from the download_list
            status = DownloadStatus.STATUS_UPLOADING
        elif self.__download.has_failed:
            status = DownloadStatus.STATUS_FAILED
        elif self.__download.is_active:
            status = DownloadStatus.STATUS_DOWNLOADING
        return status

    def download(self):
        self.__update()
        return self.__download