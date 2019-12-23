from telegram.ext import CommandHandler, run_async
from telegram.error import BadRequest, TimedOut
from bot.helper.mirror_utils import aria2_download, gdriveTools, listeners
from bot import LOGGER, dispatcher, DOWNLOAD_DIR
from bot.helper.ext_utils import fs_utils, bot_utils
from bot import download_dict, status_reply_dict, status_reply_dict_lock, download_dict_lock, Interval
from bot.helper.telegram_helper.message_utils import *
from bot.helper.ext_utils.bot_utils import get_readable_message, MirrorStatus,setInterval
from bot.helper.ext_utils.exceptions import MessageDeletedError
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
import pathlib
from time import sleep


class MirrorListener(listeners.MirrorListeners):
    def __init__(self, bot, update, isTar=False):
        super().__init__(bot, update)
        self.isTar = isTar

    def onDownloadStarted(self,reply_message):
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
        if self.isTar:
            download.is_archiving = True
            try:
                path = fs_utils.tar(f'{DOWNLOAD_DIR}{self.uid}/{download.name()}')
            except FileNotFoundError:
                self.onUploadError('Download cancelled!', download_dict, self.uid)
                return
        else:
            path = f'{DOWNLOAD_DIR}{self.uid}/{download_dict[self.uid].name()}'
        name = pathlib.PurePath(path).name
        with download_dict_lock:
            download_dict[self.uid].is_archiving = False
            LOGGER.info(f"Upload Name : {name}")
            download_dict[self.uid].upload_name = name
            gdrive = gdriveTools.GoogleDriveHelper(self)
            download_dict[self.uid].upload_helper = gdrive
        update_all_messages()
        gdrive.upload(name)

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

    def onUploadStarted(self, progress_status_list: list, index: int):
        pass

    def onUploadComplete(self, link: str, progress_status_list: list, index: int):
        msg = f'<a href="{link}">{progress_status_list[index].name()}</a> ({progress_status_list[index].size()})'
        with download_dict_lock:
            del download_dict[self.uid]
        if len(download_dict) == 0:
            self.clean()
        else:
            update_all_messages()
        sendMessage(msg, self.bot, self.update)
        print("Downloads: "+str(download_dict))
        try:
            fs_utils.clean_download(progress_status_list[index].path())
        except FileNotFoundError:
            pass

    def onUploadError(self, error: str, progress_status: list, index: int):
        LOGGER.error(error)
        sendMessage(error, self.bot, self.update)
        with download_dict_lock:
            del download_dict[self.message.message_id]
        if len(download_dict) == 0:
            self.clean()
        else:
            update_all_messages()
        try:
            fs_utils.clean_download(progress_status[index].path())
        except FileNotFoundError:
            pass

    def onUploadProgress(self, progress: list, index: int):
        msg = get_readable_message(progress)
        try:
            print("lul")
            #editMessage(msg, self.bot, self.reply_message)
        except BadRequest as e:
            raise MessageDeletedError(str(e))
        except TimedOut:
            pass


def _mirror(bot,update ,isTar=False):
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
    sendStatusMessage(update,bot)
    if len(Interval) == 0:
        Interval.append(setInterval(5,update_all_messages))

@run_async
def mirror(bot,update):
    _mirror(bot,update)


@run_async
def tar_mirror(update, bot):
    _mirror(update, bot, True)


mirror_handler = CommandHandler(BotCommands.MirrorCommand, mirror,
                                filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
tar_mirror_handler = CommandHandler(BotCommands.TarMirrorCommand, tar_mirror,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
dispatcher.add_handler(mirror_handler)
dispatcher.add_handler(tar_mirror_handler)
