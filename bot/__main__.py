from telegram.ext import CommandHandler, run_async
from bot import dispatcher, LOGGER, updater
from bot.helper.ext_utils import fs_utils
import signal
import time
from bot.helper.telegram_helper.message_utils import *
import shutil
from .helper.telegram_helper.filters import CustomFilters
from .modules import *


@run_async
def disk_usage(update, context):
    total, used, free = shutil.disk_usage('/')
    divider = 1024*1024*1024
    total //= divider
    used //= divider
    free //= divider
    disk_usage_string = f'Total disk space: {total} GBs\n' \
                        f'Used: {used} GBs\n' \
                        f'Free: {free} GBs'
    sendMessage(disk_usage_string, context, update)


@run_async
def start(update, context):
    sendMessage("This is a bot which can mirror all your links to Google drive!\n"
                "Type /help to get a list of available commands", context, update)


@run_async
def ping(update, context):
    start_time = int(round(time.time() * 1000))
    reply = sendMessage("Starting Ping", context, update)
    end_time = int(round(time.time()*1000))
    editMessage(f'{end_time - start_time} ms', context, reply)


@run_async
def bot_help(update, context):
    help_string = '''
    /help: To get this message

    /mirror [download_url][magnet_link]: Start mirroring the link to google drive

    /cancel: Reply to the message by which the download was initiated and that download will be cancelled

    /status: Shows a status of all the downloads

    /list [search term]: Searches the search term in the Google drive, if found replies with the link'''
    sendMessage(help_string, context, update)


def main():

    start_handler = CommandHandler('start', start,
                                   filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    ping_handler = CommandHandler('ping', ping,
                                  filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    help_handler = CommandHandler('help',
                                  bot_help, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    disk_handler = CommandHandler('disk',
                                  disk_usage, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(ping_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(disk_handler)
    updater.start_polling()
    LOGGER.info("Bot Started!")
    signal.signal(signal.SIGINT, fs_utils.exit_clean_up)


main()
