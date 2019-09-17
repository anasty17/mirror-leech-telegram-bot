from telegram.ext import CommandHandler, run_async
from bot import dispatcher, LOGGER, updater
import bot.mirror

@run_async
def start(update, context):
	print(update)
	context.bot.send_message(chat_id=update.message.chat_id, text="I'm a bot, please talk to me!")

LOGGER.info('__main__.py')
def main():
    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)
    LOGGER.info("Bot Started!")
    updater.start_polling()
    
main()