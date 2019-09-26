from telegram.ext import CommandHandler, run_async
from telegram.error import BadRequest
from bot.helper.gdriveTools import GoogleDriveHelper
from bot import LOGGER,dispatcher

LOGGER.info('list.py')


@run_async
def list_drive(update, context):
	message = update.message.text
	search = message.replace('/list ', '')
	LOGGER.info("Searching: "+search)
	gdrive = GoogleDriveHelper(None)		
	msg = gdrive.drive_list(search)
	if msg:
		context.bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id,
                                     text=msg,parse_mode='HTML')
	else:
		context.bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id,
                                     text="No Results Found.")

list_handler = CommandHandler('list', list_drive)
dispatcher.add_handler(list_handler)