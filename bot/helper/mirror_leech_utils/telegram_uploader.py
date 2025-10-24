from PIL import Image
from aioshutil import rmtree
from asyncio import sleep, Event
from logging import getLogger
from natsort import natsorted
from os import walk, path as ospath
from time import time
from re import match as re_match, sub as re_sub
from aiofiles.os import (
    remove,
    path as aiopath,
    rename,
)
from pytdbot.types import (
    ChatTypePrivate,
    InputMessageVideo,
    InputMessageAudio,
    InputMessageDocument,
    InputMessagePhoto,
    InputFileRemote,
    InputFileLocal,
    InputThumbnail,
)

from ...core.config_manager import Config
from ...core.telegram_client import TgManager
from ..ext_utils.bot_utils import sync_to_async
from ..ext_utils.files_utils import is_archive, get_base_name
from ..telegram_helper.progress import tracker
from ..ext_utils.exceptions import TgUploadException
from ..ext_utils.media_utils import (
    get_media_info,
    get_document_type,
    get_video_thumbnail,
    get_audio_thumbnail,
    get_multiple_frames_thumbnail,
)
from ..telegram_helper.message_utils import (
    delete_message,
    send_album,
    send_message_with_content,
)

LOGGER = getLogger(__name__)


class TelegramUploader:
    def __init__(self, listener, path):
        self._last_uploaded = 0
        self._processed_bytes = 0
        self._listener = listener
        self._path = path
        self._start_time = time()
        self._total_files = 0
        self._thumb = self._listener.thumb or f"thumbnails/{listener.user_id}.jpg"
        self._msgs_dict = {}
        self._corrupted = 0
        self._is_corrupted = False
        self._media_dict = {"videos": {}, "documents": {}}
        self._last_msg_in_group = False
        self._up_path = ""
        self._lprefix = ""
        self._media_group = False
        self._is_private = False
        self._sent_msg = None
        self._user_session = self._listener.user_transmission
        self._error = ""
        self._f_size = 0
        self._event = Event()
        self._temp_message = None

    async def _upload_progress(self, key, progress_dict, is_completed):
        if is_completed:
            self._event.set()
        if self._listener.is_cancelled:
            if self._temp_message is not None:
                await self._temp_message.delete()
            await tracker.cancel_progress(key)
            self._event.set()
        chunk_size = progress_dict["transferred"] - self._last_uploaded
        self._last_uploaded = progress_dict["transferred"]
        self._processed_bytes += chunk_size

    async def _user_settings(self):
        self._media_group = self._listener.user_dict.get("MEDIA_GROUP") or (
            Config.MEDIA_GROUP
            if "MEDIA_GROUP" not in self._listener.user_dict
            else False
        )
        self._lprefix = self._listener.user_dict.get("LEECH_FILENAME_PREFIX") or (
            Config.LEECH_FILENAME_PREFIX
            if "LEECH_FILENAME_PREFIX" not in self._listener.user_dict
            else ""
        )
        if self._thumb != "none" and not await aiopath.exists(self._thumb):
            self._thumb = None

    async def _msg_to_reply(self):
        if self._listener.up_dest:
            msg = (
                self._listener.message_link
                if self._listener.is_super_chat
                else self._listener.message.text.lstrip("/")
            )
            if self._user_session:
                self._sent_msg = await TgManager.user.sendTextMessage(
                    chat_id=self._listener.up_dest,
                    text=msg,
                    disable_web_page_preview=True,
                    message_thread_id=self._listener.chat_thread_id,
                    disable_notification=True,
                )
            else:
                self._sent_msg = await self._listener.client.sendTextMessage(
                    chat_id=self._listener.up_dest,
                    text=msg,
                    disable_web_page_preview=True,
                    message_thread_id=self._listener.chat_thread_id,
                    disable_notification=True,
                )
                if not self._sent_msg.is_error:
                    dest_chat = await self._sent_msg.getChat()
                    self._is_private = isinstance(dest_chat.type, ChatTypePrivate)
            if self._sent_msg.is_error:
                await self._listener.on_upload_error(self._sent_msg["message"])
                return False
        elif self._user_session:
            self._sent_msg = await TgManager.user.getMessage(
                chat_id=self._listener.message.chat_id, message_id=self._listener.mid
            )
            if self._sent_msg.is_error:
                self._sent_msg = await TgManager.user.sendTextMessage(
                    chat_id=self._listener.message.chat_id,
                    text="Deleted Cmd Message! Don't delete the cmd message again!",
                    disable_web_page_preview=True,
                    disable_notification=True,
                )
        else:
            self._sent_msg = self._listener.message
        return True

    async def _prepare_file(self, file_, dirpath):
        if self._lprefix:
            cap_mono = f"{self._lprefix} <code>{file_}</code>"
            self._lprefix = re_sub("<.*?>", "", self._lprefix)
            new_path = ospath.join(dirpath, f"{self._lprefix} {file_}")
            await rename(self._up_path, new_path)
            self._up_path = new_path
        else:
            cap_mono = f"<code>{file_}</code>"
        if len(file_) > 60:
            if is_archive(file_):
                name = get_base_name(file_)
                ext = file_.split(name, 1)[1]
            elif match := re_match(r".+(?=\..+\.0*\d+$)|.+(?=\.part\d+\..+$)", file_):
                name = match.group(0)
                ext = file_.split(name, 1)[1]
            elif len(fsplit := ospath.splitext(file_)) > 1:
                name = fsplit[0]
                ext = fsplit[1]
            else:
                name = file_
                ext = ""
            extn = len(ext)
            remain = 60 - extn
            name = name[:remain]
            new_path = ospath.join(dirpath, f"{name}{ext}")
            await rename(self._up_path, new_path)
            self._up_path = new_path
        return cap_mono

    def _get_input_media(self, subkey, key):
        rlist = []
        for msg in self._media_dict[key][subkey]:
            if key == "videos":
                input_media = InputMessageVideo(
                    video=InputFileRemote(id=msg.remote_file_id),
                    supports_streaming=True,
                    caption=msg.caption,
                )
            else:
                input_media = InputMessageDocument(
                    document=InputFileRemote(id=msg.remote_file_id),
                    caption=msg.caption,
                )
            rlist.append(input_media)
        return rlist

    async def _send_screenshots(self, dirpath, outputs):
        inputs = [
            InputMessagePhoto(
                photo=InputFileLocal(path=ospath.join(dirpath, p)),
                caption=p.rsplit("/", 1)[-1],
            )
            for p in outputs
        ]
        for i in range(0, len(inputs), 10):
            batch = inputs[i : i + 10]
            self._sent_msg = (await send_album(self._sent_msg, batch)).messages[-1]

    async def _send_media_group(self, subkey, key, msgs):
        for index, msg in enumerate(msgs):
            if self._listener.hybrid_leech or not self._user_session:
                msgs[index] = await self._listener.client.getMessage(
                    chat_id=msg[0], message_id=msg[1]
                )
            else:
                msgs[index] = await TgManager.user.getMessage(
                    chat_id=msg[0], message_id=msg[1]
                )
        replied_to = await msgs[0].getRepliedMessage()
        msgs_list = (
            await send_album(replied_to, self._get_input_media(subkey, key))
        ).messages
        for msg in msgs:
            msg_link = await msg.getMessageLink(in_message_thread=bool(msg.topic_id))
            link = msg_link.link
            if link in self._msgs_dict:
                del self._msgs_dict[link]
            await delete_message(msg)
        del self._media_dict[key][subkey]
        if self._listener.is_super_chat or self._listener.up_dest:
            for m in msgs_list:
                msg_link = await m.getMessageLink(in_message_thread=bool(msg.topic_id))
                link = msg_link.link
                self._msgs_dict[link] = m.caption
        self._sent_msg = msgs_list[-1]

    async def upload(self):
        await self._user_settings()
        res = await self._msg_to_reply()
        if not res:
            return
        for dirpath, _, files in natsorted(await sync_to_async(walk, self._path)):
            if dirpath.strip().endswith("/yt-dlp-thumb"):
                continue
            if dirpath.strip().endswith("_mltbss"):
                await self._send_screenshots(dirpath, files)
                await rmtree(dirpath, ignore_errors=True)
                continue
            for file_ in natsorted(files):
                self._error = ""
                self._up_path = f_path = ospath.join(dirpath, file_)
                if not await aiopath.exists(self._up_path):
                    LOGGER.error(f"{self._up_path} not exists! Continue uploading!")
                    continue
                try:
                    self._f_size = await aiopath.getsize(self._up_path)
                    self._total_files += 1
                    if self._f_size == 0:
                        LOGGER.error(
                            f"{self._up_path} size is zero, telegram don't upload zero size files"
                        )
                        self._corrupted += 1
                        continue
                    if self._listener.is_cancelled:
                        return
                    cap_mono = await self._prepare_file(file_, dirpath)
                    if self._last_msg_in_group:
                        group_lists = [
                            x for v in self._media_dict.values() for x in v.keys()
                        ]
                        match = re_match(r".+(?=\.0*\d+$)|.+(?=\.part\d+\..+$)", f_path)
                        if not match or match and match.group(0) not in group_lists:
                            for key, value in list(self._media_dict.items()):
                                for subkey, msgs in list(value.items()):
                                    if len(msgs) > 1:
                                        await self._send_media_group(subkey, key, msgs)
                    if self._listener.hybrid_leech and self._listener.user_transmission:
                        self._user_session = self._f_size > 2097152000
                        if self._user_session:
                            self._sent_msg = await TgManager.user.getMessage(
                                chat_id=self._sent_msg.chat_id,
                                message_id=self._sent_msg.id,
                            )
                        else:
                            self._sent_msg = await self._listener.client.getMessage(
                                chat_id=self._sent_msg.chat_id,
                                message_id=self._sent_msg.id,
                            )
                    self._last_msg_in_group = False
                    self._last_uploaded = 0
                    await self._upload_file(cap_mono, file_, f_path)
                    if self._listener.is_cancelled:
                        return
                    if (
                        not self._is_corrupted
                        and (self._listener.is_super_chat or self._listener.up_dest)
                        and not self._is_private
                    ):
                        msg_link = await self._sent_msg.getMessageLink(
                            in_message_thread=bool(self._sent_msg.topic_id)
                        )
                        link = msg_link.link
                        self._msgs_dict[link] = file_
                    await sleep(1)
                except Exception as err:
                    LOGGER.error(f"{err}. Path: {self._up_path}")
                    self._error = str(err)
                    self._corrupted += 1
                    if self._listener.is_cancelled:
                        return
                if not self._listener.is_cancelled and await aiopath.exists(
                    self._up_path
                ):
                    await remove(self._up_path)
        for key, value in list(self._media_dict.items()):
            for subkey, msgs in list(value.items()):
                if len(msgs) > 1:
                    try:
                        await self._send_media_group(subkey, key, msgs)
                    except Exception as e:
                        LOGGER.info(
                            f"While sending media group at the end of task. Error: {e}"
                        )
        if self._listener.is_cancelled:
            return
        if self._total_files == 0:
            await self._listener.on_upload_error(
                "No files to upload. In case you have filled EXCLUDED_EXTENSIONS, then check if all files have those extensions or not."
            )
            return
        if self._total_files <= self._corrupted:
            await self._listener.on_upload_error(
                f"Files Corrupted or unable to upload. {self._error or 'Check logs!'}"
            )
            return
        LOGGER.info(f"Leech Completed: {self._listener.name}")
        await self._listener.on_upload_complete(
            None, self._msgs_dict, self._total_files, self._corrupted
        )
        return

    async def _upload_file(self, cap_mono, file, o_path, force_document=False):
        if (
            self._thumb is not None
            and not await aiopath.exists(self._thumb)
            and self._thumb != "none"
        ):
            self._thumb = None
        thumb = self._thumb
        self._is_corrupted = False
        try:
            is_video, is_audio, is_image = await get_document_type(self._up_path)

            if not is_image and thumb is None:
                file_name = ospath.splitext(file)[0]
                thumb_path = f"{self._path}/yt-dlp-thumb/{file_name}.jpg"
                if await aiopath.isfile(thumb_path):
                    thumb = thumb_path
                elif is_audio and not is_video:
                    thumb = await get_audio_thumbnail(self._up_path)

            if (
                self._listener.as_doc
                or force_document
                or (not is_video and not is_audio and not is_image)
            ):
                key = "documents"
                if is_video and thumb is None:
                    thumb = await get_video_thumbnail(self._up_path, None)

                if self._listener.is_cancelled:
                    return
                if thumb == "none":
                    thumb = None
                caption = await self._sent_msg._client.parseText(cap_mono)
                thumbnail = (
                    InputThumbnail(InputFileLocal(path=thumb)) if thumb else None
                )
                content = InputMessageDocument(
                    document=InputFileLocal(path=self._up_path),
                    thumbnail=thumbnail,
                    disable_content_type_detection=True,
                    caption=caption,
                )
            elif is_video:
                key = "videos"
                duration = (await get_media_info(self._up_path))[0]
                if thumb is None and self._listener.thumbnail_layout:
                    thumb = await get_multiple_frames_thumbnail(
                        self._up_path,
                        self._listener.thumbnail_layout,
                        self._listener.screen_shots,
                    )
                if thumb is None:
                    thumb = await get_video_thumbnail(self._up_path, duration)
                if thumb is not None and thumb != "none":
                    with Image.open(thumb) as img:
                        width, height = img.size
                else:
                    width = 480
                    height = 320
                if self._listener.is_cancelled:
                    return
                if thumb == "none":
                    thumb = None
                caption = await self._sent_msg._client.parseText(cap_mono)
                thumbnail = (
                    InputThumbnail(InputFileLocal(path=thumb)) if thumb else None
                )
                content = InputMessageVideo(
                    video=InputFileLocal(path=self._up_path),
                    thumbnail=thumbnail,
                    duration=duration,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    caption=caption,
                )
            elif is_audio:
                key = "audios"
                duration, artist, title = await get_media_info(self._up_path)
                if self._listener.is_cancelled:
                    return
                if thumb == "none":
                    thumb = None
                caption = await self._sent_msg._client.parseText(cap_mono)
                thumbnail = (
                    InputThumbnail(InputFileLocal(path=thumb)) if thumb else None
                )
                content = InputMessageAudio(
                    audio=InputFileLocal(path=self._up_path),
                    album_cover_thumbnail=thumbnail,
                    duration=duration,
                    title=title,
                    performer=artist,
                    caption=caption,
                )
            else:
                key = "photos"
                if self._listener.is_cancelled:
                    return
                caption = await self._sent_msg._client.parseText(cap_mono)
                content = InputMessagePhoto(
                    photo=InputFileLocal(path=self._up_path),
                    caption=caption,
                )
            self._temp_message = await send_message_with_content(
                self._sent_msg, content
            )
            if self._temp_message.is_error:
                raise TgUploadException(self._temp_message)
            await self._event.wait()
            if self._listener.is_cancelled:
                return
            self._sent_msg = self._temp_message
            self._temp_message = None
            content_type = self._sent_msg.content.getType()
            if self._media_group and content_type in [
                "messageDocument",
                "messageVideo",
            ]:
                key = "documents" if content_type == "messageDocument" else "videos"
                if match := re_match(r".+(?=\.0*\d+$)|.+(?=\.part\d+\..+$)", o_path):
                    pname = match.group(0)
                    if pname in self._media_dict[key].keys():
                        self._media_dict[key][pname].append(
                            [self._sent_msg.chat_id, self._sent_msg.id]
                        )
                    else:
                        self._media_dict[key][pname] = [
                            [self._sent_msg.chat_id, self._sent_msg.id]
                        ]
                    msgs = self._media_dict[key][pname]
                    if len(msgs) == 10:
                        await self._send_media_group(pname, key, msgs)
                    else:
                        self._last_msg_in_group = True

            if (
                self._thumb is None
                and thumb is not None
                and await aiopath.exists(thumb)
            ):
                await remove(thumb)
        except Exception as err:
            if (
                self._thumb is None
                and thumb is not None
                and await aiopath.exists(thumb)
            ):
                await remove(thumb)
            raise err

    @property
    def speed(self):
        try:
            return self._processed_bytes / (time() - self._start_time)
        except:
            return 0

    @property
    def processed_bytes(self):
        return self._processed_bytes

    async def cancel_task(self):
        self._listener.is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self._listener.name}")
        await self._listener.on_upload_error("your upload has been stopped!")
