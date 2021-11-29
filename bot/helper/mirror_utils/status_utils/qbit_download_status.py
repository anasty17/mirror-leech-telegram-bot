from bot import DOWNLOAD_DIR, LOGGER
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time
from .status import Status
from time import sleep


class QbDownloadStatus(Status):

    def __init__(self, gid, listener, qbhash, client):
        super().__init__()
        self.__gid = gid
        self.__hash = qbhash
        self.client = client
        self.__uid = listener.uid
        self.listener = listener
        self.message = listener.message


    def progress(self):
        """
        Calculates the progress of the mirror (upload or download)
        :return: returns progress in percentage
        """
        return f'{round(self.torrent_info().progress*100,2)}%'

    def size_raw(self):
        """
        Gets total size of the mirror file/folder
        :return: total size of mirror
        """
        return self.torrent_info().size

    def processed_bytes(self):
        return self.torrent_info().downloaded

    def speed(self):
        return f"{get_readable_file_size(self.torrent_info().dlspeed)}/s"

    def name(self):
        return self.torrent_info().name

    def path(self):
        return f"{DOWNLOAD_DIR}{self.__uid}"

    def size(self):
        return get_readable_file_size(self.torrent_info().size)

    def eta(self):
        return get_readable_time(self.torrent_info().eta)

    def status(self):
        download = self.torrent_info().state
        if download == "queuedDL":
            return MirrorStatus.STATUS_WAITING
        elif download in ["metaDL", "checkingResumeData"]:
            return MirrorStatus.STATUS_DOWNLOADING + " (Metadata)"
        elif download == "pausedDL":
            return MirrorStatus.STATUS_PAUSE
        elif download == "checkingUP":
            return MirrorStatus.STATUS_CHECKING
        else:
            return MirrorStatus.STATUS_DOWNLOADING

    def torrent_info(self):
        return self.client.torrents_info(torrent_hashes=self.__hash)[0]

    def download(self):
        return self

    def uid(self):
        return self.__uid

    def gid(self):
        return self.__gid

    def cancel_download(self):
        LOGGER.info(f"Cancelling Download: {self.name()}")
        self.client.torrents_pause(torrent_hashes=self.__hash)
        sleep(0.3)
        self.listener.onDownloadError('Download stopped by user!')
        self.client.torrents_delete(torrent_hashes=self.__hash)
