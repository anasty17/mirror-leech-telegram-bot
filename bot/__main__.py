import signal

from os import path as ospath, remove as osremove, execl as osexecl
from subprocess import run as srun, check_output
from psutil import disk_usage, cpu_percent, swap_memory, cpu_count, virtual_memory, net_io_counters, boot_time
from time import time
from pyrogram import idle
from sys import executable
from telegram import ParseMode, InlineKeyboardMarkup
from telegram.ext import CommandHandler

from bot import bot, app, dispatcher, updater, botStartTime, IGNORE_PENDING_REQUESTS, alive, AUTHORIZED_CHATS, LOGGER, Interval, rss_session
from .helper.ext_utils.fs_utils import start_cleanup, clean_all, exit_clean_up
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.message_utils import sendMessage, sendMarkup, editMessage, sendLogFile
from .helper.ext_utils.telegraph_helper import telegraph
from .helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.button_build import ButtonMaker
from .modules import authorize, list, cancel_mirror, mirror_status, mirror, clone, watch, shell, eval, delete, count, leech_settings, search, rss


def stats(update, context):
    if ospath.exists('.git'):
        last_commit = check_output(["git log -1 --date=short --pretty=format:'%cd <b>From</b> %cr'"], shell=True).decode()
    else:
        last_commit = 'No UPSTREAM_REPO'
    currentTime = get_readable_time(time() - botStartTime)
    osUptime = get_readable_time(time() - boot_time())
    total, used, free, disk= disk_usage('/')
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    sent = get_readable_file_size(net_io_counters().bytes_sent)
    recv = get_readable_file_size(net_io_counters().bytes_recv)
    cpuUsage = cpu_percent(interval=0.5)
    p_core = cpu_count(logical=False)
    t_core = cpu_count(logical=True)
    swap = swap_memory()
    swap_p = swap.percent
    swap_t = get_readable_file_size(swap.total)
    swap_u = get_readable_file_size(swap.used)
    memory = virtual_memory()
    mem_p = memory.percent
    mem_t = get_readable_file_size(memory.total)
    mem_a = get_readable_file_size(memory.available)
    mem_u = get_readable_file_size(memory.used)
    stats = f'<b>Commit Date:</b> {last_commit}\n\n'\
            f'<b>Bot Uptime:</b> {currentTime}\n'\
            f'<b>OS Uptime:</b> {osUptime}\n\n'\
            f'<b>Total Disk Space:</b> {total}\n'\
            f'<b>Used:</b> {used} | <b>Free:</b> {free}\n\n'\
            f'<b>Upload:</b> {sent}\n'\
            f'<b>Download:</b> {recv}\n\n'\
            f'<b>CPU:</b> {cpuUsage}%\n'\
            f'<b>RAM:</b> {mem_p}%\n'\
            f'<b>DISK:</b> {disk}%\n\n'\
            f'<b>Physical Cores:</b> {p_core}\n'\
            f'<b>Total Cores:</b> {t_core}\n\n'\
            f'<b>SWAP:</b> {swap_t} | <b>Used:</b> {swap_p}%\n'\
            f'<b>Memory Total:</b> {mem_t}\n'\
            f'<b>Memory Free:</b> {mem_a}\n'\
            f'<b>Memory Used:</b> {mem_u}\n'
    sendMessage(stats, context.bot, update.message)


def start(update, context):
    buttons = ButtonMaker()
    buttons.buildbutton("Repo", "https://www.github.com/anasty17/mirror-leech-telegram-bot")
    buttons.buildbutton("Report Group", "https://t.me/+PRRzqHd31XY3ZWZk")
    reply_markup = InlineKeyboardMarkup(buttons.build_menu(2))
    if CustomFilters.authorized_user(update) or CustomFilters.authorized_chat(update):
        start_string = f'''
This bot can mirror all your links to Google Drive!
Type /{BotCommands.HelpCommand} to get a list of available commands
'''
        sendMarkup(start_string, context.bot, update.message, reply_markup)
    else:
        sendMarkup('Not Authorized user, deploy your own mirror-leech bot', context.bot, update.message, reply_markup)

