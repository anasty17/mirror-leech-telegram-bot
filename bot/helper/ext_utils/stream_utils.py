from hashlib import sha256
from logging import getLogger
from urllib.parse import quote_plus

try:
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
except ImportError:
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    LinkPreviewOptions = None

from ...core.config_manager import Config
from ...core.telegram_manager import TgClient


LOGGER = getLogger(__name__)

MEDIA_TYPES = (
    "audio",
    "document",
    "photo",
    "sticker",
    "animation",
    "video",
    "voice",
    "video_note",
)


def get_media_from_message(message):
    for media_type in MEDIA_TYPES:
        media = getattr(message, media_type, None)
        if media:
            return media_type, media
    return None, None


def get_file_name(message):
    media_type, media = get_media_from_message(message)
    if media is None:
        return "file"

    if file_name := getattr(media, "file_name", None):
        return file_name

    extensions = {
        "photo": "jpg",
        "audio": "mp3",
        "voice": "ogg",
        "video": "mp4",
        "animation": "mp4",
        "video_note": "mp4",
        "sticker": "webp",
    }

    suffix = f".{extensions[media_type]}" if media_type in extensions else ""
    return f"{media_type}-{message.id}{suffix}"


def make_stream_hash(message_id, file_unique_id):
    payload = f"{message_id}:{file_unique_id}"
    return sha256(payload.encode()).hexdigest()[:6]


def build_stream_links(message):
    _, media = get_media_from_message(message)
    if media is None:
        raise ValueError("Message does not contain supported media")

    file_unique_id = getattr(media, "file_unique_id", "")
    if not file_unique_id:
        raise ValueError("Telegram file_unique_id is missing")

    message_id = message.id
    file_name = get_file_name(message)
    file_hash = make_stream_hash(message_id, file_unique_id)
    encoded_name = quote_plus(file_name, safe="")
    root = Config.STREAM_BASE_URL.rstrip("/")

    stream_link = f"{root}/{message_id}/{encoded_name}?hash={file_hash}"
    download_link = f"{root}/download/{message_id}/{encoded_name}?hash={file_hash}"
    short_link = f"{root}/{file_hash}{message_id}"

    return stream_link, download_link, short_link, file_name


def build_buttons(stream_link, download_link):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔗 Open", url=stream_link)]
        ]
    )


async def _send_without_preview(kwargs):
    if LinkPreviewOptions is not None:
        try:
            return await TgClient.bot.send_message(
                **kwargs,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except TypeError:
            pass

    try:
        return await TgClient.bot.send_message(
            **kwargs,
            disable_web_page_preview=True,
        )
    except TypeError:
        return await TgClient.bot.send_message(**kwargs)


async def _send_result_message(
    listener,
    source_message,
    text,
    stream_link,
    reply_markup,
):
    reply_to_message_id = (
        source_message.id
        if source_message.chat.id == listener.message.chat.id
        else listener.message.id
    )

    kwargs = {
        "chat_id": listener.message.chat.id,
        "text": text,
        "reply_to_message_id": reply_to_message_id,
        "message_thread_id": getattr(listener, "chat_thread_id", None),
        "disable_notification": True,
        "reply_markup": reply_markup,
    }

    if stream_link.startswith("https://") and LinkPreviewOptions is not None:
        try:
            await TgClient.bot.send_message(
                **kwargs,
                link_preview_options=LinkPreviewOptions(is_disabled=False),
            )
            return
        except Exception as error:
            LOGGER.warning(f"Link preview failed, sending without preview: {error}")

    await _send_without_preview(kwargs)


async def send_stream_links(listener, source_message, file_name=None):
    if (
        not getattr(listener, "stream_links", False)
        or not Config.STREAM_BASE_URL
        or not Config.STREAM_CHANNEL
        or not source_message
    ):
        return

    try:
        _, media = get_media_from_message(source_message)
        if media is None:
            return

        copied = await TgClient.bot.copy_message(
            chat_id=Config.STREAM_CHANNEL,
            from_chat_id=source_message.chat.id,
            message_id=source_message.id,
            disable_notification=True,
        )

        stream_link, download_link, short_link, tg_file_name = build_stream_links(copied)

        text = f"{stream_link}\n<a href=\"{short_link}\">(shortened)</a>"
        reply_markup = build_buttons(stream_link, download_link)

        await _send_result_message(
            listener,
            source_message,
            text,
            stream_link,
            reply_markup,
        )

    except Exception as error:
        LOGGER.error(f"Unable to create stream link: {error}")
