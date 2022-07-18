from time import sleep

from bot import aria2, download_dict_lock, download_dict, STOP_DUPLICATE, LOGGER
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.bot_utils import is_magnet, getDownloadByGid, new_thread
from bot.helper.mirror_utils.status_utils.aria_download_status import AriaDownloadStatus
from bot.helper.telegram_helper.message_utils import sendMarkup, sendStatusMessage, sendMessage
from bot.helper.ext_utils.fs_utils import get_base_name


@new_thread
def __onDownloadStarted(api, gid):
    try:
        if STOP_DUPLICATE:
            download = api.get_download(gid)
            if download.is_metadata:
                LOGGER.info(f'onDownloadStarted: {gid} Metadata')
                return
            elif not download.is_torrent:
                sleep(3)
                download = api.get_download(gid)
            LOGGER.info(f'onDownloadStarted: {gid}')
            dl = getDownloadByGid(gid)
            if not dl or dl.getListener().isLeech:
                return
            LOGGER.info('Checking File/Folder if already in Drive...')
            sname = download.name
            if dl.getListener().isZip:
                sname = sname + ".zip"
            elif dl.getListener().extract:
                try:
                    sname = get_base_name(sname)
                except:
                    sname = None
            if sname is not None:
                smsg, button = GoogleDriveHelper().drive_list(sname, True)
                if smsg:
                    dl.getListener().onDownloadError('File/Folder already available in Drive.\n\n')
                    api.remove([download], force=True, files=True)
                    return sendMarkup("Here are the search results:", dl.getListener().bot, dl.getListener().message, button)
    except Exception as e:
        LOGGER.error(f"{e} onDownloadStart: {gid} stop duplicate didn't pass")

@new_thread
def __onDownloadComplete(api, gid):
    LOGGER.info(f"onDownloadComplete: {gid}")
    dl = getDownloadByGid(gid)
    download = api.get_download(gid)
    if download.followed_by_ids:
        new_gid = download.followed_by_ids[0]
        LOGGER.info(f'Changed gid from {gid} to {new_gid}')
    elif dl:
        dl.getListener().onDownloadComplete()

@new_thread
def __onDownloadStopped(api, gid):
    sleep(6)
    dl = getDownloadByGid(gid)
    if dl:
        dl.getListener().onDownloadError('Dead torrent!')

@new_thread
def __onDownloadError(api, gid):
    LOGGER.info(f"onDownloadError: {gid}")
    sleep(0.5)
    dl = getDownloadByGid(gid)
    try:
        download = api.get_download(gid)
        error = download.error_message
        LOGGER.info(f"Download Error: {error}")
    except:
        pass
    if dl:
        dl.getListener().onDownloadError(error)

def start_listener():
    aria2.listen_to_notifications(threaded=True, on_download_start=__onDownloadStarted,
                                  on_download_error=__onDownloadError,
                                  on_download_stop=__onDownloadStopped,
                                  on_download_complete=__onDownloadComplete,
                                  timeout=20)

def add_aria2c_download(link: str, path, listener, filename, auth):
    if is_magnet(link):
        download = aria2.add_magnet(link, {'dir': path})
    else:
        download = aria2.add_uris([link], {'dir': path, 'out': filename, 'header': f"authorization: {auth}"})
    if download.error_message:
        error = str(download.error_message).replace('<', ' ').replace('>', ' ')
        LOGGER.info(f"Download Error: {error}")
        return sendMessage(error, listener.bot, listener.message)
    with download_dict_lock:
        download_dict[listener.uid] = AriaDownloadStatus(download.gid, listener)
        LOGGER.info(f"Started: {download.gid} DIR: {download.dir} ")
    listener.onDownloadStart()
    sendStatusMessage(listener.message, listener.bot)

start_listener()
