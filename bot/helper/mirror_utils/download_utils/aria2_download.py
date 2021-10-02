from bot import aria2, download_dict_lock, STOP_DUPLICATE, TORRENT_DIRECT_LIMIT, TAR_UNZIP_LIMIT
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.bot_utils import *
from bot.helper.mirror_utils.status_utils.aria_download_status import AriaDownloadStatus
from bot.helper.telegram_helper.message_utils import *
import threading
from aria2p import API
from time import sleep


class AriaDownloadHelper:

    def __init__(self):
        super().__init__()

    @new_thread
    def __onDownloadStarted(self, api, gid):
        if STOP_DUPLICATE or TORRENT_DIRECT_LIMIT is not None or TAR_UNZIP_LIMIT is not None:
            sleep(1)
            dl = getDownloadByGid(gid)
            download = aria2.get_download(gid)
        if STOP_DUPLICATE and dl is not None and not dl.getListener().isLeech:
            LOGGER.info('Checking File/Folder if already in Drive...')
            sname = aria2.get_download(gid).name
            if dl.getListener().isTar:
                sname = sname + ".zip" if dl.getListener().isZip else sname + ".tar"
            if dl.getListener().extract:
                smsg = None
            else:
                gdrive = GoogleDriveHelper()
                smsg, button = gdrive.drive_list(sname, True)
            if smsg:
                dl.getListener().onDownloadError('File/Folder already available in Drive.\n\n')
                aria2.remove([download], force=True)
                sendMarkup("Here are the search results:", dl.getListener().bot, dl.getListener().update, button)
                return
        if (TORRENT_DIRECT_LIMIT is not None or TAR_UNZIP_LIMIT is not None) and dl is not None:
            sleep(1)
            size = aria2.get_download(gid).total_length
            if dl.getListener().isTar or dl.getListener().extract:
                is_tar_ext = True
                mssg = f'Tar/Unzip limit is {TAR_UNZIP_LIMIT}'
            else:
                is_tar_ext = False
                mssg = f'Torrent/Direct limit is {TORRENT_DIRECT_LIMIT}'
            result = check_limit(size, TORRENT_DIRECT_LIMIT, TAR_UNZIP_LIMIT, is_tar_ext)
            if result:
                dl.getListener().onDownloadError(f'{mssg}.\nYour File/Folder size is {get_readable_file_size(size)}')
                aria2.remove([download], force=True)
                return
        update_all_messages()

    def __onDownloadComplete(self, api: API, gid):
        dl = getDownloadByGid(gid)
        download = aria2.get_download(gid)
        if download.followed_by_ids:
            new_gid = download.followed_by_ids[0]
            new_download = aria2.get_download(new_gid)
            if dl is None:
                dl = getDownloadByGid(new_gid)
            with download_dict_lock:
                download_dict[dl.uid()] = AriaDownloadStatus(new_gid, dl.getListener())
                if new_download.is_torrent:
                    download_dict[dl.uid()].is_torrent = True
            update_all_messages()
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
        sleep(0.5)  # sleep for split second to ensure proper dl gid update from onDownloadComplete
        dl = getDownloadByGid(gid)
        download = aria2.get_download(gid)
        error = download.error_message
        LOGGER.info(f"Download Error: {error}")
        if dl: 
            dl.getListener().onDownloadError(error)

    def start_listener(self):
        aria2.listen_to_notifications(threaded=True, on_download_start=self.__onDownloadStarted,
                                      on_download_error=self.__onDownloadError,
                                      on_download_stop=self.__onDownloadStopped,
                                      on_download_complete=self.__onDownloadComplete)

    def add_download(self, link: str, path, listener, filename):
        if is_magnet(link):
            download = aria2.add_magnet(link, {'dir': path, 'out': filename})
        else:
            download = aria2.add_uris([link], {'dir': path, 'out': filename})
        if download.error_message:  # no need to proceed further at this point
            listener.onDownloadError(download.error_message)
            return
        with download_dict_lock:
            download_dict[listener.uid] = AriaDownloadStatus(download.gid, listener)
            LOGGER.info(f"Started: {download.gid} DIR:{download.dir} ")
