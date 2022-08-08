from time import time

from bot import aria2, LOGGER
from bot.helper.ext_utils.bot_utils import MirrorStatus, get_readable_time

def get_download(gid):
    try:
        return aria2.get_download(gid)
    except Exception as e:
        LOGGER.error(f'{e}: while getting torrent info')


class AriaDownloadStatus:

    def __init__(self, gid, listener):
        self.__gid = gid
        self.__download = get_download(gid)
        self.__listener = listener
        self.start_time = 0
        self.message = listener.message

    def __update(self):
        self.__download = self.__download.live
        if self.__download.followed_by_ids:
            self.__gid = self.__download.followed_by_ids[0]
            self.__download = get_download(self.__gid)

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
        return self.__download.total_length

    def processed_bytes(self):
        return self.__download.completed_length

    def speed(self):
        self.__update()
        return self.__download.download_speed_string()

    def name(self):
        self.__update()
        return self.__download.name

    def size(self):
        return self.__download.total_length_string()

    def eta(self):
        return self.__download.eta_string()

    def status(self):
        download = self.__download
        if download.is_waiting:
            return MirrorStatus.STATUS_WAITING
        elif download.is_paused:
            return MirrorStatus.STATUS_PAUSED
        elif download.seeder and hasattr(self.__listener, 'uploaded'):
            return MirrorStatus.STATUS_SEEDING
        else:
            return MirrorStatus.STATUS_DOWNLOADING

    def seeders_num(self):
        return self.__download.num_seeders

    def leechers_num(self):
        return self.__download.connections

    def uploaded_bytes(self):
        return self.__download.upload_length_string()

    def upload_speed(self):
        return self.__download.upload_speed_string()

    def ratio(self):
        return f"{round(self.__download.upload_length / self.__download.completed_length, 3)}"

    def seeding_time(self):
        return f"{get_readable_time(time() - self.start_time)}"

    def download(self):
        return self

    def listener(self):
        return self.__listener

    def gid(self):
        self.__update()
        return self.__gid

    def cancel_download(self):
        self.__update()
        if self.__download.seeder:
            LOGGER.info(f"Cancelling Seed: {self.name}")
            self.__listener.onUploadError(f"Seeding stopped with Ratio: {self.ratio()} and Time: {self.seeding_time()}")
            aria2.remove([self.__download], force=True, files=True)
        elif len(self.__download.followed_by_ids) != 0:
            LOGGER.info(f"Cancelling Download: {self.name()}")
            downloads = aria2.get_downloads(self.__download.followed_by_ids)
            self.__listener.onDownloadError('Download stopped by user!')
            aria2.remove(downloads, force=True, files=True)
        else:
            LOGGER.info(f"Cancelling Download: {self.name()}")
            self.__listener.onDownloadError('Download stopped by user!')
        aria2.remove([self.__download], force=True, files=True)
