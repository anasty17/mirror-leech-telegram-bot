from random import SystemRandom
from string import ascii_letters, digits
from logging import getLogger
from yt_dlp import YoutubeDL, DownloadError
from threading import RLock
from time import time
from re import search as re_search

from bot import download_dict_lock, download_dict
from bot.helper.telegram_helper.message_utils import sendStatusMessage
from ..status_utils.youtube_dl_download_status import YoutubeDLDownloadStatus

LOGGER = getLogger(__name__)


class MyLogger:
    def __init__(self, obj):
        self.obj = obj

    def debug(self, msg):
        # Hack to fix changing extension
        if not self.obj.is_playlist:
            match = re_search(r'.Merger..Merging formats into..(.*?).$', msg) # To mkv
            if not match:
                match = re_search(r'.ExtractAudio..Destination..(.*?)$', msg) # To mp3
            if match:
                LOGGER.info(msg)
                newname = match.group(1)
                newname = newname.rsplit("/", 1)[-1]
                self.obj.name = newname

    @staticmethod
    def warning(msg):
        LOGGER.warning(msg)

    @staticmethod
    def error(msg):
        if msg != "ERROR: Cancelling...":
            LOGGER.error(msg)


class YoutubeDLHelper:
    def __init__(self, listener):
        self.name = ""
        self.is_playlist = False
        self.size = 0
        self.progress = 0
        self.downloaded_bytes = 0
        self._last_downloaded = 0
        self.__download_speed = 0
        self.__start_time = time()
        self.__listener = listener
        self.__gid = ""
        self.__is_cancelled = False
        self.__downloading = False
        self.__resource_lock = RLock()
        self.opts = {'progress_hooks': [self.__onDownloadProgress],
                     'logger': MyLogger(self),
                     'usenetrc': True,
                     'prefer_ffmpeg': True,
                     'cookiefile': 'cookies.txt',
                     'allow_multiple_video_streams': True,
                     'allow_multiple_audio_streams': True,
                     'trim_file_name': 200,
                     'ffmpeg_location': '/bin/new-api'}

    @property
    def download_speed(self):
        with self.__resource_lock:
            return self.__download_speed

    def __onDownloadProgress(self, d):
        self.__downloading = True
        if self.__is_cancelled:
            raise ValueError("Cancelling...")
        if d['status'] == "finished":
            if self.is_playlist:
                self._last_downloaded = 0
        elif d['status'] == "downloading":
            with self.__resource_lock:
                self.__download_speed = d['speed']
                if self.is_playlist:
                    downloadedBytes = d['downloaded_bytes']
                    chunk_size = downloadedBytes - self._last_downloaded
                    self._last_downloaded = downloadedBytes
                    self.downloaded_bytes += chunk_size
                else:
                    if d.get('total_bytes'):
                        self.size = d['total_bytes']
                    elif d.get('total_bytes_estimate'):
                        self.size = d['total_bytes_estimate']
                    self.downloaded_bytes = d['downloaded_bytes']
                try:
                    self.progress = (self.downloaded_bytes / self.size) * 100
                except ZeroDivisionError:
                    pass

    def __onDownloadStart(self):
        with download_dict_lock:
            download_dict[self.__listener.uid] = YoutubeDLDownloadStatus(self, self.__listener, self.__gid)
        self.__listener.onDownloadStart()
        sendStatusMessage(self.__listener.message, self.__listener.bot)

    def __onDownloadComplete(self):
        self.__listener.onDownloadComplete()

    def __onDownloadError(self, error):
        self.__is_cancelled = True
        self.__listener.onDownloadError(error)

    def extractMetaData(self, link, name, args, get_info=False):
        if args is not None:
            self.__set_args(args)
        if get_info:
            self.opts['playlist_items'] = '0'
        with YoutubeDL(self.opts) as ydl:
            try:
                result = ydl.extract_info(link, download=False)
                if get_info:
                    return result
                elif result is None:
                    raise ValueError('Info result is None')
                realName = ydl.prepare_filename(result)
            except Exception as e:
                if get_info:
                    raise e
                return self.__onDownloadError(str(e))
        if 'entries' in result:
            for v in result['entries']:
                if 'filesize_approx' in v:
                    self.size += v['filesize_approx']
                elif 'filesize' in v:
                    self.size += v['filesize']
            if name == "":
                self.name = realName.split(f" [{result['id'].replace('*', '_')}]")[0]
            else:
                self.name = name
        else:
            ext = realName.split('.')[-1]
            if name == "":
                newname = realName.split(f" [{result['id'].replace('*', '_')}]")
                if len(newname) > 1:
                    self.name = newname[0] + '.' + ext
                else:
                    self.name = newname[0]
            else:
                self.name = f"{name}.{ext}"

    def __download(self, link):
        try:
            with YoutubeDL(self.opts) as ydl:
                try:
                    ydl.download([link])
                except DownloadError as e:
                    if not self.__is_cancelled:
                        self.__onDownloadError(str(e))
                    return
            if self.__is_cancelled:
                raise ValueError
            self.__onDownloadComplete()
        except ValueError:
            self.__onDownloadError("Download Stopped by User!")

    def add_download(self, link, path, name, qual, playlist, args):
        if playlist:
            self.opts['ignoreerrors'] = True
            self.is_playlist = True
        self.__gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=10))
        self.__onDownloadStart()
        if qual.startswith('ba/b'):
            audio_info = qual.split('-')
            qual = audio_info[0]
            if len(audio_info) == 2:
                rate = audio_info[1]
            else:
                rate = 320
            self.opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': f'{rate}'}]
        self.opts['format'] = qual
        LOGGER.info(f"Downloading with YT-DLP: {link}")
        self.extractMetaData(link, name, args)
        if self.__is_cancelled:
            return
        if not self.is_playlist:
            if args is None:
                self.opts['outtmpl'] = f"{path}/{self.name}"
            else:
                folder_name = self.name.rsplit('.', 1)[0]
                self.opts['outtmpl'] = f"{path}/{folder_name}/{self.name}"
                self.name = folder_name
        else:
            self.opts['outtmpl'] = f"{path}/{self.name}/%(title)s.%(ext)s"
        self.__download(link)

    def cancel_download(self):
        self.__is_cancelled = True
        LOGGER.info(f"Cancelling Download: {self.name}")
        if not self.__downloading:
            self.__onDownloadError("Download Cancelled by User!")

    def __set_args(self, args):
        args = args.split('|')
        for arg in args:
            xy = arg.split(':')
            if xy[1].startswith('^'):
                xy[1] = int(xy[1].split('^')[1])
            elif xy[1].lower() == 'true':
                xy[1] = True
            elif xy[1].lower() == 'false':
                xy[1] = False
            self.opts[xy[0]] = xy[1]
