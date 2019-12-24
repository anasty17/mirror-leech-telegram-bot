from telegram.ext import CommandHandler, run_async
from bot.helper.mirror_utils.status_utils import listeners
from bot.helper.mirror_utils.upload_utils import gdriveTools
from bot.helper.mirror_utils.download_utils import aria2_download
from bot.helper.mirror_utils.status_utils.upload_status import UploadStatus
from bot.helper.mirror_utils.status_utils.tar_status import TarStatus
from bot import dispatcher, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL
from bot.helper.ext_utils import fs_utils, bot_utils
from bot import Interval
from bot.helper.telegram_helper.message_utils import *
from bot.helper.ext_utils.bot_utils import setInterval
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
import pathlib


class MirrorListener(listeners.MirrorListeners):
    def __init__(self, bot, update, isTar=False):
        super().__init__(bot, update)
        self.isTar = isTar

    def onDownloadStarted(self):
        pass

    def onDownloadProgress(self):
        # We are handling this on our own!
        pass

    def clean(self):
        Interval[0].cancel()
        del Interval[0]
        delete_all_messages()

    def onDownloadComplete(self):
        with download_dict_lock:
            LOGGER.info(f"Download completed: {download_dict[self.uid].name()}")
            download = download_dict[self.uid]
            name = download.name()
            size = download.size_raw()
            m_path = f'{DOWNLOAD_DIR}{self.uid}/{download.name()}'
        if self.isTar:
            download.is_archiving = True
            try:
                with download_dict_lock:
                    download_dict[self.uid] = TarStatus(name, m_path, size)
                path = fs_utils.tar(m_path)
            except FileNotFoundError:
                LOGGER.info('File to archive not found!')
                self.onUploadError('Internal error occurred!!')
                return
        else:
            path = f'{DOWNLOAD_DIR}{self.uid}/{download_dict[self.uid].name()}'
        name = pathlib.PurePath(path).name
        with download_dict_lock:
            download_dict[self.uid].is_archiving = False
            LOGGER.info(f"Upload Name : {name}")
            drive = gdriveTools.GoogleDriveHelper(name, self)
            upload_status = UploadStatus(drive, size, self.uid)
            download_dict[self.uid] = upload_status
        update_all_messages()
        drive.upload(name)

    def onDownloadError(self, error):
        LOGGER.info(self.update.effective_chat.id)
        with download_dict_lock:
            try:
                download = download_dict[self.uid]
                del download_dict[self.uid]
                LOGGER.info(f"Deleting folder: {download.path()}")
                fs_utils.clean_download(download.path())
                LOGGER.info(f"Deleting {download.name()} from download_dict.")
                LOGGER.info(str(download_dict))
            except Exception as e:
                LOGGER.error(str(e))
            count = len(download_dict)
        if count == 0:
            self.clean()
        if self.message.from_user.username:
            uname = f"@{self.message.from_user.username}"
        else:
            uname = f'<a href="tg://user?id={self.message.from_user.id}">{self.message.from_user.first_name}</a>'
        msg = f"{uname} your download has been stopped due to: {error}"
        if count != 0:
            update_all_messages()
        sendMessage(msg, self.bot, self.update)

    def onUploadStarted(self):
        pass

    def onUploadComplete(self, link: str):
        with download_dict_lock:
            msg = f'<a href="{link}">{download_dict[self.uid].name()}</a> ({download_dict[self.uid].size()})'
            LOGGER.info(f'Done Uploading {download_dict[self.uid].name()}')

        if len(download_dict) == 0:
            self.clean()
        else:
            update_all_messages()
        sendMessage(msg, self.bot, self.update)
        try:
            with download_dict_lock:
                fs_utils.clean_download(download_dict[self.uid].path())
                del download_dict[self.uid]
                count = len(download_dict)
            if count == 0:
                self.clean()
            else:
                update_all_messages()
        except FileNotFoundError:
            pass

    def onUploadError(self, error: str):
        LOGGER.error(error)
        sendMessage(error, self.bot, self.update)
        with download_dict_lock:
            del download_dict[self.message.message_id]
        if len(download_dict) == 0:
            self.clean()
        else:
            update_all_messages()
        try:
            with download_dict_lock:
                fs_utils.clean_download(download_dict[self.uid].path())
        except FileNotFoundError:
            pass


def _mirror(bot, update, isTar=False):
    message_args = update.message.text.split(' ')
    try:
        link = message_args[1]
    except IndexError:
        link = ''
    LOGGER.info(link)
    link = link.strip()

    if len(link) == 0:
        if update.message.reply_to_message is not None:
            document = update.message.reply_to_message.document
            if document is not None and document.mime_type == "application/x-bittorrent":
                link = document.get_file().file_path
            else:
                sendMessage('Only torrent files can be mirrored from telegram', bot, update)
                return
    if not bot_utils.is_url(link) and not bot_utils.is_magnet(link):
        sendMessage('No download source provided', bot, update)
        return
    listener = MirrorListener(bot, update, isTar)
    aria = aria2_download.AriaDownloadHelper(listener)
    aria.add_download(link, f'{DOWNLOAD_DIR}/{listener.uid}/')
    sendStatusMessage(update, bot)
    if len(Interval) == 0:
        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))


@run_async
def mirror(bot, update):
    _mirror(bot, update)


@run_async
def tar_mirror(update, bot):
    _mirror(update, bot, True)


mirror_handler = CommandHandler(BotCommands.MirrorCommand, mirror,
                                filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
tar_mirror_handler = CommandHandler(BotCommands.TarMirrorCommand, tar_mirror,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
dispatcher.add_handler(mirror_handler)
dispatcher.add_handler(tar_mirror_handler)
