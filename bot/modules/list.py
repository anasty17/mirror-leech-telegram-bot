from telegram.ext import CommandHandler, run_async
from bot.helper.mirror_utils.gdriveTools import GoogleDriveHelper
from bot import LOGGER, dispatcher
from bot.helper.telegram_helper.message_utils import auto_delete_message, sendMessage
import threading
from bot.helper.telegram_helper.bot_commands import BotCommands

@run_async
def list_drive(update, context):
    message = update.message.text
    search = message.replace('/list ','')
    LOGGER.info(f"Searching: {search}")
    gdrive = GoogleDriveHelper(None)
    msg = gdrive.drive_list(search)
    if msg:
        reply_message = sendMessage(msg, context, update)
    else:
        reply_message = sendMessage('No result found', context, update)

    threading.Thread(target=auto_delete_message, args=(context, update.message, reply_message)).start()


list_handler = CommandHandler(BotCommands.ListCommand, list_drive)
dispatcher.add_handler(list_handler)
