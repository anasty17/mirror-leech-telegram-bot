from .download_helper import DownloadHelper
import time
from youtube_dl import YoutubeDL
import threading
from bot import LOGGER,download_dict_lock,download_dict,DOWNLOAD_DIR
from ..status_utils.youtube_dl_download_status import YoutubeDLDownloadStatus

class YoutubeDLHelper(DownloadHelper):
    def __init__(self, listener):
        super().__init__()
        self.__name = ""
        self.__start_time = time.time()
        self.__listener = listener
        self.__gid = ""
        self.opts = {
        'format': 'bestaudio/best',
        'progress_hooks':[self.__onDownloadProgress],
        'outtmpl': f"{DOWNLOAD_DIR}{self.__listener.uid}/%(title)s.%(ext)s"
        }
        self.ydl = YoutubeDL(self.opts)
        self.__download_speed = 0
        self.download_speed_readable = ""
        self.downloaded_bytes = 0
        self.size = 0
        self.is_playlist = False
        self.last_downloaded = 0
        self.is_cancelled = False
        self.__resource_lock = threading.RLock()

    @property
    def download_speed(self):
        with self.__resource_lock:
            return self.__download_speed

    @property
    def gid(self):
        with self.__resource_lock:
            return self.__gid

    def __onDownloadProgress(self,d):
        if self.is_cancelled:
            raise ValueError("Cancelling Download..")
        if d['status'] == "finished":
            if self.is_playlist:
                self.last_downloaded = 0
                if self.downloaded_bytes == self.size:
                    self.__onDownloadComplete()
            else: 
                self.__onDownloadComplete()
        elif d['status'] == "downloading":
            with self.__resource_lock:
                self.progress = self.downloaded_bytes / self.size * 100
                self.__download_speed = d['speed']
                if self.is_playlist:
                    chunk_size = self.size * self.progress - self.last_downloaded
                    self.last_downloaded = self.size * self.progress
                    self.downloaded_bytes += chunk_size
                else:
                    self.download_speed_readable = d['_speed_str']
                    self.downloaded_bytes = d['downloaded_bytes']
        
    def __onDownloadStart(self):
        with download_dict_lock:
            download_dict[self.__listener.uid] = YoutubeDLDownloadStatus(self,self.__listener.uid)

    def __onDownloadComplete(self):
        self.__listener.onDownloadComplete()

    def __onDownloadError(self,error):
        self.__listener.onDownloadError(error)

    def extractMetaData(self,link):
        result = self.ydl.extract_info(link,download=False)
        if 'entries' in result:
            video = result['entries'][0]
            for v in result['entries']:
                self.size += int(v['filesize'])
            self.name = result.get('title')
            self.vid_id = video.get('id')
            self.is_playlist = True
            self.opts['outtmpl'] = f"{DOWNLOAD_DIR}{self.__listener.uid}/%(playlist)s/%(title)s.%(ext)s"
            self.ydl = YoutubeDL(self.opts)
        else:
            video = result
            self.size = int(video.get('filesize'))
            self.name = video.get('title')
            self.vid_id = video.get('id')
        return video

    def __download(self,link):
        try:
            self.ydl.download([link],)
        except ValueError:
            LOGGER.info("Download Cancelled by User!")
            self.__onDownloadError("Download Cancelled by User!")

    def add_download(self,link):
        LOGGER.info(f"Downloading with YT-DL: {link}")
        self.__gid = f"{self.vid_id}{self.__listener.uid}"
        threading.Thread(target=self.__download,args=(link,)).start()
        self.__onDownloadStart()

    def cancel_download(self):
        self.is_cancelled = True