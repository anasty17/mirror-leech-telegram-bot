from telegram.ext import CommandHandler, run_async
from telegram.error import BadRequest, TimedOut
from bot.helper.mirror_utils import download_tools, gdriveTools, listeners
from bot import LOGGER, dispatcher, DOWNLOAD_DIR
from bot.helper.ext_utils import fs_utils, bot_utils
from bot import download_dict, status_reply_dict, status_reply_dict_lock, download_dict_lock
from bot.helper.telegram_helper.message_utils import *
from bot.helper.ext_utils.bot_utils import get_readable_message, MirrorStatus
from bot.helper.ext_utils.exceptions import KillThreadException
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
import pathlib
import threading


class MirrorListener(listeners.MirrorListeners):
    def __init__(self, context, update, reply_message, isTar=False):
        super().__init__(context, update, reply_message)
        self.isTar = isTar

    def onDownloadStarted(self, link):
        LOGGER.info("Adding link: " + link)

    def onDownloadProgress(self, progress_status_list: list, index: int):
        msg = get_readable_message(progress_status_list)
        if progress_status_list[index].status() == MirrorStatus.STATUS_CANCELLED:
            editMessage(msg, self.context, self.reply_message)
            raise KillThreadException('Mirror cancelled by user')
        # LOGGER.info("Editing message")
        try:
            editMessage(msg, self.context, self.reply_message)
        except BadRequest:
            raise KillThreadException('Message deleted. Terminate thread')

    def onDownloadComplete(self, progress_status_list, index: int):
        LOGGER.info(f"Download completed: {progress_status_list[index].name()}")
        if self.isTar:
            with download_dict_lock:
                download_dict[self.uid].is_archiving = True
            try:
                path = fs_utils.tar(f'{DOWNLOAD_DIR}{self.uid}/{progress_status_list[index].name()}')
            except FileNotFoundError:
                self.onUploadError('Download cancelled!', progress_status_list, index)
                return
        else:
            path = f'{DOWNLOAD_DIR}{self.uid}/{progress_status_list[index].name()}'
        name = pathlib.PurePath(path).name
        with download_dict_lock:
            download_dict[self.uid].is_archiving = False
            LOGGER.info(f"Upload Name : {name}")
            download_dict[self.uid].upload_name = name
        gdrive = gdriveTools.GoogleDriveHelper(self)
        with download_dict_lock:
            download_dict[self.uid].upload_helper = gdrive
        gdrive.upload(name)

    def onDownloadError(self, error, progress_status_list: list, index: int):
        LOGGER.error(error)
        with status_reply_dict_lock:
            if len(status_reply_dict) == 1:
                try:
                    deleteMessage(self.context, status_reply_dict[self.update.effective_chat.id])
                except KeyError:
                    pass
            LOGGER.info(self.update.effective_chat.id)
            try:
                del status_reply_dict[self.update.effective_chat.id]
            except KeyError:
                pass
        with download_dict_lock:
            LOGGER.info(f"Deleting {progress_status_list[index].name()} from download_dict.")
            try:
               del download_dict[self.uid]
            except KeyError as e:
                LOGGER.info(str(e))
                pass   
        try:
            fs_utils.clean_download(progress_status_list[index].path())
        except FileNotFoundError:
            pass
        if self.message.from_user.username:
            uname = f"@{self.message.from_user.username}"
        else:
            uname = f'<a href="tg://user?id={self.message.from_user.id}">{self.message.from_user.first_name}</a>' 
        msg = f"{uname} your download has been stopped due to: {error}"
        sendMessage(msg, self.context, self.update)

    def onUploadStarted(self, progress_status_list: list, index: int):
        pass

    def onUploadComplete(self, link: str, progress_status_list: list, index: int):
        msg = f'<a href="{link}">{progress_status_list[index].name()}</a> ({progress_status_list[index].size()})'
        with download_dict_lock:
            del download_dict[self.message.message_id]
        try:
            deleteMessage(self.context, self.reply_message)
            with status_reply_dict_lock:
                del status_reply_dict[self.update.effective_chat.id]
        except BadRequest as e:
            LOGGER.error(str(e))
            # This means that the message has been deleted because of a /status command
            pass
        except KeyError as e:
            LOGGER.error(str(e))
            pass
        sendMessage(msg, self.context, self.update)
        try:
            fs_utils.clean_download(progress_status_list[index].path())
        except FileNotFoundError:
            pass

    def onUploadError(self, error: str, progress_status: list, index: int):
        LOGGER.error(error)
        sendMessage(error, self.context, self.update)
        with download_dict_lock:
            del download_dict[self.message.message_id]
        try:
            fs_utils.clean_download(progress_status[index].path())
        except FileNotFoundError:
            pass

    def onUploadProgress(self, progress: list, index: int):
        msg = get_readable_message(progress)
        try:
            editMessage(msg, self.context, self.reply_message)
        except BadRequest as e:
            raise KillThreadException(str(e))
        except TimedOut:
            pass


def _mirror(update, context, isTar=False):
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
                sendMessage('Only torrent files can be mirrored from telegram', context, update)
                return
    if not bot_utils.is_url(link) and not bot_utils.is_magnet(link):
        sendMessage('No download source provided', context, update)
        return
    reply_msg = sendMessage('Starting Download', context, update)
    index = update.effective_chat.id
    with status_reply_dict_lock:
        if index in status_reply_dict.keys():
            try:
                deleteMessage(context, status_reply_dict[index])
            except BadRequest:
                pass
        status_reply_dict[index] = reply_msg
    listener = MirrorListener(context, update, reply_msg, isTar)
    aria = download_tools.DownloadHelper(listener)
    t = threading.Thread(target=aria.add_download, args=(link,))
    t.start()


@run_async
def mirror(update, context):
    _mirror(update, context)


@run_async
def tar_mirror(update, context):
    _mirror(update, context, True)


mirror_handler = CommandHandler(BotCommands.MirrorCommand, mirror, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
tar_mirror_handler = CommandHandler(BotCommands.TarMirrorCommand, tar_mirror,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
dispatcher.add_handler(mirror_handler)
dispatcher.add_handler(tar_mirror_handler)
