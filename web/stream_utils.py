from hashlib import sha256
from urllib.parse import quote


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


def make_legacy_stream_token(chat_id, message_id, file_unique_id):
    payload = f"{chat_id}:{message_id}:{file_unique_id}"
    return sha256(payload.encode()).hexdigest()[:32]


def verify_stream_hash(value, chat_id, message_id, media):
    file_unique_id = getattr(media, "file_unique_id", "")
    if not value or not file_unique_id:
        return False

    expected_hash = make_stream_hash(message_id, file_unique_id)
    if value == expected_hash:
        return True

    expected_legacy = make_legacy_stream_token(chat_id, message_id, file_unique_id)
    return value == expected_legacy


def build_content_disposition(disposition, file_name):
    safe_name = file_name.replace("\\", "_").replace('"', '\\"')
    encoded_name = quote(file_name)

    return f'{disposition}; filename="{safe_name}"; filename*=UTF-8\'\'{encoded_name}'
