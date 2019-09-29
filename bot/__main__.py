from telegram.ext import CommandHandler, run_async
from bot import dispatcher, LOGGER, updater, aria2
import bot.mirror, bot.list, bot.mirror_status, bot.cancel_mirror
from bot.helper import fs_utils
import signal
import time
from bot.helper.message_utils import *


@run_async
def start(update, context):
    print(update)
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
    help_string = f'/help: To get this message\n' \
                  f'/mirror [download_url][magnet_link]: Start mirroring the link to google drive\n' \
                  f'/cancel: Reply to the message by which the download was initiated and that download will be cancelled\n' \
                  f'/status: Shows a status of all the downloads\n' \
                  f'/list [search term]: Searches the search term in the Google drive, if found replies with the link'
    sendMessage(help_string, context, update)


def main():

    start_handler = CommandHandler('start', start)
    ping_handler = CommandHandler('ping', ping)
    help_handler = CommandHandler('help', bot_help)
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(ping_handler)
    dispatcher.add_handler(help_handler)
    updater.start_polling()
    LOGGER.info("Bot Started!")
    signal.signal(signal.SIGINT, fs_utils.exit_clean_up)


main()
