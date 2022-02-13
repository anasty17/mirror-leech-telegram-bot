import random
import string

from bot import download_dict, download_dict_lock, ZIP_UNZIP_LIMIT, LOGGER, STOP_DUPLICATE
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.mirror_utils.status_utils.gd_download_status import GdDownloadStatus
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage, sendMarkup
from bot.helper.ext_utils.bot_utils import get_readable_file_size
from bot.helper.ext_utils.fs_utils import get_base_name


def add_gd_download(link, listener, is_gdtot):
    res, size, name, files = GoogleDriveHelper().helper(link)
    if res != "":
        return sendMessage(res, listener.bot, listener.update)
    if STOP_DUPLICATE and not listener.isLeech:
        LOGGER.info('Checking File/Folder if already in Drive...')
        if listener.isZip:
            gname = name + ".zip"
        elif listener.extract:
            try:
                gname = get_base_name(name)
            except:
                gname = None
        if gname is not None:
            gmsg, button = GoogleDriveHelper().drive_list(gname, True)
            if gmsg:
                msg = "File/Folder is already available in Drive.\nHere are the search results:"
                return sendMarkup(msg, listener.bot, listener.update, button)
    if ZIP_UNZIP_LIMIT is not None:
        LOGGER.info('Checking File/Folder Size...')
        if size > ZIP_UNZIP_LIMIT * 1024**3:
            msg = f'Failed, Zip/Unzip limit is {ZIP_UNZIP_LIMIT}GB.\nYour File/Folder size is {get_readable_file_size(size)}.'
            return sendMessage(msg, listener.bot, listener.update)
    LOGGER.info(f"Download Name: {name}")
    drive = GoogleDriveHelper(name, listener)
    gid = ''.join(random.SystemRandom().choices(string.ascii_letters + string.digits, k=12))
    download_status = GdDownloadStatus(drive, size, listener, gid)
    with download_dict_lock:
        download_dict[listener.uid] = download_status
    sendStatusMessage(listener.update, listener.bot)
    drive.download(link)
    if is_gdtot:
        drive.deletefile(link)
