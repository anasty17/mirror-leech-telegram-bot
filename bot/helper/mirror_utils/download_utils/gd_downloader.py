import random
import string

from bot import download_dict, download_dict_lock, ZIP_UNZIP_LIMIT, LOGGER
from bot.helper.mirror_utils.upload_utils import gdriveTools
from bot.helper.mirror_utils.status_utils.gd_download_status import GdDownloadStatus
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.bot_utils import get_readable_file_size


def add_gd_download(link: str, listener, gdtot):
    res, size, name, files = gdriveTools.GoogleDriveHelper().helper(link)
    if res != "":
        sendMessage(res, listener.bot, listener.update)
        return
    if ZIP_UNZIP_LIMIT is not None:
        LOGGER.info('Checking File/Folder Size...')
        if size > ZIP_UNZIP_LIMIT * 1024**3:
            msg = f'Failed, Zip/Unzip limit is {ZIP_UNZIP_LIMIT}GB.\nYour File/Folder size is {get_readable_file_size(size)}.'
            sendMessage(msg, listener.bot, listener.update)
            return
    LOGGER.info(f"Download Name: {name}")
    drive = gdriveTools.GoogleDriveHelper(name, listener)
    gid = ''.join(random.SystemRandom().choices(string.ascii_letters + string.digits, k=12))
    download_status = GdDownloadStatus(drive, size, listener, gid)
    with download_dict_lock:
        download_dict[listener.uid] = download_status
    sendStatusMessage(listener.update, listener.bot)
    drive.download(link)
    if gdtot:
        drive.deletefile(link)