def restart(update, context):
    restart_message = sendMessage("Restarting...", context.bot, update.message)
    if Interval:
        Interval[0].cancel()
    alive.kill()
    srun(["pkill", "-f", "gunicorn"])
    clean_all()
    srun(["pkill", "-f", "aria2c"])
    srun(["python3", "update.py"])
    with open(".restartmsg", "w") as f:
        f.truncate(0)
        f.write(f"{restart_message.chat.id}\n{restart_message.message_id}\n")
    osexecl(executable, executable, "-m", "bot")


def ping(update, context):
    start_time = int(round(time() * 1000))
    reply = sendMessage("Starting Ping", context.bot, update.message)
    end_time = int(round(time() * 1000))
    editMessage(f'{end_time - start_time} ms', reply)


def log(update, context):
    sendLogFile(context.bot, update.message)


help_string_telegraph = f'''<br>
<b>/{BotCommands.HelpCommand}</b>: To get this message
<br><br>
<b>/{BotCommands.MirrorCommand}</b> [download_url][magnet_link]: Start mirroring to Google Drive. Send <b>/{BotCommands.MirrorCommand}</b> for more help
<br><br>
<b>/{BotCommands.ZipMirrorCommand}</b> [download_url][magnet_link]: Start mirroring and upload the file/folder compressed with zip extension
<br><br>
<b>/{BotCommands.UnzipMirrorCommand}</b> [download_url][magnet_link]: Start mirroring and upload the file/folder extracted from any archive extension
<br><br>
<b>/{BotCommands.QbMirrorCommand}</b> [magnet_link][torrent_file][torrent_file_url]: Start Mirroring using qBittorrent, Use <b>/{BotCommands.QbMirrorCommand} s</b> to select files before downloading
<br><br>
<b>/{BotCommands.QbZipMirrorCommand}</b> [magnet_link][torrent_file][torrent_file_url]: Start mirroring using qBittorrent and upload the file/folder compressed with zip extension
<br><br>
<b>/{BotCommands.QbUnzipMirrorCommand}</b> [magnet_link][torrent_file][torrent_file_url]: Start mirroring using qBittorrent and upload the file/folder extracted from any archive extension
<br><br>
<b>/{BotCommands.LeechCommand}</b> [download_url][magnet_link]: Start leeching to Telegram, Use <b>/{BotCommands.LeechCommand} s</b> to select files before leeching
<br><br>
<b>/{BotCommands.ZipLeechCommand}</b> [download_url][magnet_link]: Start leeching to Telegram and upload the file/folder compressed with zip extension
<br><br>
<b>/{BotCommands.UnzipLeechCommand}</b> [download_url][magnet_link][torent_file]: Start leeching to Telegram and upload the file/folder extracted from any archive extension
<br><br>
<b>/{BotCommands.QbLeechCommand}</b> [magnet_link][torrent_file][torrent_file_url]: Start leeching to Telegram using qBittorrent, Use <b>/{BotCommands.QbLeechCommand} s</b> to select files before leeching
<br><br>
<b>/{BotCommands.QbZipLeechCommand}</b> [magnet_link][torrent_file][torrent_file_url]: Start leeching to Telegram using qBittorrent and upload the file/folder compressed with zip extension
<br><br>
<b>/{BotCommands.QbUnzipLeechCommand}</b> [magnet_link][torrent_file][torrent_file_url]: Start leeching to Telegram using qBittorrent and upload the file/folder extracted from any archive extension
<br><br>
<b>/{BotCommands.CloneCommand}</b> [drive_url][gdtot_url]: Copy file/folder to Google Drive
<br><br>
<b>/{BotCommands.CountCommand}</b> [drive_url][gdtot_url]: Count file/folder of Google Drive
<br><br>
<b>/{BotCommands.DeleteCommand}</b> [drive_url]: Delete file/folder from Google Drive (Only Owner & Sudo)
<br><br>
<b>/{BotCommands.WatchCommand}</b> [yt-dlp supported link]: Mirror yt-dlp supported link. Send <b>/{BotCommands.WatchCommand}</b> for more help
<br><br>
<b>/{BotCommands.ZipWatchCommand}</b> [yt-dlp supported link]: Mirror yt-dlp supported link as zip
<br><br>
<b>/{BotCommands.LeechWatchCommand}</b> [yt-dlp supported link]: Leech yt-dlp supported link
<br><br>
<b>/{BotCommands.LeechZipWatchCommand}</b> [yt-dlp supported link]: Leech yt-dlp supported link as zip
<br><br>
<b>/{BotCommands.LeechSetCommand}</b>: Leech settings
<br><br>
<b>/{BotCommands.SetThumbCommand}</b>: Reply photo to set it as Thumbnail
<br><br>
<b>/{BotCommands.RssListCommand}</b>: List all subscribed rss feed info
<br><br>
<b>/{BotCommands.RssGetCommand}</b>: [Title] [Number](last N links): Force fetch last N links
<br><br>
<b>/{BotCommands.RssSubCommand}</b>: [Title] [Rss Link] f: [filter]: Subscribe new rss feed
<br><br>
<b>/{BotCommands.RssUnSubCommand}</b>: [Title]: Unubscribe rss feed by title
<br><br>
<b>/{BotCommands.RssSettingsCommand}</b>: Rss Settings
<br><br>
<b>/{BotCommands.CancelMirror}</b>: Reply to the message by which the download was initiated and that download will be cancelled
<br><br>
<b>/{BotCommands.CancelAllCommand}</b>: Cancel all downloading tasks
<br><br>
<b>/{BotCommands.ListCommand}</b> [query]: Search in Google Drive(s)
<br><br>
<b>/{BotCommands.SearchCommand}</b> [query]: Search for torrents with API
<br>sites: <code>rarbg, 1337x, yts, etzv, tgx, torlock, piratebay, nyaasi, ettv</code><br><br>
<b>/{BotCommands.StatusCommand}</b>: Shows a status of all the downloads
<br><br>
<b>/{BotCommands.StatsCommand}</b>: Show Stats of the machine the bot is hosted on
'''

