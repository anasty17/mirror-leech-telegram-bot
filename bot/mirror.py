from telegram.ext import CommandHandler, run_async
from bot.helper import download_tools, gdriveTools, listeners
from bot import config, LOGGER, dispatcher

LOGGER.info('mirror.py')


def get_readable_message(progress_list: list):
    msg = ""
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
        LOGGER.info("Editing message")
        msg = get_readable_message(progress_status_list)
        self.context.bot.edit_message_text(text=msg, message_id=self.reply_message.message_id,
                                           chat_id=self.reply_message.chat.id,
                                           parse_mode='HTMl')

    def onDownloadComplete(self, progress_status_list, index: int):
        msg = get_readable_message(progress_status_list)
        LOGGER.info("Download completed")
        self.context.bot.edit_message_text(text=msg, message_id=self.reply_message.message_id,
                                           chat_id=self.reply_message.chat.id,
                                           parse_mode='HTMl')
        gdrive = gdriveTools.GoogleDriveHelper(self)
        gdrive.upload(progress_status_list[index].name())

    def onDownloadError(self, error):
        LOGGER.error(error)
        self.context.bot.edit_message_text(text=error, message_id=self.reply_message.message_id,
                                           chat_id=self.reply_message.chat.id,
                                           parse_mode='HTMl')

    def onUploadStarted(self, progress_status_list: list, index: int):
        msg = get_readable_message(progress_status_list)
        if not msg != self.update.message.text:
            self.context.bot.edit_message_text(text=msg, message_id=self.reply_message.message_id,
                                               chat_id=self.reply_message.chat.id,
                                               parse_mode='HTMl')

    def onUploadComplete(self, link: str, progress_status_list: list, index: int):
        msg = '<a href="{}">{}</a>'.format(link, progress_status_list[index].name())
        self.context.bot.delete_message(chat_id=self.reply_message.chat.id, message_id=self.reply_message.message_id)
        self.context.bot.send_message(chat_id=self.update.message.chat_id,
                                      reply_to_message_id=self.update.message.message_id,
                                      text=msg, parse_mode='HTMl')

    def onUploadError(self, error: str):
        LOGGER.error(error)
        self.context.bot.edit_message_text(text=error, message_id=self.reply_message.message_id,
                                           chat_id=self.reply_message.chat.id,
                                           parse_mode='HTMl')


@run_async
def mirror(update, context):
    message = update.message.text
    link = message.replace('/mirror', '')[1:]
    reply_msg = context.bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id,
                                         text="Starting Download")
    listener = MirrorListener(context, update, reply_msg)
    aria = download_tools.DownloadHelper(listener)
    aria.add_download(link)


mirror_handler = CommandHandler('mirror', mirror)
dispatcher.add_handler(mirror_handler)
