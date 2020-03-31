from .download_helper import DownloadHelper
import time
from youtube_dl import YoutubeDL
import threading
from bot import LOGGER, download_dict_lock, download_dict, DOWNLOAD_DIR
from ..status_utils.youtube_dl_download_status import YoutubeDLDownloadStatus


class YoutubeDLHelper(DownloadHelper):
    def __init__(self, listener):
        super().__init__()
        self.__name = ""
        self.__start_time = time.time()
        self.__listener = listener
        self.__gid = ""
        self.opts = {
            'progress_hooks': [self.__onDownloadProgress],
            'usenetrc': True
        }
        self.__download_speed = 0
        self.download_speed_readable = ''
        self.downloaded_bytes = 0
        self.size = 0
        self.is_playlist = False
        self.last_downloaded = 0
        self.is_cancelled = False
        self.vid_id = ''
        self.__resource_lock = threading.RLock()

    @property
    def download_speed(self):
        with self.__resource_lock:
            return self.__download_speed

    @property
    def gid(self):
        with self.__resource_lock:
            return self.__gid

    def __onDownloadProgress(self, d):
        if self.is_cancelled:
            raise ValueError("Cancelling Download..")
        if d['status'] == "finished":
            if self.is_playlist:
                self.last_downloaded = 0
        elif d['status'] == "downloading":
            with self.__resource_lock:
                self.__download_speed = d['speed']
                if self.is_playlist:
                    progress = d['downloaded_bytes'] / d['total_bytes']
                    chunk_size = d['downloaded_bytes'] - self.last_downloaded
                    self.last_downloaded = d['total_bytes'] * progress
                    self.downloaded_bytes += chunk_size
                    self.progress = (self.downloaded_bytes / self.size) * 100
                else:
                    self.download_speed_readable = d['_speed_str']
                    self.downloaded_bytes = d['downloaded_bytes']

    def __onDownloadStart(self):
        with download_dict_lock:
            download_dict[self.__listener.uid] = YoutubeDLDownloadStatus(self, self.__listener.uid)

    def __onDownloadComplete(self):
        self.__listener.onDownloadComplete()

    def __onDownloadError(self, error):
        self.__listener.onDownloadError(error)

    def extractMetaData(self, link):
        if 'hotstar' in link:
            self.opts['geo_bypass_country'] = 'IN'

        with YoutubeDL(self.opts) as ydl:
            result = ydl.extract_info(link, download=False)
            name = ydl.prepare_filename(result)
        if result.get('direct'):
            return None
        if 'entries' in result:
            video = result['entries'][0]
            for v in result['entries']:
                if v.get('filesize'):
                    self.size += float(v['filesize'])
            # For playlists, ydl.prepare-filename returns the following format: <Playlist Name>-<Id of playlist>.NA
            self.name = name.split(f"-{result['id']}")[0]
            self.vid_id = video.get('id')
            self.is_playlist = True
        else:
            video = result
            if video.get('filesize'):
                self.size = int(video.get('filesize'))
            self.name = name
            self.vid_id = video.get('id')
        return video

    def __download(self, link):
        try:
            with YoutubeDL(self.opts) as ydl:
                ydl.download([link])
            self.__onDownloadComplete()
        except ValueError:
            LOGGER.info("Download Cancelled by User!")
            self.__onDownloadError("Download Cancelled by User!")

    def add_download(self, link, path):
        LOGGER.info(f"Downloading with YT-DL: {link}")
        self.__gid = f"{self.vid_id}{self.__listener.uid}"
        if not self.is_playlist:
            self.opts['outtmpl'] = f"{path}/{self.name}"
        else:
            self.opts['outtmpl'] = f"{path}/{self.name}/%(title)s.%(ext)s"

        self.__onDownloadStart()
        threading.Thread(target=self.__download, args=(link,)).start()

    def cancel_download(self):
        self.is_cancelled = True
