from bot import aria2, download_dict_lock, download_dict, STOP_DUPLICATE, TORRENT_DIRECT_LIMIT, ZIP_UNZIP_LIMIT, LOGGER
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.bot_utils import is_magnet, getDownloadByGid, new_thread, get_readable_file_size
from bot.helper.mirror_utils.status_utils.aria_download_status import AriaDownloadStatus
from bot.helper.telegram_helper.message_utils import sendMarkup
from time import sleep
import threading


class AriaDownloadHelper:

    def __init__(self):
        super().__init__()

    @new_thread
    def __onDownloadStarted(self, api, gid):
        if STOP_DUPLICATE or TORRENT_DIRECT_LIMIT is not None or ZIP_UNZIP_LIMIT is not None:
            sleep(1)
            dl = getDownloadByGid(gid)
            download = api.get_download(gid)
        if STOP_DUPLICATE and dl is not None and not dl.getListener().isLeech:
            LOGGER.info('Checking File/Folder if already in Drive...')
            sname = download.name
            if dl.getListener().isZip:
                sname = sname + ".zip"
            if not dl.getListener().extract:
                gdrive = GoogleDriveHelper()
                smsg, button = gdrive.drive_list(sname, True)
                if smsg:
                     dl.getListener().onDownloadError('File/Folder already available in Drive.\n\n')
                     api.remove([download], force=True)
                     sendMarkup("Here are the search results:", dl.getListener().bot, dl.getListener().update, button)
                     return
        if dl is not None and (ZIP_UNZIP_LIMIT is not None or TORRENT_DIRECT_LIMIT is not None):
            limit = None
            if ZIP_UNZIP_LIMIT is not None and (dl.getListener().isZip or dl.getListener().extract):
                mssg = f'Zip/Unzip limit is {ZIP_UNZIP_LIMIT}GB'
                limit = ZIP_UNZIP_LIMIT
            elif TORRENT_DIRECT_LIMIT is not None:
                mssg = f'Torrent/Direct limit is {TORRENT_DIRECT_LIMIT}GB'
                limit = TORRENT_DIRECT_LIMIT
            if limit is not None:
                LOGGER.info('Checking File/Folder Size...')
                sleep(1)
                size = dl.size_raw()
                if size > limit * 1024**3:
                    dl.getListener().onDownloadError(f'{mssg}.\nYour File/Folder size is {get_readable_file_size(size)}')
                    api.remove([download], force=True)
                    return

    def __onDownloadComplete(self, api, gid):
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        if download.followed_by_ids:
            new_gid = download.followed_by_ids[0]
            new_download = api.get_download(new_gid)
            if dl is None:
                dl = getDownloadByGid(new_gid)
            with download_dict_lock:
                download_dict[dl.uid()] = AriaDownloadStatus(new_gid, dl.getListener())
            LOGGER.info(f'Changed gid from {gid} to {new_gid}')
        elif dl:
            threading.Thread(target=dl.getListener().onDownloadComplete).start()

    @new_thread
    def __onDownloadStopped(self, api, gid):
        sleep(4)
        dl = getDownloadByGid(gid)
        if dl:
            dl.getListener().onDownloadError('Dead torrent!')

    @new_thread
    def __onDownloadError(self, api, gid):
        LOGGER.info(f"onDownloadError: {gid}")
        sleep(0.5)
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        error = download.error_message
        LOGGER.info(f"Download Error: {error}")
        if dl:
            dl.getListener().onDownloadError(error)

    def start_listener(self):
        aria2.listen_to_notifications(threaded=True, on_download_start=self.__onDownloadStarted,
                                      on_download_error=self.__onDownloadError,
                                      on_download_stop=self.__onDownloadStopped,
                                      on_download_complete=self.__onDownloadComplete,
                                      timeout=30)

    def add_download(self, link: str, path, listener, filename):
        if is_magnet(link):
            download = aria2.add_magnet(link, {'dir': path, 'out': filename})
        else:
            download = aria2.add_uris([link], {'dir': path, 'out': filename})
        if download.error_message:
            listener.onDownloadError(download.error_message)
            return
        with download_dict_lock:
            download_dict[listener.uid] = AriaDownloadStatus(download.gid, listener)
            LOGGER.info(f"Started: {download.gid} DIR:{download.dir} ")
