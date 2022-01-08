import re
import threading
import time
import math
import psutil
import shutil
import requests
import urllib.request

from bot.helper.telegram_helper.bot_commands import BotCommands
from bot import dispatcher, download_dict, download_dict_lock, STATUS_LIMIT, botStartTime
from telegram import InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from bot.helper.telegram_helper import button_build, message_utils

MAGNET_REGEX = r"magnet:\?xt=urn:btih:[a-zA-Z0-9]*"

URL_REGEX = r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-?=%.]+"

COUNT = 0
PAGE_NO = 1


class MirrorStatus:
    STATUS_UPLOADING = "Uploading...📤"
    STATUS_DOWNLOADING = "Downloading...📥"
    STATUS_CLONING = "Cloning...♻️"
    STATUS_WAITING = "Queued...💤"
    STATUS_FAILED = "Failed 🚫. Cleaning Download..."
    STATUS_PAUSE = "Paused...⛔️"
    STATUS_ARCHIVING = "Archiving...🔐"
    STATUS_EXTRACTING = "Extracting...📂"
    STATUS_SPLITTING = "Splitting...✂️"
    STATUS_CHECKING = "CheckingUp...📝"
    STATUS_SEEDING = "Seeding...🌧"

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']


class setInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.stopEvent = threading.Event()
        thread = threading.Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self):
        nextTime = time.time() + self.interval
        while not self.stopEvent.wait(nextTime - time.time()):
            nextTime += self.interval
            self.action()

    def cancel(self):
        self.stopEvent.set()

def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
    except IndexError:
        return 'File too large'

def getDownloadByGid(gid):
    with download_dict_lock:
        for dl in download_dict.values():
            status = dl.status()
            if (
                status
                not in [
                    MirrorStatus.STATUS_ARCHIVING,
                    MirrorStatus.STATUS_EXTRACTING,
                    MirrorStatus.STATUS_SPLITTING,
                ]
                and dl.gid() == gid
            ):
                return dl
    return None

def getAllDownload():
    with download_dict_lock:
        for dlDetails in download_dict.values():
            status = dlDetails.status()
            if (
                status
                not in [
                    MirrorStatus.STATUS_ARCHIVING,
                    MirrorStatus.STATUS_EXTRACTING,
                    MirrorStatus.STATUS_SPLITTING,
                    MirrorStatus.STATUS_CLONING,
                    MirrorStatus.STATUS_UPLOADING,
                    MirrorStatus.STATUS_CHECKING,
                ]
                and dlDetails
            ):
                return dlDetails
    return None

def get_progress_bar_string(status):
    completed = status.processed_bytes() / 8
    total = status.size_raw() / 8
    p = 0 if total == 0 else round(completed * 100 / total)
    p = min(max(p, 0), 100)
    cFull = p // 8
    p_str = '■' * cFull
    p_str += '□' * (12 - cFull)
    p_str = f"[{p_str}]"
    return p_str

