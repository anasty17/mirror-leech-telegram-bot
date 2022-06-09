from bot import DOWNLOAD_DIR, LOGGER
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_readable_time

def get_download(client, hash_):
    try:
        return client.torrents_info(torrent_hashes=hash_)[0]
    except Exception as e:
        LOGGER.error(f'{e}: while getting torrent info')


class QbDownloadStatus:

    def __init__(self, listener, obj):
        self.__obj = obj
        self.__listener = listener
        self.__uid = listener.uid
        self.__info = get_download(obj.client, obj.ext_hash)
        self.message = listener.message

    def __update(self):
        self.__info = get_download(self.__obj.client, self.__obj.ext_hash)

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
        if self.__obj.select:
            return self.__info.size
        else:
            return self.__info.total_size

    def processed_bytes(self):
        return self.__info.downloaded

    def speed(self):
        self.__update()
        return f"{get_readable_file_size(self.__info.dlspeed)}/s"

    def name(self):
        self.__update()
        return self.__info.name

    def path(self):
        return f"{DOWNLOAD_DIR}{self.__uid}"

    def size(self):
        return get_readable_file_size(self.__info.size)

    def eta(self):
        return get_readable_time(self.__info.eta)

    def status(self):
        download = self.__info.state
        if download in ["queuedDL", "queuedUP"]:
            return MirrorStatus.STATUS_WAITING
        elif download in ["metaDL", "checkingResumeData"]:
            return MirrorStatus.STATUS_DOWNLOADING + " (Metadata)"
        elif download in ["pausedDL", "pausedUP"]:
            return MirrorStatus.STATUS_PAUSE
        elif download in ["checkingUP", "checkingDL"]:
            return MirrorStatus.STATUS_CHECKING
        elif download in ["stalledUP", "uploading"] and self.__obj.is_seeding:
            return MirrorStatus.STATUS_SEEDING
        else:
            return MirrorStatus.STATUS_DOWNLOADING

    def torrent_info(self):
        return self.__info

    def download(self):
        return self.__obj

    def gid(self):
        return self.__obj.ext_hash[:12]

    def client(self):
        return self.__obj.client

    def listener(self):
        return self.__listener
