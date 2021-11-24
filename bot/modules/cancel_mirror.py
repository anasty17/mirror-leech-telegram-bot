from telegram.ext import CommandHandler
from bot import download_dict, dispatcher, download_dict_lock, DOWNLOAD_DIR
from bot.helper.ext_utils.fs_utils import clean_download
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage

from time import sleep
from bot.helper.ext_utils.bot_utils import getDownloadByGid, MirrorStatus, getAllDownload


def cancel_mirror(update, context):
    args = update.message.text.split(" ", maxsplit=1)
    mirror_message = None
    if len(args) > 1:
        gid = args[1]
        dl = getDownloadByGid(gid)
        if not dl:
            sendMessage(f"GID: <code>{gid}</code> Not Found.", context.bot, update)
            return
        mirror_message = dl.message
    elif update.message.reply_to_message:
        mirror_message = update.message.reply_to_message
        with download_dict_lock:
            keys = list(download_dict.keys())
            try:
                dl = download_dict[mirror_message.message_id]
            except:
                pass
    if len(args) == 1 and (
        not mirror_message or mirror_message.message_id not in keys
    ):
        msg = f"Reply to active <code>/{BotCommands.MirrorCommand}</code> message which was used to start the download or send <code>/{BotCommands.CancelMirror} GID</code> to cancel it!"
        sendMessage(msg, context.bot, update)
        return
    if dl.status() == MirrorStatus.STATUS_ARCHIVING:
        sendMessage("Archival in Progress, You Can't Cancel It.", context.bot, update)
    elif dl.status() == MirrorStatus.STATUS_EXTRACTING:
        sendMessage("Extract in Progress, You Can't Cancel It.", context.bot, update)
    elif dl.status() == MirrorStatus.STATUS_SPLITTING:
        sendMessage("Split in Progress, You Can't Cancel It.", context.bot, update)
    else:
        dl.download().cancel_download()
        sleep(3)  # incase of any error with ondownloaderror listener
        clean_download(f'{DOWNLOAD_DIR}{mirror_message.message_id}')


def cancel_all(update, context):
    count = 0
    gid = 0
    while True:
        dl = getAllDownload()
        if dl:
            if dl.gid() != gid:
                gid = dl.gid()
                dl.download().cancel_download()
                count += 1
                sleep(0.3)
        else:
            break
    sendMessage(f'{count} Download(s) has been Cancelled!', context.bot, update)



cancel_mirror_handler = CommandHandler(BotCommands.CancelMirror, cancel_mirror,
                                       filters=(CustomFilters.authorized_chat | CustomFilters.authorized_user) & CustomFilters.mirror_owner_filter | CustomFilters.sudo_user, run_async=True)
cancel_all_handler = CommandHandler(BotCommands.CancelAllCommand, cancel_all,
                                    filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
dispatcher.add_handler(cancel_all_handler)
dispatcher.add_handler(cancel_mirror_handler)
