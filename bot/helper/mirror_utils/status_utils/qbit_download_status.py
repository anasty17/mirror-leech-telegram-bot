from time import sleep

from bot import LOGGER, get_client
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time

def get_download(client, hash_):
    try:
        return client.torrents_info(torrent_hashes=hash_)[0]
    except Exception as e:
        LOGGER.error(f'{e}: Qbittorrent, Error while getting torrent info')
        client = get_client()
        return get_download(client, hash_)


class QbDownloadStatus:

    def __init__(self, listener, hash_, seeding=False):
        self.__client = get_client()
        self.__listener = listener
        self.__hash = hash_
        self.__info = get_download(self.__client, self.__hash)
        self.seeding = seeding
        self.message = listener.message

    def __update(self):
        self.__info = get_download(self.__client, self.__hash)

    def progress(self):
        """
        Calculates the progress of the mirror (upload or download)
        :return: returns progress in percentage
        """
        return f'{round(self.__info.progress*100, 2)}%'

    def size_raw(self):
        """
        Gets total size of the mirror file/folder
        :return: total size of mirror
        """
        return self.__info.size

    def processed_bytes(self):
        return self.__info.downloaded

    def speed(self):
        self.__update()
        return f"{get_readable_file_size(self.__info.dlspeed)}/s"

    def name(self):
        if self.__info.state in ["metaDL", "checkingResumeData"]:
            return f"[METADATA]{self.__info.name}"
        else:
            return self.__info.name

    def size(self):
        return get_readable_file_size(self.__info.size)

    def eta(self):
        return get_readable_time(self.__info.eta)

    def status(self):
        self.__update()
        download = self.__info.state
        if download in ["queuedDL", "queuedUP"]:
            return MirrorStatus.STATUS_QUEUEDL
        elif download in ["pausedDL", "pausedUP"]:
            return MirrorStatus.STATUS_PAUSED
        elif download in ["checkingUP", "checkingDL"]:
            return MirrorStatus.STATUS_CHECKING
        elif download in ["stalledUP", "uploading"] and self.seeding:
            return MirrorStatus.STATUS_SEEDING
        else:
            return MirrorStatus.STATUS_DOWNLOADING

    def seeders_num(self):
        return self.__info.num_seeds

    def leechers_num(self):
        return self.__info.num_leechs

    def uploaded_bytes(self):
        return f"{get_readable_file_size(self.__info.uploaded)}"

    def upload_speed(self):
        self.__update()
        return f"{get_readable_file_size(self.__info.upspeed)}/s"

    def ratio(self):
        return f"{round(self.__info.ratio, 3)}"

    def seeding_time(self):
        return f"{get_readable_time(self.__info.seeding_time)}"

    def download(self):
        return self

    def gid(self):
        return self.__hash[:12]

    def hash(self):
        return self.__hash

    def client(self):
        return self.__client

    def listener(self):
        return self.__listener

    def cancel_download(self):
        self.__client.torrents_pause(torrent_hashes=self.__hash)
        if self.status() != MirrorStatus.STATUS_SEEDING:
            LOGGER.info(f"Cancelling Download: {self.__info.name}")
            sleep(0.3)
            self.__listener.onDownloadError('Download stopped by user!')
            self.__client.torrents_delete(torrent_hashes=self.__hash, delete_files=True)
