from logging import getLogger, ERROR
from os import remove as osremove, walk, path as ospath, rename as osrename
from time import time, sleep
from pyrogram.errors import FloodWait, RPCError
from PIL import Image
from threading import RLock

from bot import app, DOWNLOAD_DIR, AS_DOCUMENT, AS_DOC_USERS, AS_MEDIA_USERS, CUSTOM_FILENAME, EXTENTION_FILTER
from bot.helper.ext_utils.fs_utils import take_ss, get_media_info, get_video_resolution, get_path_size
from bot.helper.ext_utils.bot_utils import get_readable_file_size

LOGGER = getLogger(__name__)
getLogger("pyrogram").setLevel(ERROR)

VIDEO_SUFFIXES = ("MKV", "MP4", "MOV", "WMV", "3GP", "MPG", "WEBM", "AVI", "FLV", "M4V", "GIF")
AUDIO_SUFFIXES = ("MP3", "M4A", "M4B", "FLAC", "WAV", "AIF", "OGG", "AAC", "DTS", "MID", "AMR", "MKA")
IMAGE_SUFFIXES = ("JPG", "JPX", "PNG", "WEBP", "CR2", "TIF", "BMP", "JXR", "PSD", "ICO", "HEIC", "JPEG")


class TgUploader:

    def __init__(self, name=None, listener=None):
        self.name = name
        self.uploaded_bytes = 0
        self._last_uploaded = 0
        self.__listener = listener
        self.__start_time = time()
        self.__total_files = 0
        self.__is_cancelled = False
        self.__as_doc = AS_DOCUMENT
        self.__thumb = f"Thumbnails/{listener.message.from_user.id}.jpg"
        self.__sent_msg = app.get_messages(self.__listener.message.chat.id, self.__listener.uid)
        self.__msgs_dict = {}
        self.__corrupted = 0
        self.__resource_lock = RLock()
        self.__user_settings()

    def upload(self):
        path = f"{DOWNLOAD_DIR}{self.__listener.uid}"
        size = get_readable_file_size(get_path_size(path))
        for dirpath, subdir, files in sorted(walk(path)):
            for file_ in sorted(files):
                if not file_.lower().endswith(tuple(EXTENTION_FILTER)):
                    self.__total_files += 1
                    up_path = ospath.join(dirpath, file_)
                    if ospath.getsize(up_path) == 0:
                        LOGGER.error(f"{up_path} size is zero, telegram don't upload zero size files")
                        self.__corrupted += 1
                        continue
                    self.__upload_file(up_path, file_, dirpath)
                    if self.__is_cancelled:
                        return
                    if not self.__listener.isPrivate:
                        self.__msgs_dict[file_] = self.__sent_msg.link
                    self._last_uploaded = 0
                    sleep(1)
        if self.__total_files <= self.__corrupted:
            return self.__listener.onUploadError('Files Corrupted. Check logs')
        LOGGER.info(f"Leech Completed: {self.name}")
        self.__listener.onUploadComplete(None, size, self.__msgs_dict, self.__total_files, self.__corrupted, self.name)

    def __upload_file(self, up_path, file_, dirpath):
        if CUSTOM_FILENAME is not None:
            cap_mono = f"{CUSTOM_FILENAME} <code>{file_}</code>"
            file_ = f"{CUSTOM_FILENAME} {file_}"
            new_path = ospath.join(dirpath, file_)
            osrename(up_path, new_path)
            up_path = new_path
        else:
            cap_mono = f"<code>{file_}</code>"
        notMedia = False
        thumb = self.__thumb
        try:
            if not self.__as_doc:
                duration = 0
                if file_.upper().endswith(VIDEO_SUFFIXES):
                    duration = get_media_info(up_path)[0]
                    if thumb is None:
                        thumb = take_ss(up_path)
                        if self.__is_cancelled:
                            if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
                                osremove(thumb)
                            return
                    if thumb is not None:
                        img = Image.open(thumb)
                        width, height = img.size
                    else:
                        width, height = get_video_resolution(up_path)
                    if not file_.upper().endswith(("MKV", "MP4")):
                        file_ = ospath.splitext(file_)[0] + '.mp4'
                        new_path = ospath.join(dirpath, file_)
                        osrename(up_path, new_path)
                        up_path = new_path
                    self.__sent_msg = self.__sent_msg.reply_video(video=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              duration=duration,
                                                              width=width,
                                                              height=height,
                                                              thumb=thumb,
                                                              supports_streaming=True,
                                                              disable_notification=True,
                                                              progress=self.__upload_progress)
                elif file_.upper().endswith(AUDIO_SUFFIXES):
                    duration , artist, title = get_media_info(up_path)
                    self.__sent_msg = self.__sent_msg.reply_audio(audio=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              duration=duration,
                                                              performer=artist,
                                                              title=title,
                                                              thumb=thumb,
                                                              disable_notification=True,
                                                              progress=self.__upload_progress)
                elif file_.upper().endswith(IMAGE_SUFFIXES):
                    self.__sent_msg = self.__sent_msg.reply_photo(photo=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              disable_notification=True,
                                                              progress=self.__upload_progress)
                else:
                    notMedia = True
            if self.__as_doc or notMedia:
                if file_.upper().endswith(VIDEO_SUFFIXES) and thumb is None:
                    thumb = take_ss(up_path)
                    if self.__is_cancelled:
                        if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
                            osremove(thumb)
                        return
                self.__sent_msg = self.__sent_msg.reply_document(document=up_path,
                                                             quote=True,
                                                             thumb=thumb,
                                                             caption=cap_mono,
                                                             disable_notification=True,
                                                             progress=self.__upload_progress)
        except FloodWait as f:
            LOGGER.warning(str(f))
            sleep(f.value)
        except RPCError as e:
            LOGGER.error(f"RPCError: {e} File: {up_path}")
            self.__corrupted += 1
        except Exception as err:
            LOGGER.error(f"{err} File: {up_path}")
            self.__corrupted += 1
        if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
            osremove(thumb)
        if not self.__is_cancelled:
            osremove(up_path)

    def __upload_progress(self, current, total):
        if self.__is_cancelled:
            self.__listener.onUploadError('your upload has been stopped!')
            app.stop_transmission()
            return
        with self.__resource_lock:
            chunk_size = current - self._last_uploaded
            self._last_uploaded = current
            self.uploaded_bytes += chunk_size

    def __user_settings(self):
        if self.__listener.message.from_user.id in AS_DOC_USERS:
            self.__as_doc = True
        elif self.__listener.message.from_user.id in AS_MEDIA_USERS:
            self.__as_doc = False
        if not ospath.lexists(self.__thumb):
            self.__thumb = None

    @property
    def speed(self):
        with self.__resource_lock:
            try:
                return self.uploaded_bytes / (time() - self.__start_time)
            except ZeroDivisionError:
                return 0

    def cancel_download(self):
        self.__is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self.name}")