def get_readable_message():
    with download_dict_lock:
        msg = ""
        dlspeed_bytes = 0
        uldl_bytes = 0
        START = 0
        if STATUS_LIMIT is not None:
            tasks = len(download_dict)
            global pages
            pages = math.ceil(tasks/STATUS_LIMIT)
            if PAGE_NO > pages and pages != 0:
                globals()['COUNT'] -= STATUS_LIMIT
                globals()['PAGE_NO'] -= 1
            START = COUNT
        for index, download in enumerate(list(download_dict.values())[START:], start=1):
            msg += f"<b>═══════ @KristyCloud ═══════\n\nName : {download.name()}</b>"
            msg += f"\n<b>Status : {download.status()}</b>"
            if download.status() not in [
                MirrorStatus.STATUS_ARCHIVING,
                MirrorStatus.STATUS_EXTRACTING,
                MirrorStatus.STATUS_SPLITTING,
                MirrorStatus.STATUS_SEEDING,
            ]:
                msg += f"\n{get_progress_bar_string(download)} {download.progress()}"
                if download.status() == MirrorStatus.STATUS_CLONING:
                    msg += f"\n<b>Cloned : {get_readable_file_size(download.processed_bytes())} of {download.size()}</b>"
                elif download.status() == MirrorStatus.STATUS_UPLOADING:
                    msg += f"\n<b>Uploaded : {get_readable_file_size(download.processed_bytes())} of {download.size()}</b>"
                else:
                    msg += f"\n<b>Downloaded : {get_readable_file_size(download.processed_bytes())} of {download.size()}</b>"
                msg += f"\n<b>Speed : {download.speed()}</b> || <b>ETA : {download.eta()}</b>"
                try:
                    msg += f"\n<b>Seeders : {download.aria_download().num_seeders}"</b> \
                           f" | <b>Peers : {download.aria_download().connections}"</b>
                except:
                    pass
                try:
                    msg += f"\n<b>Seeders : {download.torrent_info().num_seeds}" </b>\
                           f" | <b>Leechers : {download.torrent_info().num_leechs}</b>"
                except:
                    pass
                msg += f"\n<b>/{BotCommands.CancelMirror} {download.gid()}</b>"
            elif download.status() == MirrorStatus.STATUS_SEEDING:
                msg += f"\n<b>Size : {download.size()}</b>"
                msg += f"\n<b>Speed : {get_readable_file_size(download.torrent_info().upspeed)}/s</b>"
                msg += f" | <b>Uploaded : {get_readable_file_size(download.torrent_info().uploaded)}</b>"
                msg += f"\n<b>Ratio : {round(download.torrent_info().ratio, 3)}</b>"
                msg += f" | <b>Time : {get_readable_time(download.torrent_info().seeding_time)}</b>"
                msg += f"\n<b>/{BotCommands.CancelMirror} {download.gid()}</b>"
            else:
                msg += f"\n<b>Size : {download.size()}</b>"
            msg += "\n\n"
            if STATUS_LIMIT is not None and index == STATUS_LIMIT:
                break
        total, used, free = shutil.disk_usage('.')
        free = get_readable_file_size(free)
        currentTime = get_readable_time(time.time() - botStartTime)
        bmsg = f"<b>CPU : {psutil.cpu_percent()}% | FREE : {free}</b>"
        for download in list(download_dict.values()):
            speedy = download.speed()
            if download.status() == MirrorStatus.STATUS_DOWNLOADING:
                if 'K' in speedy:
                    dlspeed_bytes += float(speedy.split('K')[0]) * 1024
                elif 'M' in speedy:
                    dlspeed_bytes += float(speedy.split('M')[0]) * 1048576
            if download.status() == MirrorStatus.STATUS_UPLOADING:
                if 'KB/s' in speedy:
                    uldl_bytes += float(speedy.split('K')[0]) * 1024
                elif 'MB/s' in speedy:
                    uldl_bytes += float(speedy.split('M')[0]) * 1048576
        dlspeed = get_readable_file_size(dlspeed_bytes)
        ulspeed = get_readable_file_size(uldl_bytes)
        bmsg += f"\n<b>RAM : {psutil.virtual_memory().percent}% | UPTIME : {currentTime}</b>"
        bmsg += f"\n<b>DL : {dlspeed}/s | UL : {ulspeed}/s</b>"
        if STATUS_LIMIT is not None and tasks > STATUS_LIMIT:
            msg += f"<b>Page : {PAGE_NO}/{pages} | Tasks : {tasks}</b>\n"
            buttons = button_build.ButtonMaker()
            buttons.sbutton("<--- Previous", "status pre")
            buttons.sbutton("Next --->", "status nex")
            button = InlineKeyboardMarkup(buttons.build_menu(2))
            return msg + bmsg, button
        return msg + bmsg, ""

def turn(update, context):
    query = update.callback_query
    data = query.data
    data = data.split(' ')
    query.answer()
    try:
        with download_dict_lock:
            global COUNT, PAGE_NO
            if data[1] == "nex":
                if PAGE_NO == pages:
                    COUNT = 0
                    PAGE_NO = 1
                else:
                    COUNT += STATUS_LIMIT
                    PAGE_NO += 1
            elif data[1] == "pre":
                if PAGE_NO == 1:
                    COUNT = STATUS_LIMIT * (pages - 1)
                    PAGE_NO = pages
                else:
                    COUNT -= STATUS_LIMIT
                    PAGE_NO -= 1
        message_utils.update_all_messages()
    except:
        query.message.delete()

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
    url = re.findall(URL_REGEX, url)
    return bool(url)

def is_gdrive_link(url: str):
    return "drive.google.com" in url

def is_gdtot_link(url: str):
    url = re.match(r'https?://.*\.gdtot\.\S+', url)
    return bool(url)

def is_mega_link(url: str):
    return "mega.nz" in url or "mega.co.nz" in url

def get_mega_link_type(url: str):
    if "folder" in url:
        return "folder"
    elif "file" in url:
        return "file"
    elif "/#F!" in url:
        return "folder"
    return "file"

def is_magnet(url: str):
    magnet = re.findall(MAGNET_REGEX, url)
    return bool(magnet)

def new_thread(fn):
    """To use as decorator to make a function call threaded.
    Needs import
    from threading import Thread"""

    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread

    return wrapper

def get_content_type(link: str):
    try:
        res = requests.head(link, allow_redirects=True, timeout=5)
        content_type = res.headers.get('content-type')
    except:
        content_type = None

    if content_type is None:
        try:
            res = urllib.request.urlopen(link, timeout=5)
            info = res.info()
            content_type = info.get_content_type()
        except:
            content_type = None
    return content_type

status_handler = CallbackQueryHandler(turn, pattern="status", run_async=True)
dispatcher.add_handler(status_handler)
