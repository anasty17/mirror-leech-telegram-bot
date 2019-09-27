
from bot.helper import download_tools, gdriveTools, listeners
from bot import LOGGER, dispatcher
from bot.helper import fs_utils
from bot.helper.download_status import DownloadStatus
from bot import download_list
from bot.helper.message_utils import *
LOGGER.info('mirror.py')


def get_readable_message(progress_list: list):
    msg = ""
    LOGGER.info(progress_list)
    for status in progress_list:
        msg += "<b>Name:</b> {}\n" \
               "<b>status:</b> {}\n" \
               "<b>Downloaded:</b> {} of {}\n" \
               "<b>Speed:</b> {}\n" \
               "<b>ETA:</b> {}\n\n".format(status.name(), status.status(),
                                           status.progress(), status.size(),
                                           status.speed(), status.eta())
    return msg


class MirrorListener(listeners.MirrorListeners):
    def __init__(self, context, update, reply_message):
        super().__init__(context, update, reply_message)

    def onDownloadStarted(self, link):
        LOGGER.info("Adding link: " + link)

    def onDownloadProgress(self, progress_status_list: list, index: int):
        msg = get_readable_message(progress_status_list)
        LOGGER.info("Editing message")
        editMessage(msg, self.context, self.reply_message)

    def onDownloadComplete(self, progress_status_list, index: int):
        msg = get_readable_message(progress_status_list)
        LOGGER.info("Download completed")
        editMessage(msg, self.context, self.reply_message)
        gdrive = gdriveTools.GoogleDriveHelper(self)
        gdrive.upload(progress_status_list[index].name())

    def onDownloadError(self, error, progress_status_list: list, index: int):
        LOGGER.error(error)
        editMessage(error, self.context, self.reply_message)
        fs_utils.clean_download(progress_status_list[index].path())

    def onUploadStarted(self, progress_status_list: list, index: int):
        msg = get_readable_message(progress_status_list)
        editMessage(msg, self.context, self.reply_message)

    def onUploadComplete(self, link: str, progress_status_list: list, index: int):
        msg = '<a href="{}">{}</a>'.format(link, progress_status_list[index].name())
        deleteMessage(self.context, self.reply_message)
        sendMessage(msg, self.context, self.update)
        fs_utils.clean_download(progress_status_list[index].path())

    def onUploadError(self, error: str, progress_status: list, index: int):
        LOGGER.error(error)
        editMessage(error, self.context, self.reply_message)
        fs_utils.clean_download(progress_status[index].path())


@run_async
def mirror(update, context):
    message = update.message.text
    link = message.replace('/mirror', '')[1:]
    reply_msg = sendMessage('Starting Download', context, update)
    listener = MirrorListener(context, update, reply_msg)
    aria = download_tools.DownloadHelper(listener)
    aria.add_download(link)


@run_async
def cancel_mirror(update, context):
    pass


mirror_handler = CommandHandler('mirror', mirror)
dispatcher.add_handler(mirror_handler)
