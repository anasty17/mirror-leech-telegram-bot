from bot import download_dict, download_dict_lock
import logging
import re

LOGGER = logging.getLogger(__name__)

MAGNET_REGEX = r"magnet:\?xt=urn:btih:[a-zA-Z0-9]*"

URL_REGEX = r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-?=%.]+"

class MirrorStatus:
    STATUS_UPLOADING = "Uploading"
    STATUS_DOWNLOADING = "Downloading"
    STATUS_WAITING = "Queued"
    STATUS_FAILED = "Failed. Cleaning download"
    STATUS_CANCELLED = "Cancelled"
    STATUS_ARCHIVING = "Archiving"


PROGRESS_MAX_SIZE = 100 // 8
PROGRESS_INCOMPLETE = ['▏', '▎', '▍', '▌', '▋', '▊', '▉']

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']


def get_readable_file_size(size_in_bytes) -> str:
    index = 0
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)} {SIZE_UNITS[index]}'
    except IndexError:
        return 'File too large'


def get_download(message_id):
    with download_dict_lock:
        return download_dict[message_id].download()


def get_download_status_list():
    with download_dict_lock:
        return list(download_dict.values())


def get_progress_bar_string(status):
    if status.status() == MirrorStatus.STATUS_UPLOADING:
        completed = status.upload_helper.uploaded_bytes / 8
    else:
        completed = status.download().completed_length / 8
    total = status.download().total_length / 8
    if total == 0:
        p = 0
    else:
        p = round(completed * 100 / total)
    p = min(max(p, 0), 100)
    cFull = p // 8
    cPart = p % 8 - 1
    p_str = '█' * cFull
    if cPart >= 0:
        p_str += PROGRESS_INCOMPLETE[cPart]
    p_str += ' ' * (PROGRESS_MAX_SIZE - cFull)
    p_str = f"[{p_str}]"
    return p_str


def get_download_index(_list, gid):
    index = 0
    for i in _list:
        if i.download().gid == gid:
            return index
        index += 1


def get_download_str():
    result = ""
    with download_dict_lock:
        for status in list(download_dict.values()):
            result += (status.progress() + status.speed() + status.status())
        return result


def get_readable_message(progress_list: list = None):
    if progress_list is None:
        with download_dict_lock:
            progress_list = list(download_dict.values())
    msg = ''
    for status in progress_list:
        msg += f'<b>Name:</b> {status.name()}\n' \
               f'<b>Status:</b> {status.status()}\n' \
               f'<code>{get_progress_bar_string(status)}</code> {status.progress()} of {status.size()}\n' \
               f'<b>Speed:</b> {status.speed()}\n' \
               f'<b>ETA:</b> {status.eta()}\n\n'
#    LOGGER.info(msg)
    return msg


def get_readable_time(seconds: int) -> str:
    result = ''
    (days, remainder) = divmod(seconds, 86400)
    days = int(days)
    if days != 0:
        result += f'{days}d'
    (hours, remainder) = divmod(remainder, 3600)
    hours = int(hours)
    if hours != 0:
        result += f'{hours}h'
    (minutes, seconds) = divmod(remainder, 60)
    minutes = int(minutes)
    if minutes != 0:
        result += f'{minutes}m'
    seconds = int(seconds)
    result += f'{seconds}s'
    return result


def is_url(url: str):
    url = re.findall(URL_REGEX,url)
    if url:
        return True
    return False    


def is_magnet(url: str):
    magnet = re.findall(MAGNET_REGEX,url)
    if magnet:
        return True
    return False
