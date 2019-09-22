from telegram.ext import CommandHandler, run_async
from bot.helper import ariaTools, gdriveTools
from bot import config, LOGGER, dispatcher
from bot.helper.exceptions import DriveAuthError
LOGGER.info('mirror.py')
@run_async
def mirror(update,context):
	message = update.message.text
	link = message.replace('/mirror','')[1:]
	reply_msg = context.bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id, text="Starting Download")
	download = ariaTools.add_download(link,[reply_msg,update])
	ariaTools.progress_status(context,reply_msg,previous=None)
	file_name = ariaTools.get_file_name(download)
	LOGGER.info("File-Name: "+file_name)
	try:
		link = gdriveTools.upload(file_name)
		msg = '<a href="{}">{}</a>'.format(link,file_name)
	except DriveAuthError as e:
		msg = 'Authentication error: {}'.format(str(e))
	except Exception as e:
		msg = str(e)
		
	context.bot.edit_message_text(text=msg,message_id=reply_msg.message_id,chat_id=reply_msg.chat.id,parse_mode='HTMl')


mirror_handler = CommandHandler('mirror', mirror)
dispatcher.add_handler(mirror_handler)