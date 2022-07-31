from telegram.ext import CommandHandler, CallbackQueryHandler

from bot import aria2, BASE_URL, download_dict, dispatcher, download_dict_lock, SUDO_USERS, OWNER_ID
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, sendStatusMessage
from bot.helper.ext_utils.bot_utils import getDownloadByGid, MirrorStatus, bt_selection_buttons

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
        msg = "Reply to an active /cmd which was used to start the qb-download or add gid along with cmd\n\n"
        msg += "This command mainly for selection incase you decided to select files from already added torrent. "
        msg += "But you can always use /cmd with arg `s` to select files before download start."
        sendMessage(msg, context.bot, update.message)
        return

    if OWNER_ID != user_id and dl.message.from_user.id != user_id and user_id not in SUDO_USERS:
        sendMessage("This task is not for you!", context.bot, update.message)
        return
    if dl.status() not in [MirrorStatus.STATUS_DOWNLOADING, MirrorStatus.STATUS_PAUSED, MirrorStatus.STATUS_WAITING]:
        sendMessage('Task should be in downloading status or in pause status incase message deleted by wrong or in queued status incase you used torrent file!', context.bot, update.message)
        return
    if dl.name().startswith('[METADATA]'):
        sendMessage('Try after downloading metadata finished!', context.bot, update.message)
        return

    try:
        if dl.listener().isQbit:
            id_ = dl.download().ext_hash
            client = dl.client()
            client.torrents_pause(torrent_hashes=id_)
            dl.download().select = True
        else:
            id_ = dl.gid()
            aria2.client.force_pause(id_)
    except:
        sendMessage("This is not a bittorrent task!", context.bot, update.message)
        return

    SBUTTONS = bt_selection_buttons(id_)
    msg = "Your download paused. Choose files then press Done Selecting button to resume downloading."
    sendMarkup(msg, context.bot, update.message, SBUTTONS)

def get_confirm(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split()
    dl = getDownloadByGid(data[2])
    if not dl:
        query.answer(text="This task has been cancelled!", show_alert=True)
        query.message.delete()
    elif user_id != dl.listener().message.from_user.id:
        query.answer(text="This task is not for you!", show_alert=True)
    elif data[1] == "pin":
        query.answer(text=data[3], show_alert=True)
    elif data[1] == "done":
        query.answer()
        id_ = data[3]
        if len(id_) > 20:
            dl.client().torrents_resume(torrent_hashes=id_)
        else:
            aria2.client.unpause(id_)
        sendStatusMessage(dl.listener().message, dl.listener().bot)
        query.message.delete()


select_handler = CommandHandler(BotCommands.BtSelectCommand, select,
                                filters=(CustomFilters.authorized_chat | CustomFilters.authorized_user), run_async=True)
bts_handler = CallbackQueryHandler(get_confirm, pattern="btsel", run_async=True)
dispatcher.add_handler(select_handler)
dispatcher.add_handler(bts_handler)
