from telegram.ext import CommandHandler, run_async
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot import LOGGER, dispatcher
from bot.helper.telegram_helper.message_utils import auto_delete_message, sendMessage
from bot.helper.telegram_helper.filters import CustomFilters
import threading
from bot.helper.telegram_helper.bot_commands import BotCommands

@run_async
def list_drive(bot,update):
    message = update.message.text
    search = message.replace('/list ','')
    LOGGER.info(f"Searching: {search}")
    gdrive = GoogleDriveHelper(None)
    msg = gdrive.drive_list(search)
    if msg:
        reply_message = sendMessage(msg, bot, update)
    else:
        reply_message = sendMessage('No result found', bot, update)

    threading.Thread(target=auto_delete_message, args=(bot, update.message, reply_message)).start()


list_handler = CommandHandler(BotCommands.ListCommand, list_drive,filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
dispatcher.add_handler(list_handler)
