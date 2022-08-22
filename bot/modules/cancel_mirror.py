from telegram.ext import CommandHandler, CallbackQueryHandler
from time import sleep
from threading import Thread

from bot import download_dict, dispatcher, download_dict_lock, SUDO_USERS, OWNER_ID, AUTO_DELETE_MESSAGE_DURATION
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, auto_delete_message
from bot.helper.ext_utils.bot_utils import getDownloadByGid, getAllDownload
from bot.helper.ext_utils.bot_utils import MirrorStatus
from bot.helper.telegram_helper import button_build


def cancel_mirror(update, context):
    user_id = update.message.from_user.id
    if len(context.args) == 1:
        gid = context.args[0]
        dl = getDownloadByGid(gid)
        if not dl:
            sendMessage(f"GID: <code>{gid}</code> Not Found.", context.bot, update.message)
            return
    elif update.message.reply_to_message:
        mirror_message = update.message.reply_to_message
        with download_dict_lock:
            if mirror_message.message_id in download_dict:
                dl = download_dict[mirror_message.message_id]
            else:
                dl = None
        if not dl:
            sendMessage("This is not an active task!", context.bot, update.message)
            return
    elif len(context.args) == 0:
        msg = f"Reply to an active Command message which was used to start the download" \
              f" or send <code>/{BotCommands.CancelMirror} GID</code> to cancel it!"
        sendMessage(msg, context.bot, update.message)
        return

    if OWNER_ID != user_id and dl.message.from_user.id != user_id and user_id not in SUDO_USERS:
        sendMessage("This task is not for you!", context.bot, update.message)
        return

    dl.download().cancel_download()

def cancel_all(status):
    gid = ''
    while dl := getAllDownload(status):
        if dl.gid() != gid:
            gid = dl.gid()
            dl.download().cancel_download()
            sleep(1)

def cancell_all_buttons(update, context):
    with download_dict_lock:
        count = len(download_dict)
    if count == 0:
        sendMessage("No active tasks!", context.bot, update.message)
        return
    buttons = button_build.ButtonMaker()
    buttons.sbutton("Downloading", f"canall {MirrorStatus.STATUS_DOWNLOADING}")
    buttons.sbutton("Uploading", f"canall {MirrorStatus.STATUS_UPLOADING}")
    buttons.sbutton("Seeding", f"canall {MirrorStatus.STATUS_SEEDING}")
    buttons.sbutton("Cloning", f"canall {MirrorStatus.STATUS_CLONING}")
    buttons.sbutton("Extracting", f"canall {MirrorStatus.STATUS_EXTRACTING}")
    buttons.sbutton("Archiving", f"canall {MirrorStatus.STATUS_ARCHIVING}")
    buttons.sbutton("Queued", f"canall {MirrorStatus.STATUS_WAITING}")
    buttons.sbutton("Paused", f"canall {MirrorStatus.STATUS_PAUSED}")
    buttons.sbutton("All", "canall all")
    if AUTO_DELETE_MESSAGE_DURATION == -1:
        buttons.sbutton("Close", "canall close")
    button = buttons.build_menu(2)
    can_msg = sendMarkup('Choose tasks to cancel.', context.bot, update.message, button)
    Thread(target=auto_delete_message, args=(context.bot, update.message, can_msg)).start()

def cancel_all_update(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split()
    if CustomFilters._owner_query(user_id):
        query.answer()
        query.message.delete()
        if data[1] == 'close':
            return
        cancel_all(data[1])
    else:
        query.answer(text="You don't have permission to use these buttons!", show_alert=True)



cancel_mirror_handler = CommandHandler(BotCommands.CancelMirror, cancel_mirror,
                                       filters=(CustomFilters.authorized_chat | CustomFilters.authorized_user), run_async=True)

cancel_all_handler = CommandHandler(BotCommands.CancelAllCommand, cancell_all_buttons,
                                    filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)

cancel_all_buttons_handler = CallbackQueryHandler(cancel_all_update, pattern="canall", run_async=True)

dispatcher.add_handler(cancel_all_handler)
dispatcher.add_handler(cancel_mirror_handler)
dispatcher.add_handler(cancel_all_buttons_handler)
