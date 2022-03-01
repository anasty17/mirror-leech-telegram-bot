from time import sleep
from threading import Thread

from bot import aria2, download_dict_lock, download_dict, STOP_DUPLICATE, TORRENT_DIRECT_LIMIT, ZIP_UNZIP_LIMIT, LOGGER, STORAGE_THRESHOLD
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.bot_utils import is_magnet, getDownloadByGid, new_thread, get_readable_file_size
from bot.helper.mirror_utils.status_utils.aria_download_status import AriaDownloadStatus
from bot.helper.telegram_helper.message_utils import sendMarkup, sendStatusMessage, sendMessage
from bot.helper.ext_utils.fs_utils import get_base_name, check_storage_threshold


@new_thread
def __onDownloadStarted(api, gid):
    try:
        if any([STOP_DUPLICATE, TORRENT_DIRECT_LIMIT, ZIP_UNZIP_LIMIT, STORAGE_THRESHOLD]):
            sleep(1.5)
            dl = getDownloadByGid(gid)
            if not dl:
                return
            download = api.get_download(gid)
            if STOP_DUPLICATE and not dl.getListener().isLeech:
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
            if any([ZIP_UNZIP_LIMIT, TORRENT_DIRECT_LIMIT, STORAGE_THRESHOLD]):
                sleep(1)
                limit = None
                size = api.get_download(gid).total_length
                arch = any([dl.getListener().isZip, dl.getListener().extract])
                if STORAGE_THRESHOLD is not None:
                    acpt = check_storage_threshold(size, arch, True)
                    # True if files allocated, if allocation disabled remove True arg
                    if not acpt:
                        msg = f'You must leave {STORAGE_THRESHOLD}GB free storage.'
                        msg += f'\nYour File/Folder size is {get_readable_file_size(size)}'
                        dl.getListener().onDownloadError(msg)
                        return api.remove([download], force=True, files=True)
                if ZIP_UNZIP_LIMIT is not None and arch:
                    mssg = f'Zip/Unzip limit is {ZIP_UNZIP_LIMIT}GB'
                    limit = ZIP_UNZIP_LIMIT
                elif TORRENT_DIRECT_LIMIT is not None:
                    mssg = f'Torrent/Direct limit is {TORRENT_DIRECT_LIMIT}GB'
                    limit = TORRENT_DIRECT_LIMIT
                if limit is not None:
                    LOGGER.info('Checking File/Folder Size...')
                    if size > limit * 1024**3:
                        dl.getListener().onDownloadError(f'{mssg}.\nYour File/Folder size is {get_readable_file_size(size)}')
                        return api.remove([download], force=True, files=True)
    except Exception as e:
        LOGGER.error(f"{e} onDownloadStart: {gid} stop duplicate and size check didn't pass")

@new_thread
def __onDownloadComplete(api, gid):
    LOGGER.info(f"onDownloadComplete: {gid}")
    dl = getDownloadByGid(gid)
    download = api.get_download(gid)
    if download.followed_by_ids:
        new_gid = download.followed_by_ids[0]
        new_download = api.get_download(new_gid)
        if not dl:
            dl = getDownloadByGid(new_gid)
        with download_dict_lock:
            download_dict[dl.uid()] = AriaDownloadStatus(new_gid, dl.getListener())
        LOGGER.info(f'Changed gid from {gid} to {new_gid}')
    elif dl:
        Thread(target=dl.getListener().onDownloadComplete).start()

@new_thread
def __onDownloadStopped(api, gid):
    sleep(4)
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

def add_aria2c_download(link: str, path, listener, filename):
    if is_magnet(link):
        download = aria2.add_magnet(link, {'dir': path, 'out': filename})
    else:
        download = aria2.add_uris([link], {'dir': path, 'out': filename})
    if download.error_message:
        error = str(download.error_message).replace('<', ' ').replace('>', ' ')
        LOGGER.info(f"Download Error: {error}")
        return sendMessage(error, listener.bot, listener.message)
    with download_dict_lock:
        download_dict[listener.uid] = AriaDownloadStatus(download.gid, listener)
        LOGGER.info(f"Started: {download.gid} DIR: {download.dir} ")
    sendStatusMessage(listener.message, listener.bot)

start_listener()
