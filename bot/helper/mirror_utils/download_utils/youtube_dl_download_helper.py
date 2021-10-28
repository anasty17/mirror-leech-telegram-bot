import random
import string
import time
import logging
import re
import threading

from .download_helper import DownloadHelper
from yt_dlp import YoutubeDL, DownloadError
from bot import download_dict_lock, download_dict
from ..status_utils.youtube_dl_download_status import YoutubeDLDownloadStatus

LOGGER = logging.getLogger(__name__)


class MyLogger:
    def __init__(self, obj):
        self.obj = obj

    def debug(self, msg):
        LOGGER.debug(msg)
        # Hack to fix changing changing extension
        match = re.search(r'.ffmpeg..Merging formats into..(.*?).$', msg)
        if match and not self.obj.is_playlist:
            newname = match.group(1)
            newname = newname.split("/")
            newname = newname[-1]
            self.obj.name = newname

    @staticmethod
    def warning(msg):
        LOGGER.warning(msg)

    @staticmethod
    def error(msg):
        LOGGER.error(msg)


class YoutubeDLHelper(DownloadHelper):
    def __init__(self, listener):
        super().__init__()
        self.name = ""
        self.__start_time = time.time()
        self.__listener = listener
        self.__gid = ""
        self.__download_speed = 0
        self.downloaded_bytes = 0
        self.size = 0
        self.is_playlist = False
        self.last_downloaded = 0
        self.is_cancelled = False
        self.__resource_lock = threading.RLock()
        self.opts = {'progress_hooks': [self.__onDownloadProgress],
                     'logger': MyLogger(self),
                     'usenetrc': True,
                     'continuedl': True,
                     'embedsubtitles': True,
                     'hls_prefer_native': False,
                     'prefer_ffmpeg': True,
                     'restrictfilenames': True}

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
                try:
                    tbyte = d['total_bytes']
                except KeyError:
                    tbyte = d['total_bytes_estimate']
                if self.is_playlist:
                    downloadedBytes = d['downloaded_bytes']
                    chunk_size = downloadedBytes - self.last_downloaded
                    self.last_downloaded = downloadedBytes
                    self.downloaded_bytes += chunk_size
                else:
                    self.size = tbyte
                    self.downloaded_bytes = d['downloaded_bytes']
                try:
                    self.progress = (self.downloaded_bytes / self.size) * 100
                except ZeroDivisionError:
                    pass

    def __onDownloadStart(self):
        with download_dict_lock:
            download_dict[self.__listener.uid] = YoutubeDLDownloadStatus(self, self.__listener)

    def __onDownloadComplete(self):
        self.__listener.onDownloadComplete()

    def onDownloadError(self, error):
        self.__listener.onDownloadError(error)

    def extractMetaData(self, link, name):
        with YoutubeDL(self.opts) as ydl:
            try:
                result = ydl.extract_info(link, download=False)
                self.name = ydl.prepare_filename(result)
            except DownloadError as e:
                self.onDownloadError(str(e))
                return
        if 'entries' in result:
            for v in result['entries']:
                try:
                    self.size += v['filesize_approx']
                except KeyError:
                    pass
            self.is_playlist = True
            if name != "":
                self.name = name
        elif name != "":
            ext = self.name.split('.')[-1]
            self.name = f"{name}.{ext}"

    def __download(self, link):
        try:
            with YoutubeDL(self.opts) as ydl:
                try:
                    ydl.download([link])
                except DownloadError as e:
                    if not self.is_playlist:
                        self.onDownloadError(str(e))
                        return
                    else:
                        pass
                self.__onDownloadComplete()
        except ValueError:
            self.onDownloadError("Download Cancelled by User!")

    def add_download(self, link, path, qual, name):
        if "hotstar" in link or "sonyliv" in link:
            self.opts['geo_bypass_country'] = 'IN'
        self.__onDownloadStart()
        self.__gid = ''.join(random.SystemRandom().choices(string.ascii_letters + string.digits, k=10))
        if qual == 'audio':
          self.opts['format'] = 'bestaudio/best'
          self.opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '340'}]
        else:
          self.opts['format'] = qual
        self.extractMetaData(link, name)
        LOGGER.info(f"Downloading with YT-DL: {link}")
        if not self.is_playlist:
            self.opts['outtmpl'] = f"{path}/{self.name}"
        else:
            self.opts['outtmpl'] = f"{path}/{self.name}/%(title)s.%(ext)s"
        self.__download(link)

    def cancel_download(self):
        self.is_cancelled = True
