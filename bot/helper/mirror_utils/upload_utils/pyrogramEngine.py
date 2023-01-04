from logging import getLogger, ERROR
from os import remove as osremove, walk, path as ospath, rename as osrename
from time import time, sleep
from pyrogram.types import InputMediaVideo, InputMediaDocument
from pyrogram.errors import FloodWait, RPCError
from PIL import Image
from threading import RLock
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, RetryError
from re import search as re_search

from bot import config_dict, user_data, GLOBAL_EXTENSION_FILTER, app
from bot.helper.ext_utils.fs_utils import take_ss, get_media_info, get_media_streams, clean_unwanted
from bot.helper.ext_utils.bot_utils import get_readable_file_size

LOGGER = getLogger(__name__)
getLogger("pyrogram").setLevel(ERROR)

IMAGE_SUFFIXES = ("JPG", "JPX", "PNG", "CR2", "TIF", "BMP", "JXR", "PSD", "ICO", "HEIC", "JPEG")


class TgUploader:

    def __init__(self, name=None, path=None, size=0, listener=None):
        self.name = name
        self.uploaded_bytes = 0
        self._last_uploaded = 0
        self.__listener = listener
        self.__path = path
        self.__start_time = time()
        self.__total_files = 0
        self.__is_cancelled = False
        self.__thumb = f"Thumbnails/{listener.message.from_user.id}.jpg"
        self.__msgs_dict = {}
        self.__corrupted = 0
        self.__resource_lock = RLock()
        self.__is_corrupted = False
        self.__size = size
        self.__media_dict = {'videos': {}, 'documents': {}}
        self.__last_msg_in_group = False
        self.__msg_to_reply()
        self.__user_settings()

    def upload(self, o_files, m_size):
        for dirpath, subdir, files in sorted(walk(self.__path)):
            for file_ in sorted(files, key=ospath.splitext):
                try:
                    if file_.lower().endswith(tuple(GLOBAL_EXTENSION_FILTER)):
                        continue
                    up_path = ospath.join(dirpath, file_)
                    f_size = ospath.getsize(up_path)
                    if self.__listener.seed and file_ in o_files and f_size in m_size:
                        continue
                    self.__total_files += 1
                    if f_size == 0:
                        LOGGER.error(f"{up_path} size is zero, telegram don't upload zero size files")
                        self.__corrupted += 1
                        continue
                    if self.__is_cancelled:
                        return
                    if self.__last_msg_in_group:
                        group_lists = [x for v in self.__media_dict.values() for x in v.keys()]
                        if (match := re_search(r'.+(?=\.0*\d+$)|.+(?=\.part\d+\..+)', up_path)) and match.group(0) not in group_lists:
                            for key, value in list(self.__media_dict.items()):
                                for subkey, msgs in list(value.items()):
                                    if len(msgs) > 1:
                                        self.__send_media_group(subkey, key, msgs)
                    self.__last_msg_in_group = False
                    up_path, cap_mono = self.__prepare_file(up_path, file_, dirpath)
                    self._last_uploaded = 0
                    self.__upload_file(up_path, cap_mono)
                    if self.__is_cancelled:
                        return
                    if not self.__listener.seed or self.__listener.newDir or dirpath.endswith("splited_files_mltb"):
                            osremove(up_path)
                    if not self.__is_corrupted and (not self.__listener.isPrivate or config_dict['DUMP_CHAT']):
                        self.__msgs_dict[self.__sent_msg.link] = file_
                    sleep(1)
                except Exception as err:
                    if isinstance(err, RetryError):
                        LOGGER.info(f"Total Attempts: {err.last_attempt.attempt_number}")
                    else:
                        LOGGER.error(f"{err}. Path: {up_path}")
                    continue
        for key, value in list(self.__media_dict.items()):
            for subkey, msgs in list(value.items()):
                if len(msgs) > 1:
                    self.__send_media_group(subkey, key, msgs)
        if self.__is_cancelled:
            return
        if self.__listener.seed and not self.__listener.newDir:
            clean_unwanted(self.__path)
        if self.__total_files == 0:
            self.__listener.onUploadError("No files to upload. In case you have filled EXTENSION_FILTER, then check if all files have those extensions or not.")
            return
        if self.__total_files <= self.__corrupted:
            self.__listener.onUploadError('Files Corrupted or unable to upload. Check logs!')
            return
        LOGGER.info(f"Leech Completed: {self.name}")
        size = get_readable_file_size(self.__size)
        self.__listener.onUploadComplete(None, size, self.__msgs_dict, self.__total_files, self.__corrupted, self.name)

    def __prepare_file(self, up_path, file_, dirpath):
        if LEECH_FILENAME_PREFIX := config_dict['LEECH_FILENAME_PREFIX']:
            cap_mono = f"{LEECH_FILENAME_PREFIX} <code>{file_}</code>"
            new_path = ospath.join(dirpath, f"{LEECH_FILENAME_PREFIX} {file_}")
            osrename(up_path, new_path)
            up_path = new_path
        else:
            cap_mono = f"<code>{file_}</code>"
        return up_path, cap_mono

    @retry(wait=wait_exponential(multiplier=2, min=4, max=8), stop=stop_after_attempt(3),
           retry=retry_if_exception_type(Exception))
    def __upload_file(self, up_path, cap_mono, force_document=False):
        if self.__thumb is not None and not ospath.lexists(self.__thumb):
            self.__thumb = None
        thumb = self.__thumb
        self.__is_corrupted = False
        try:
            is_video, is_audio, is_image = get_media_streams(up_path)
            is_image = is_image or up_path.upper().endswith(IMAGE_SUFFIXES)
            if self.__as_doc or force_document or (not is_video and not is_audio and not is_image):
                key = 'documents'
                if is_video and thumb is None:
                    thumb = take_ss(up_path, None)
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
            elif is_video:
                key = 'videos'
                duration = get_media_info(up_path)[0]
                if thumb is None:
                    thumb = take_ss(up_path, duration)
                    if self.__is_cancelled:
                        if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
                            osremove(thumb)
                        return
                if thumb is not None:
                    with Image.open(thumb) as img:
                        width, height = img.size
                else:
                    width = 480
                    height = 320
                if not up_path.upper().endswith(("MKV", "MP4")):
                    new_path = f"{up_path.rsplit('.', 1)[0]}.mp4"
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
            elif is_audio:
                key = 'audios'
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
            else:
                key = 'photos'
                self.__sent_msg = self.__sent_msg.reply_photo(photo=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              disable_notification=True,
                                                              progress=self.__upload_progress)
            if not self.__is_cancelled and self.__media_group and (self.__sent_msg.video or self.__sent_msg.document):
                key = 'documents' if self.__sent_msg.document else 'videos'
                if match := re_search(r'.+(?=\.0*\d+$)|.+(?=\.part\d+\..+)', up_path):
                    pname = match.group(0)
                    if pname in self.__media_dict[key].keys():
                        self.__media_dict[key][pname].append(self.__sent_msg)
                    else:
                        self.__media_dict[key][pname] = [self.__sent_msg]
                    msgs = self.__media_dict[key][pname]
                    if len(msgs) == 10:
                        self.__send_media_group(pname, key, msgs)
                    else:
                        self.__last_msg_in_group = True
        except FloodWait as f:
            LOGGER.warning(str(f))
            sleep(f.value)
        except Exception as err:
            err_type = "RPCError: " if isinstance(err, RPCError) else ""
            LOGGER.error(f"{err_type}{err}. Path: {up_path}")
            if 'Telegram says: [400' in str(err) and key != 'documents':
                LOGGER.error(f"Retrying As Document. Path: {up_path}")
                return self.__upload_file(up_path, cap_mono, True)
            raise err
        finally:
            if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
                osremove(thumb)

    def __upload_progress(self, current, total):
        if self.__is_cancelled:
            app.stop_transmission()
            return
        with self.__resource_lock:
            chunk_size = current - self._last_uploaded
            self._last_uploaded = current
            self.uploaded_bytes += chunk_size

    def __user_settings(self):
        user_id = self.__listener.message.from_user.id
        user_dict = user_data.get(user_id, {})
        self.__as_doc = user_dict.get('as_doc') or config_dict['AS_DOCUMENT']
        self.__media_group = user_dict.get('media_group') or config_dict['MEDIA_GROUP']
        if not ospath.lexists(self.__thumb):
            self.__thumb = None

    def __msg_to_reply(self):
        if DUMP_CHAT := config_dict['DUMP_CHAT']:
            if self.__listener.isPrivate:
                msg = self.__listener.message.text
            else:
                msg = self.__listener.message.link
            self.__sent_msg = app.send_message(DUMP_CHAT, msg, disable_web_page_preview=True)
        else:
            self.__sent_msg = app.get_messages(self.__listener.message.chat.id, self.__listener.uid)

    def __get_input_media(self, subkey, key):
        rlist = []
        for msg in self.__media_dict[key][subkey]:
            if key == 'videos':
                input_media = InputMediaVideo(media=msg.video.file_id, caption=msg.caption)
            else:
                input_media = InputMediaDocument(media=msg.document.file_id, caption=msg.caption)
            rlist.append(input_media)
        return rlist

    def __send_media_group(self, subkey, key, msgs):
        msgs_list = msgs[0].reply_to_message.reply_media_group(
                            media=self.__get_input_media(subkey, key),
                            quote=True,
                            disable_notification=True)
        for msg in msgs:
            if msg.link in self.__msgs_dict:
                del self.__msgs_dict[msg.link]
            msg.delete()
        del self.__media_dict[key][subkey]
        if not self.__listener.isPrivate or config_dict['DUMP_CHAT']:
            for m in msgs_list:
                self.__msgs_dict[m.link] = m.caption
        self.__sent_msg = msgs_list[-1]

    @property
    def speed(self):
        with self.__resource_lock:
            try:
                return self.uploaded_bytes / (time() - self.__start_time)
            except:
                return 0

    def cancel_download(self):
        self.__is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self.name}")
        self.__listener.onUploadError('your upload has been stopped!')
