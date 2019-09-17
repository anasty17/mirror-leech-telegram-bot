from telegram.ext import Updater,CommandHandler,run_async
import ariaTools
import logging
import gdriveTools
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)




@run_async
def start(update, context):
	print(update)
	context.bot.send_message(chat_id=update.message.chat_id, text="I'm a bot, please talk to me!")

@run_async
def mirror(update,context):
	message = update.message.text
	link = message.replace('/mirror','')[1:]
	reply_msg = context.bot.send_message(chat_id=update.message.chat_id, reply_to_message_id=update.message.message_id, text="Starting Download")
	download = ariaTools.add_download(link,[reply_msg,update])
	ariaTools.progress_status(context,reply_msg,previous=None)
	with open('data','r') as f:
		file_name = f.read()
		print("File-Name: "+file_name)
	link = gdriveTools.upload(file_name)
	msg = '<a href="{}">{}</a>'.format(link,file_name)
	context.bot.edit_message_text(text=msg,message_id=reply_msg.message_id,chat_id=reply_msg.chat.id,parse_mode='HTMl')


def main():
	BOT_TOKEN = "976868081:AAEO--j0dqomyy0ZOYD0sSIGim4UHTYQg5E"
	updater = Updater(token=BOT_TOKEN, use_context=True)

	start_handler = CommandHandler('start', start)
	mirror_handler = CommandHandler('mirror',mirror)
	dispatcher = updater.dispatcher
	dispatcher.add_handler(start_handler)
	dispatcher.add_handler(mirror_handler)
	logging.info("Bot Started")




	updater.start_polling()


main()	
