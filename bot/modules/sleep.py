from telegram.ext import CommandHandler

from bot import dispatcher, BASE_URL, alive
from bot.helper.telegram_helper.message_utils import sendMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands


def sleep(update, context):
    if BASE_URL is None:
        sendMessage('BASE_URL_OF_BOT not provided!', context.bot, update.message)
    elif alive.returncode is None:
        alive.kill()
        msg = 'Your bot will sleep in 30 minute maximum.\n\n'
        msg += 'In case changed your mind and want to use the bot again before the sleep then restart the bot.\n\n'
        msg += f'Open this link when you want to wake up the bot {BASE_URL}.'
        sendMessage(msg, context.bot, update.message)
    else:
        sendMessage('Ping have been stopped, your bot will sleep in less than 30 min.', context.bot, update.message)


sleep_handler = CommandHandler(command=BotCommands.SleepCommand, callback=sleep, filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
dispatcher.add_handler(sleep_handler)
