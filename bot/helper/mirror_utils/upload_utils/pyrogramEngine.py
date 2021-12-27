import os
import logging
import time
import threading

from pyrogram.errors import FloodWait, RPCError
from PIL import Image

from bot import app, DOWNLOAD_DIR, AS_DOCUMENT, AS_DOC_USERS, AS_MEDIA_USERS, CUSTOM_FILENAME
from bot.helper.ext_utils.fs_utils import take_ss, get_media_info, get_video_resolution, get_path_size

LOGGER = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

VIDEO_SUFFIXES = ("MKV", "MP4", "MOV", "WMV", "3GP", "MPG", "WEBM", "AVI", "FLV", "M4V", "GIF")
AUDIO_SUFFIXES = ("MP3", "M4A", "M4B", "FLAC", "WAV", "AIF", "OGG", "AAC", "DTS", "MID", "AMR", "MKA")
IMAGE_SUFFIXES = ("JPG", "JPX", "PNG", "WEBP", "CR2", "TIF", "BMP", "JXR", "PSD", "ICO", "HEIC", "JPEG")


class TgUploader:

    def __init__(self, name=None, listener=None):
        self.__listener = listener
        self.name = name
        self.__app = app
        self.total_bytes = 0
        self.uploaded_bytes = 0
        self._last_uploaded = 0
        self.__start_time = time.time()
        self.__resource_lock = threading.RLock()
        self.__is_cancelled = False
        self.__chat_id = listener.message.chat.id
        self.__message_id = listener.uid
        self.__user_id = listener.message.from_user.id
        self.__as_doc = AS_DOCUMENT
        self.__thumb = f"Thumbnails/{self.__user_id}.jpg"
        self.__sent_msg = self.__app.get_messages(self.__chat_id, self.__message_id)
        self.__msgs_dict = {}
        self.__corrupted = 0
        self.__user_settings()

    def upload(self):
        path = f"{DOWNLOAD_DIR}{self.__message_id}"
        size = get_path_size(path)
        for dirpath, subdir, files in sorted(os.walk(path)):
            for filee in sorted(files):
                if self.__is_cancelled:
                    return
                if filee.endswith('.torrent'):
                    continue
                up_path = os.path.join(dirpath, filee)
                fsize = os.path.getsize(up_path)
                if fsize == 0:
                    LOGGER.error(f"{up_path} size is zero, telegram don't upload zero size files")
                    self.__corrupted += 1
                    continue
                self.__upload_file(up_path, filee, dirpath)
                if self.__is_cancelled:
                    return
                self.__msgs_dict[filee] = self.__sent_msg.message_id
                self._last_uploaded = 0
                time.sleep(1.5)
        if len(self.__msgs_dict) <= self.__corrupted:
            return self.__listener.onUploadError('Files Corrupted. Check logs')
        LOGGER.info(f"Leech Completed: {self.name}")
        self.__listener.onUploadComplete(self.name, size, self.__msgs_dict, None, self.__corrupted)

    def __upload_file(self, up_path, filee, dirpath):
        if CUSTOM_FILENAME is not None:
            cap_mono = f"{CUSTOM_FILENAME} <code>{filee}</code>"
            filee = f"{CUSTOM_FILENAME} {filee}"
            new_path = os.path.join(dirpath, filee)
            os.rename(up_path, new_path)
            up_path = new_path
        else:
            cap_mono = f"<code>{filee}</code>"
        notMedia = False
        thumb = self.__thumb
        try:
            if not self.__as_doc:
                duration = 0
                if filee.upper().endswith(VIDEO_SUFFIXES):
                    duration = get_media_info(up_path)[0]
                    if thumb is None:
                        thumb = take_ss(up_path)
                        if self.__is_cancelled:
                            if self.__thumb is None and thumb is not None and os.path.lexists(thumb):
                                os.remove(thumb)
                            return
                    if thumb is not None:
                        img = Image.open(thumb)
                        width, height = img.size
                    else:
                        width, height = get_video_resolution(up_path)
                    if not filee.upper().endswith(("MKV", "MP4")):
                        filee = os.path.splitext(filee)[0] + '.mp4'
                        new_path = os.path.join(dirpath, filee)
                        os.rename(up_path, new_path)
                        up_path = new_path
                    self.__sent_msg = self.__sent_msg.reply_video(video=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              parse_mode="html",
                                                              duration=duration,
                                                              width=width,
                                                              height=height,
                                                              thumb=thumb,
                                                              supports_streaming=True,
                                                              disable_notification=True,
                                                              progress=self.__upload_progress)
                elif filee.upper().endswith(AUDIO_SUFFIXES):
                    duration , artist, title = get_media_info(up_path)
                    self.__sent_msg = self.__sent_msg.reply_audio(audio=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              parse_mode="html",
                                                              duration=duration,
                                                              performer=artist,
                                                              title=title,
                                                              thumb=thumb,
                                                              disable_notification=True,
                                                              progress=self.__upload_progress)
                elif filee.upper().endswith(IMAGE_SUFFIXES):
                    self.__sent_msg = self.__sent_msg.reply_photo(photo=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              parse_mode="html",
                                                              disable_notification=True,
                                                              progress=self.__upload_progress)
                else:
                    notMedia = True
            if self.__as_doc or notMedia:
                if filee.upper().endswith(VIDEO_SUFFIXES) and thumb is None:
                    thumb = take_ss(up_path)
                    if self.__is_cancelled:
                        if self.__thumb is None and thumb is not None and os.path.lexists(thumb):
                            os.remove(thumb)
                        return
                self.__sent_msg = self.__sent_msg.reply_document(document=up_path,
                                                             quote=True,
                                                             thumb=thumb,
                                                             caption=cap_mono,
                                                             parse_mode="html",
                                                             disable_notification=True,
                                                             progress=self.__upload_progress)
        except FloodWait as f:
            LOGGER.warning(str(f))
            time.sleep(f.x * 1.5)
        except RPCError as e:
            LOGGER.error(f"RPCError: {e} File: {up_path}")
            self.__corrupted += 1
        except Exception as err:
            LOGGER.error(f"{err} File: {up_path}")
            self.__corrupted += 1
        if self.__thumb is None and thumb is not None and os.path.lexists(thumb):
            os.remove(thumb)
        if not self.__is_cancelled:
            os.remove(up_path)

    def __upload_progress(self, current, total):
        if self.__is_cancelled:
            self.__app.stop_transmission()
            return
        with self.__resource_lock:
            chunk_size = current - self._last_uploaded
            self._last_uploaded = current
            self.uploaded_bytes += chunk_size

    def __user_settings(self):
        if self.__user_id in AS_DOC_USERS:
            self.__as_doc = True
        elif self.__user_id in AS_MEDIA_USERS:
            self.__as_doc = False
        if not os.path.lexists(self.__thumb):
            self.__thumb = None

    def speed(self):
        try:
            return self.uploaded_bytes / (time.time() - self.__start_time)
        except ZeroDivisionError:
            return 0

    def cancel_download(self):
        self.__is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self.name}")
        self.__listener.onUploadError('your upload has been stopped!')
