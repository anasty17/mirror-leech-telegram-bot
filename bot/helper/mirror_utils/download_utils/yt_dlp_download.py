#!/usr/bin/env python3
from os import path as ospath, listdir
from random import SystemRandom
from string import ascii_letters, digits
from logging import getLogger
from yt_dlp import YoutubeDL, DownloadError
from re import search as re_search

from bot import download_dict_lock, download_dict, non_queued_dl, queue_dict_lock
from bot.helper.telegram_helper.message_utils import sendStatusMessage
from ..status_utils.yt_dlp_download_status import YtDlpDownloadStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.ext_utils.bot_utils import sync_to_async, async_to_sync
from bot.helper.ext_utils.task_manager import is_queued, stop_duplicate_check

LOGGER = getLogger(__name__)


class MyLogger:
    def __init__(self, obj):
        self.obj = obj

    def debug(self, msg):
        # Hack to fix changing extension
        if not self.obj.is_playlist:
            if match := re_search(r'.Merger..Merging formats into..(.*?).$', msg) or \
                    re_search(r'.ExtractAudio..Destination..(.*?)$', msg):
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
        self.__last_downloaded = 0
        self.__size = 0
        self.__progress = 0
        self.__downloaded_bytes = 0
        self.__download_speed = 0
        self.__eta = '-'
        self.__listener = listener
        self.__gid = ''
        self.__is_cancelled = False
        self.__downloading = False
        self.__ext = ''
        self.name = ''
        self.is_playlist = False
        self.opts = {'progress_hooks': [self.__onDownloadProgress],
                     'logger': MyLogger(self),
                     'usenetrc': True,
                     'cookiefile': 'cookies.txt',
                     'allow_multiple_video_streams': True,
                     'allow_multiple_audio_streams': True,
                     'noprogress': True,
                     'allow_playlist_files': True,
                     'overwrites': True,
                     'writethumbnail': True,
                     'trim_file_name': 220,
                     'retry_sleep_functions': {'http': lambda x: 2,
                                               'fragment': lambda x: 2,
                                               'file_access': lambda x: 2,
                                               'extractor': lambda x: 2}}

    @property
    def download_speed(self):
        return self.__download_speed

    @property
    def downloaded_bytes(self):
        return self.__downloaded_bytes

    @property
    def size(self):
        return self.__size

    @property
    def progress(self):
        return self.__progress

    @property
    def eta(self):
        return self.__eta

    def __onDownloadProgress(self, d):
        self.__downloading = True
        if self.__is_cancelled:
            raise ValueError("Cancelling...")
        if d['status'] == "finished":
            if self.is_playlist:
                self.__last_downloaded = 0
        elif d['status'] == "downloading":
            self.__download_speed = d['speed']
            if self.is_playlist:
                downloadedBytes = d['downloaded_bytes']
                chunk_size = downloadedBytes - self.__last_downloaded
                self.__last_downloaded = downloadedBytes
                self.__downloaded_bytes += chunk_size
            else:
                if d.get('total_bytes'):
                    self.__size = d['total_bytes']
                elif d.get('total_bytes_estimate'):
                    self.__size = d['total_bytes_estimate']
                self.__downloaded_bytes = d['downloaded_bytes']
                self.__eta = d.get('eta', '-') or '-'
            try:
                self.__progress = (self.__downloaded_bytes / self.__size) * 100
            except:
                pass

    async def __onDownloadStart(self, from_queue=False):
        async with download_dict_lock:
            download_dict[self.__listener.uid] = YtDlpDownloadStatus(
                self, self.__listener, self.__gid)
        if not from_queue:
            await self.__listener.onDownloadStart()
            await sendStatusMessage(self.__listener.message)

    def __onDownloadError(self, error):
        self.__is_cancelled = True
        async_to_sync(self.__listener.onDownloadError, error)

    def extractMetaData(self, link, name):
        if link.startswith(('rtmp', 'mms', 'rstp', 'rtmps')):
            self.opts['external_downloader'] = 'ffmpeg'
        with YoutubeDL(self.opts) as ydl:
            try:
                result = ydl.extract_info(link, download=False)
                if result is None:
                    raise ValueError('Info result is None')
            except Exception as e:
                return self.__onDownloadError(str(e))
            if 'entries' in result:
                self.name = name
                for entry in result['entries']:
                    if not entry:
                        continue
                    elif 'filesize_approx' in entry:
                        self.__size += entry['filesize_approx']
                    elif 'filesize' in entry:
                        self.__size += entry['filesize']
                    if not name:
                        outtmpl_ = '%(series,playlist_title,channel)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d.%(ext)s'
                        name, ext = ospath.splitext(
                            ydl.prepare_filename(entry, outtmpl=outtmpl_))
                        self.name = name
                        if not self.__ext:
                            self.__ext = ext
            else:
                outtmpl_ = '%(title,fulltitle,alt_title)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d%(episode_number&E|)s%(episode_number|)02d%(height& |)s%(height|)s%(height&p|)s%(fps|)s%(fps&fps|)s%(tbr& |)s%(tbr|)d.%(ext)s'
                realName = ydl.prepare_filename(result, outtmpl=outtmpl_)
                ext = ospath.splitext(realName)[-1]
                self.name = f"{name}{ext}" if name else realName
                if not self.__ext:
                    self.__ext = ext

    def __download(self, link, path):
        try:
            with YoutubeDL(self.opts) as ydl:
                try:
                    ydl.download([link])
                except DownloadError as e:
                    if not self.__is_cancelled:
                        self.__onDownloadError(str(e))
                    return
            if self.is_playlist and (not ospath.exists(path) or len(listdir(path)) == 0):
                self.__onDownloadError(
                    "No video available to download from this playlist. Check logs for more details")
                return
            if self.__is_cancelled:
                raise ValueError
            async_to_sync(self.__listener.onDownloadComplete)
        except ValueError:
            self.__onDownloadError("Download Stopped by User!")

    async def add_download(self, link, path, name, qual, playlist, options):
        if playlist:
            self.opts['ignoreerrors'] = True
            self.is_playlist = True

        self.__gid = ''.join(SystemRandom().choices(
            ascii_letters + digits, k=10))

        await self.__onDownloadStart()

        self.opts['postprocessors'] = [
            {'add_chapters': True, 'add_infojson': 'if_exists', 'add_metadata': True, 'key': 'FFmpegMetadata'}]

        if qual.startswith('ba/b-'):
            audio_info = qual.split('-')
            qual = audio_info[0]
            audio_format = audio_info[1]
            rate = audio_info[2]
            self.opts['postprocessors'].append(
                {'key': 'FFmpegExtractAudio', 'preferredcodec': audio_format, 'preferredquality': rate})
            if audio_format == 'vorbis':
                self.__ext = '.ogg'
            elif audio_format == 'alac':
                self.__ext = '.m4a'
            else:
                self.__ext = f'.{audio_format}'

        self.opts['format'] = qual

        if options:
            self.__set_options(options)

        await sync_to_async(self.extractMetaData, link, name)
        if self.__is_cancelled:
            return

        base_name, ext = ospath.splitext(self.name)
        trim_name = self.name if self.is_playlist else base_name
        if len(trim_name.encode()) > 200:
            self.name = self.name[:
                                  200] if self.is_playlist else f'{base_name[:200]}{ext}'
            base_name = ospath.splitext(self.name)[0]

        if self.is_playlist:
            self.opts['outtmpl'] = {'default': f"{path}/{self.name}/%(title,fulltitle,alt_title)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d%(episode_number&E|)s%(episode_number|)02d%(height& |)s%(height|)s%(height&p|)s%(fps|)s%(fps&fps|)s%(tbr& |)s%(tbr|)d.%(ext)s",
                                    'thumbnail': f"{path}/yt-dlp-thumb/%(title,fulltitle,alt_title)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d%(episode_number&E|)s%(episode_number|)02d%(height& |)s%(height|)s%(height&p|)s%(fps|)s%(fps&fps|)s%(tbr& |)s%(tbr|)d.%(ext)s"}
        elif any(key in options for key in ['writedescription', 'writeinfojson', 'writeannotations', 'writedesktoplink', 'writewebloclink', 'writeurllink', 'writesubtitles', 'writeautomaticsub']):
            self.opts['outtmpl'] = {'default': f"{path}/{base_name}/{self.name}",
                                    'thumbnail': f"{path}/yt-dlp-thumb/{base_name}.%(ext)s"}
        else:
            self.opts['outtmpl'] = {'default': f"{path}/{self.name}",
                                    'thumbnail': f"{path}/yt-dlp-thumb/{base_name}.%(ext)s"}
            self.name = base_name

        if self.__listener.isLeech:
            self.opts['postprocessors'].append(
                {'format': 'jpg', 'key': 'FFmpegThumbnailsConvertor', 'when': 'before_dl'})
        if self.__ext in ['.mp3', '.mkv', '.mka', '.ogg', '.opus', '.flac', '.m4a', '.mp4', '.mov']:
            self.opts['postprocessors'].append(
                {'already_have_thumbnail': self.__listener.isLeech, 'key': 'EmbedThumbnail'})
        elif not self.__listener.isLeech:
            self.opts['writethumbnail'] = False

        msg, button = await stop_duplicate_check(name, self.__listener)
        if msg:
            await self.__listener.onDownloadError(msg, button)
            return

        added_to_queue, event = await is_queued(self.__listener.uid)
        if added_to_queue:
            LOGGER.info(f"Added to Queue/Download: {self.name}")
            async with download_dict_lock:
                download_dict[self.__listener.uid] = QueueStatus(
                    self.name, self.__size, self.__gid, self.__listener, 'dl')
            await event.wait()
            async with download_dict_lock:
                if self.__listener.uid not in download_dict:
                    return
            LOGGER.info(f'Start Queued Download from YT_DLP: {self.name}')
            await self.__onDownloadStart(True)
        else:
            LOGGER.info(f'Download with YT_DLP: {self.name}')

        async with queue_dict_lock:
            non_queued_dl.add(self.__listener.uid)

        await sync_to_async(self.__download, link, path)

    async def cancel_download(self):
        self.__is_cancelled = True
        LOGGER.info(f"Cancelling Download: {self.name}")
        if not self.__downloading:
            await self.__listener.onDownloadError("Download Cancelled by User!")

    def __set_options(self, options):
        options = options.split('|')
        for opt in options:
            key, value = map(str.strip, opt.split(':', 1))
            if value.startswith('^'):
                if '.' in value or value == '^inf':
                    value = float(value.split('^')[1])
                else:
                    value = int(value.split('^')[1])
            elif value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            elif value.startswith(('{', '[', '(')) and value.endswith(('}', ']', ')')):
                value = eval(value)

            if key == 'postprocessors':
                if isinstance(value, list):
                    self.opts[key].extend(tuple(value))
                elif isinstance(value, dict):
                    self.opts[key].append(value)
            else:
                self.opts[key] = value
