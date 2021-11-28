import os
import logging
import time
import threading

from pyrogram.errors import FloodWait, RPCError

from bot import app, DOWNLOAD_DIR, AS_DOCUMENT, AS_DOC_USERS, AS_MEDIA_USERS, CUSTOM_FILENAME
from bot.helper.ext_utils.fs_utils import take_ss, get_media_info

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
        self.last_uploaded = 0
        self.start_time = time.time()
        self.__resource_lock = threading.RLock()
        self.is_cancelled = False
        self.chat_id = listener.message.chat.id
        self.message_id = listener.uid
        self.user_id = listener.message.from_user.id
        self.as_doc = AS_DOCUMENT
        self.thumb = f"Thumbnails/{self.user_id}.jpg"
        self.sent_msg = self.__app.get_messages(self.chat_id, self.message_id)
        self.msgs_dict = {}
        self.corrupted = 0

    def upload(self):
        path = f"{DOWNLOAD_DIR}{self.message_id}"
        self.user_settings()
        for dirpath, subdir, files in sorted(os.walk(path)):
            for filee in sorted(files):
                if self.is_cancelled:
                    return
                if filee.endswith('.torrent'):
                    continue
                up_path = os.path.join(dirpath, filee)
                fsize = os.path.getsize(up_path)
                if fsize == 0:
                    self.corrupted += 1
                    continue
                self.upload_file(up_path, filee, dirpath)
                if self.is_cancelled:
                    return
                self.msgs_dict[filee] = self.sent_msg.message_id
                self.last_uploaded = 0
                time.sleep(1.5)
        LOGGER.info(f"Leech Done: {self.name}")
        self.__listener.onUploadComplete(self.name, None, self.msgs_dict, None, self.corrupted)

    def upload_file(self, up_path, filee, dirpath):
        if CUSTOM_FILENAME is not None:
            cap_mono = f"{CUSTOM_FILENAME} <code>{filee}</code>"
            filee = f"{CUSTOM_FILENAME} {filee}"
            new_path = os.path.join(dirpath, filee)
            os.rename(up_path, new_path)
            up_path = new_path
        else:
            cap_mono = f"<code>{filee}</code>"
        notMedia = False
        thumb = self.thumb
        try:
            if not self.as_doc:
                duration = 0
                if filee.upper().endswith(VIDEO_SUFFIXES):
                    duration = get_media_info(up_path)[0]
                    if thumb is None:
                        thumb = take_ss(up_path)
                        if self.is_cancelled:
                            if self.thumb is None and thumb is not None and os.path.lexists(thumb):
                                os.remove(thumb)
                            return
                    if not filee.upper().endswith(("MKV", "MP4")):
                        filee = os.path.splitext(filee)[0] + '.mp4'
                        new_path = os.path.join(dirpath, filee)
                        os.rename(up_path, new_path)
                        up_path = new_path
                    self.sent_msg = self.sent_msg.reply_video(video=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              parse_mode="html",
                                                              duration=duration,
                                                              width=480,
                                                              height=320,
                                                              thumb=thumb,
                                                              supports_streaming=True,
                                                              disable_notification=True,
                                                              progress=self.upload_progress)
                elif filee.upper().endswith(AUDIO_SUFFIXES):
                    duration , artist, title = get_media_info(up_path)
                    self.sent_msg = self.sent_msg.reply_audio(audio=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              parse_mode="html",
                                                              duration=duration,
                                                              performer=artist,
                                                              title=title,
                                                              thumb=thumb,
                                                              disable_notification=True,
                                                              progress=self.upload_progress)
                elif filee.upper().endswith(IMAGE_SUFFIXES):
                    self.sent_msg = self.sent_msg.reply_photo(photo=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              parse_mode="html",
                                                              disable_notification=True,
                                                              progress=self.upload_progress)
                else:
                    notMedia = True
            if self.as_doc or notMedia:
                if filee.upper().endswith(VIDEO_SUFFIXES) and thumb is None:
                    thumb = take_ss(up_path)
                    if self.is_cancelled:
                        if self.thumb is None and thumb is not None and os.path.lexists(thumb):
                            os.remove(thumb)
                        return
                self.sent_msg = self.sent_msg.reply_document(document=up_path,
                                                             quote=True,
                                                             thumb=thumb,
                                                             caption=cap_mono,
                                                             parse_mode="html",
                                                             disable_notification=True,
                                                             progress=self.upload_progress)
        except FloodWait as f:
            LOGGER.info(f)
            time.sleep(f.x)
        except RPCError as e:
            LOGGER.error(str(e))
            self.is_cancelled = True
            self.__listener.onUploadError(str(e))
        if self.thumb is None and thumb is not None and os.path.lexists(thumb):
            os.remove(thumb)
        if not self.is_cancelled:
            os.remove(up_path)

    def upload_progress(self, current, total):
        if self.is_cancelled:
            self.__app.stop_transmission()
            return
        with self.__resource_lock:
            chunk_size = current - self.last_uploaded
            self.last_uploaded = current
            self.uploaded_bytes += chunk_size

    def user_settings(self):
        if self.user_id in AS_DOC_USERS:
            self.as_doc = True
        elif self.user_id in AS_MEDIA_USERS:
            self.as_doc = False
        if not os.path.lexists(self.thumb):
            self.thumb = None

    def speed(self):
        try:
            return self.uploaded_bytes / (time.time() - self.start_time)
        except ZeroDivisionError:
            return 0

    def cancel_download(self):
        self.is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self.name}")
        self.__listener.onUploadError('your upload has been stopped!')
