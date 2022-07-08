from telegram import InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler

from bot import BASE_URL, download_dict, dispatcher, download_dict_lock, WEB_PINCODE, SUDO_USERS, OWNER_ID
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, sendStatusMessage
from bot.helper.ext_utils.bot_utils import getDownloadByGid, MirrorStatus
from bot.helper.telegram_helper import button_build

def select(update, context):
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
        msg = "Reply to an active /qbcmd which was used to start the qb-download or add gid along with cmd\n\n"
        msg += "This command mainly for selection incase you decided to select files from already added qb-torrent. "
        msg += "But you can always use /qbcmd with arg `s` to select files before download start."
        sendMessage(msg, context.bot, update.message)
        return

    if OWNER_ID != user_id and dl.message.from_user.id != user_id and user_id not in SUDO_USERS:
        sendMessage("This task is not for you!", context.bot, update.message)
        return

    if dl.status() != MirrorStatus.STATUS_DOWNLOADING:
        sendMessage('Task should be in downloading status!', context.bot, update.message)
        return
    try:
        hash_ = dl.download().ext_hash
        client = dl.client()
    except:
        sendMessage("This task not started from qBittorrent", context.bot, update.message)
        return

    client.torrents_pause(torrent_hashes=hash_)
    pincode = ""
    for n in str(hash_):
        if n.isdigit():
            pincode += str(n)
        if len(pincode) == 4:
            break
    buttons = button_build.ButtonMaker()
    gid = hash_[:12]
    if WEB_PINCODE:
        buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{hash_}")
        buttons.sbutton("Pincode", f"qbs pin {gid} {pincode}")
    else:
        buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{hash_}?pin_code={pincode}")
    buttons.sbutton("Done Selecting", f"qbs done {gid} {hash_}")
    QBBUTTONS = InlineKeyboardMarkup(buttons.build_menu(2))
    msg = "Your download paused. Choose files then press Done Selecting button to resume downloading."
    sendMarkup(msg, context.bot, update.message, QBBUTTONS)
    dl.download().select = True

def get_confirm(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split()
    qbdl = getDownloadByGid(data[2])
    if not qbdl:
        query.answer(text="This task has been cancelled!", show_alert=True)
        query.message.delete()
    elif user_id != qbdl.listener().message.from_user.id:
        query.answer(text="This task is not for you!", show_alert=True)
    elif data[1] == "pin":
        query.answer(text=data[3], show_alert=True)
    elif data[1] == "done":
        query.answer()
        qbdl.client().torrents_resume(torrent_hashes=data[3])
        sendStatusMessage(qbdl.listener().message, qbdl.listener().bot)
        query.message.delete()


select_handler = CommandHandler(BotCommands.QbSelectCommand, select,
                                filters=(CustomFilters.authorized_chat | CustomFilters.authorized_user), run_async=True)
qbs_handler = CallbackQueryHandler(get_confirm, pattern="qbs", run_async=True)
dispatcher.add_handler(select_handler)
dispatcher.add_handler(qbs_handler)