help = telegraph.create_page(
        title='Mirror-Leech-Bot Help',
        content=help_string_telegraph,
    )["path"]

help_string = f'''
/{BotCommands.PingCommand}: Check how long it takes to Ping the Bot

/{BotCommands.AuthorizeCommand}: Authorize a chat or a user to use the bot (Can only be invoked by Owner & Sudo of the bot)

/{BotCommands.UnAuthorizeCommand}: Unauthorize a chat or a user to use the bot (Can only be invoked by Owner & Sudo of the bot)

/{BotCommands.AuthorizedUsersCommand}: Show authorized users (Only Owner & Sudo)

/{BotCommands.AddSudoCommand}: Add sudo user (Only Owner)

/{BotCommands.RmSudoCommand}: Remove sudo users (Only Owner)

/{BotCommands.RestartCommand}: Restart and update the bot

/{BotCommands.LogCommand}: Get a log file of the bot. Handy for getting crash reports

/{BotCommands.ShellCommand}: Run commands in Shell (Only Owner)

/{BotCommands.ExecHelpCommand}: Get help for Executor module (Only Owner)
'''

def bot_help(update, context):
    button = ButtonMaker()
    button.buildbutton("Other Commands", f"https://telegra.ph/{help}")
    reply_markup = InlineKeyboardMarkup(button.build_menu(1))
    sendMarkup(help_string, context.bot, update.message, reply_markup)

