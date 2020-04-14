from telegram.ext import CommandHandler, run_async
from telegram import Bot, Update
from bot import Interval, INDEX_URL, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL, dispatcher, LOGGER
from bot.helper.ext_utils.bot_utils import setInterval
from bot.helper.telegram_helper.message_utils import update_all_messages, sendMessage
from .mirror import MirrorListener
from bot.helper.mirror_utils.download_utils.youtube_dl_download_helper import YoutubeDLHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters


def _watch(bot: Bot, update: Update, args: list, isTar=False):
    try:
        link = args[0]
    except IndexError:
        sendMessage('/watch [yt_dl supported link] to mirror with youtube_dl', bot, update)
        return
    reply_to = update.message.reply_to_message
    if reply_to is not None:
        tag = reply_to.from_user.username
    else:
        tag = None

    listener = MirrorListener(bot, update, isTar, tag)
    ydl = YoutubeDLHelper(listener)
    ydl.add_download(link, f'{DOWNLOAD_DIR}{listener.uid}')
    if len(Interval) == 0:
        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))


@run_async
def watchTar(bot: Bot, update: Update, args: list):
    _watch(bot, update, args, True)


def watch(bot: Bot, update: Update, args: list):
    _watch(bot, update, args)


mirror_handler = CommandHandler(BotCommands.WatchCommand, watch,
                                pass_args=True,
                                filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
tar_mirror_handler = CommandHandler(BotCommands.TarWatchCommand, watchTar,
                                    pass_args=True,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
dispatcher.add_handler(mirror_handler)
dispatcher.add_handler(tar_mirror_handler)
