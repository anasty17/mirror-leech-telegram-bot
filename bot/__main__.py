from telegram.ext import CommandHandler, run_async
from bot import dispatcher, LOGGER, updater, botStartTime
from bot.helper.ext_utils import fs_utils
from .helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time
import signal
import time
from bot.helper.telegram_helper.message_utils import *
import shutil
from .helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from .modules import authorize, list, cancel_mirror, mirror_status, mirror

@run_async
def stats(bot,update):
    currentTime = get_readable_time((time.time() - botStartTime))
    total, used, free = shutil.disk_usage('.')
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    stats = f'Bot Uptime: {currentTime}\n' \
            f'Total disk space: {total}\n' \
                        f'Used: {used}\n' \
                        f'Free: {free}'
    sendMessage(stats, bot, update)



@run_async
def start(bot,update):
    sendMessage("This is a bot which can mirror all your links to Google drive!\n"
                "Type /help to get a list of available commands", bot, update)


@run_async
def ping(bot,update):
    start_time = int(round(time.time() * 1000))
    reply = sendMessage("Starting Ping", bot, update)
    end_time = int(round(time.time()*1000))
    editMessage(f'{end_time - start_time} ms',reply)


@run_async
def log(bot,update):
    sendLogFile(bot, update)


@run_async
def bot_help(bot,update):
    help_string = f'''
/{BotCommands.HelpCommand}: To get this message

/{BotCommands.MirrorCommand} [download_url][magnet_link]: Start mirroring the link to google drive

/{BotCommands.TarMirrorCommand} [download_url][magnet_link]: start mirroring and upload the archived (.tar) version of the download

/{BotCommands.CancelMirror} : Reply to the message by which the download was initiated and that download will be cancelled

/{BotCommands.StatusCommand}: Shows a status of all the downloads

/{BotCommands.ListCommand} [search term]: Searches the search term in the Google drive, if found replies with the link

/{BotCommands.StatsCommand}: Show Stats of the machine the bot is hosted on

/{BotCommands.AuthorizeCommand}: Authorize a chat or a user to use the bot (Can only be invoked by owner of the bot)

/{BotCommands.LogCommand}: Get a log file of the bot. Handy for getting crash reports

'''
    sendMessage(help_string, bot, update)


def main():
    fs_utils.start_cleanup()
    start_handler = CommandHandler(BotCommands.StartCommand, start,
                                   filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    ping_handler = CommandHandler(BotCommands.PingCommand, ping,
                                  filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    help_handler = CommandHandler(BotCommands.HelpCommand,
                                  bot_help, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    stats_handler = CommandHandler(BotCommands.StatsCommand,
                                  stats, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    log_handler = CommandHandler(BotCommands.LogCommand, log, filters=CustomFilters.owner_filter)
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(ping_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(stats_handler)
    dispatcher.add_handler(log_handler)
    updater.start_polling()
    LOGGER.info("Bot Started!")
    signal.signal(signal.SIGINT, fs_utils.exit_clean_up)


main()