botcmds = [

        (f'{BotCommands.MirrorCommand}', 'Mirror'),
        (f'{BotCommands.ZipMirrorCommand}','Mirror and upload as zip'),
        (f'{BotCommands.UnzipMirrorCommand}','Mirror and extract files'),
        (f'{BotCommands.QbMirrorCommand}','Mirror torrent using qBittorrent'),
        (f'{BotCommands.QbZipMirrorCommand}','Mirror torrent and upload as zip using qb'),
        (f'{BotCommands.QbUnzipMirrorCommand}','Mirror torrent and extract files using qb'),
        (f'{BotCommands.WatchCommand}','Mirror yt-dlp supported link'),
        (f'{BotCommands.ZipWatchCommand}','Mirror yt-dlp supported link as zip'),
        (f'{BotCommands.CloneCommand}','Copy file/folder to Drive'),
        (f'{BotCommands.LeechCommand}','Leech'),
        (f'{BotCommands.ZipLeechCommand}','Leech and upload as zip'),
        (f'{BotCommands.UnzipLeechCommand}','Leech and extract files'),
        (f'{BotCommands.QbLeechCommand}','Leech torrent using qBittorrent'),
        (f'{BotCommands.QbZipLeechCommand}','Leech torrent and upload as zip using qb'),
        (f'{BotCommands.QbUnzipLeechCommand}','Leech torrent and extract using qb'),
        (f'{BotCommands.LeechWatchCommand}','Leech yt-dlp supported link'),
        (f'{BotCommands.LeechZipWatchCommand}','Leech yt-dlp supported link as zip'),
        (f'{BotCommands.CountCommand}','Count file/folder of Drive'),
        (f'{BotCommands.DeleteCommand}','Delete file/folder from Drive'),
        (f'{BotCommands.CancelMirror}','Cancel a task'),
        (f'{BotCommands.CancelAllCommand}','Cancel all downloading tasks'),
        (f'{BotCommands.ListCommand}','Search in Drive'),
        (f'{BotCommands.LeechSetCommand}','Leech settings'),
        (f'{BotCommands.SetThumbCommand}','Set thumbnail'),
        (f'{BotCommands.StatusCommand}','Get mirror status message'),
        (f'{BotCommands.StatsCommand}','Bot usage stats'),
        (f'{BotCommands.PingCommand}','Ping the bot'),
        (f'{BotCommands.RestartCommand}','Restart the bot'),
        (f'{BotCommands.LogCommand}','Get the bot Log'),
        (f'{BotCommands.HelpCommand}','Get detailed help')
    ]

def main():
    # bot.set_my_commands(botcmds)
    start_cleanup()
    # Check if the bot is restarting
    if ospath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
        bot.edit_message_text("Restarted successfully!", chat_id, msg_id)
        osremove(".restartmsg")
    elif AUTHORIZED_CHATS:
        try:
            for i in AUTHORIZED_CHATS:
                if str(i).startswith('-'):
                    bot.sendMessage(chat_id=i, text="<b>Bot Started!</b>", parse_mode=ParseMode.HTML)
        except Exception as e:
            LOGGER.error(e)

    start_handler = CommandHandler(BotCommands.StartCommand, start, run_async=True)
    ping_handler = CommandHandler(BotCommands.PingCommand, ping,
                                  filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
    restart_handler = CommandHandler(BotCommands.RestartCommand, restart,
                                     filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
    help_handler = CommandHandler(BotCommands.HelpCommand,
                                  bot_help, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
    stats_handler = CommandHandler(BotCommands.StatsCommand,
                                   stats, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
    log_handler = CommandHandler(BotCommands.LogCommand, log, filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(ping_handler)
    dispatcher.add_handler(restart_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(stats_handler)
    dispatcher.add_handler(log_handler)
    updater.start_polling(drop_pending_updates=IGNORE_PENDING_REQUESTS)
    LOGGER.info("Bot Started!")
    signal.signal(signal.SIGINT, exit_clean_up)
    if rss_session is not None:
        rss_session.start()

app.start()
main()
idle()
