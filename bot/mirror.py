from telegram.ext import CommandHandler, run_async
from bot.helper import download_tools, gdriveTools, listeners
from bot import config, LOGGER, dispatcher

LOGGER.info('mirror.py')


class MirrorListener(listeners.MirrorListeners):
    def __init__(self, context, update, reply_message):
        super().__init__(context, update, reply_message)

    def onDownloadStarted(self, link):
        LOGGER.info("Adding link: " + link)

    def onDownloadProgress(self, progress_str_list: list):
        LOGGER.info("Editing message")
        msg = "Status:\n"
        for progress_str in progress_str_list:
            msg += progress_str + '\n\n'
        self.context.bot.edit_message_text(text=msg, message_id=self.reply_message.message_id,
                                           chat_id=self.reply_message.chat.id,
                                           parse_mode='HTMl')

    def onDownloadComplete(self, download):
        msg = "Downloaded"
        LOGGER.info("Download completed")
        self.context.bot.edit_message_text(text=msg, message_id=self.reply_message.message_id,
                                           chat_id=self.reply_message.chat.id,
                                           parse_mode='HTMl')
        gdrive = gdriveTools.GoogleDriveHelper(self)
        gdrive.upload(download.name)

    def onDownloadError(self, error):
        LOGGER.error(error)
        self.context.bot.edit_message_text(text=error, message_id=self.reply_message.message_id,
                                           chat_id=self.reply_message.chat.id,
                                           parse_mode='HTMl')

    def onUploadStarted(self, filename: str):
        msg = "<i>" + filename + "</i>:- Uploading."
        self.context.bot.edit_message_text(text=msg, message_id=self.reply_message.message_id,
                                           chat_id=self.reply_message.chat.id,
                                           parse_mode='HTMl')

    def onUploadComplete(self, link: str, file_name: str):
        msg = '<a href="{}">{}</a>'.format(link, file_name)
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
