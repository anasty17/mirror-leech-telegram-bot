from os import remove as osremove, path as ospath, mkdir
from threading import Thread
from PIL import Image
from telegram.ext import CommandHandler, CallbackQueryHandler

from bot import user_data, dispatcher, AS_DOCUMENT, DB_URI
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, editMessage, auto_delete_message
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper import button_build
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.ext_utils.bot_utils import update_user_ldata


def getleechinfo(from_user):
    user_id = from_user.id
    name = from_user.full_name
    buttons = button_build.ButtonMaker()
    thumbpath = f"Thumbnails/{user_id}.jpg"
    if user_id in user_data and (user_data[user_id].get('as_doc') or not user_data[user_id].get('as_media')) \
       and AS_DOCUMENT:
        ltype = "DOCUMENT"
        buttons.sbutton("Send As Media", f"leechset {user_id} med")
    else:
        ltype = "MEDIA"
        buttons.sbutton("Send As Document", f"leechset {user_id} doc")

    if ospath.exists(thumbpath):
        thumbmsg = "Exists"
        buttons.sbutton("Delete Thumbnail", f"leechset {user_id} thumb")
    else:
        thumbmsg = "Not Exists"

    buttons.sbutton("Close", f"leechset {user_id} close")
    button = buttons.build_menu(1)
    text = f"<u>Leech Settings for <a href='tg://user?id={user_id}'>{name}</a></u>\n"\
           f"Leech Type <b>{ltype}</b>\n"\
           f"Custom Thumbnail <b>{thumbmsg}</b>"
    return text, button

def editLeechType(message, query):
    msg, button = getleechinfo(query.from_user)
    editMessage(msg, message, button)

def leechSet(update, context):
    msg, button = getleechinfo(update.message.from_user)
    choose_msg = sendMarkup(msg, context.bot, update.message, button)
    Thread(target=auto_delete_message, args=(context.bot, update.message, choose_msg)).start()

def setLeechType(update, context):
    query = update.callback_query
    message = query.message
    user_id = query.from_user.id
    data = query.data
    data = data.split()
    if user_id != int(data[1]):
        query.answer(text="Not Yours!", show_alert=True)
    elif data[2] == "doc":
        if user_id in user_data and user_data[user_id].get('as_media'):
            update_user_ldata(user_id, 'as_media', False)
        update_user_ldata(user_id, 'as_doc', True)
        if DB_URI is not None:
            DbManger().update_user_data(user_id)
        query.answer(text="Your File Will Deliver As Document!", show_alert=True)
        editLeechType(message, query)
    elif data[2] == "med":
        if user_id in user_data and user_data[user_id].get('as_doc'):
            update_user_ldata(user_id, 'as_doc', False)
        update_user_ldata(user_id, 'as_media', True)
        if DB_URI is not None:
            DbManger().update_user_data(user_id)
        query.answer(text="Your File Will Deliver As Media!", show_alert=True)
        editLeechType(message, query)
    elif data[2] == "thumb":
        path = f"Thumbnails/{user_id}.jpg"
        if ospath.lexists(path):
            osremove(path)
            update_user_ldata(user_id, 'thumb', False)
            if DB_URI is not None:
                DbManger().update_thumb(user_id)
            query.answer(text="Thumbnail Removed!", show_alert=True)
            editLeechType(message, query)
        else:
            query.answer(text="Old Settings", show_alert=True)
    else:
        query.answer()
        query.message.delete()
        query.message.reply_to_message.delete()

def setThumb(update, context):
    user_id = update.message.from_user.id
    reply_to = update.message.reply_to_message
    if reply_to is not None and reply_to.photo:
        path = "Thumbnails/"
        if not ospath.isdir(path):
            mkdir(path)
        photo_dir = reply_to.photo[-1].get_file().download()
        des_dir = ospath.join(path, f'{user_id}.jpg')
        Image.open(photo_dir).convert("RGB").save(des_dir, "JPEG")
        osremove(photo_dir)
        update_user_ldata(user_id, 'thumb', True)
        if DB_URI is not None:
            DbManger().update_thumb(user_id, des_dir)
        msg = f"Custom thumbnail saved for {update.message.from_user.mention_html(update.message.from_user.first_name)}."
        sendMessage(msg, context.bot, update.message)
    else:
        sendMessage("Reply to a photo to save custom thumbnail.", context.bot, update.message)

def sendUsersSettings(update, context):
    msg = ''
    for u, d in user_data.items():
        msg += f'<code>{u}</code>: {d}'
    sendMessage(msg, context.bot, update.message)

users_settings_handler = CommandHandler(BotCommands.UsersCommand, sendUsersSettings,
                                            filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
leech_set_handler = CommandHandler(BotCommands.UserSetCommand, leechSet,
                                   filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
set_thumb_handler = CommandHandler(BotCommands.SetThumbCommand, setThumb,
                                   filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
but_set_handler = CallbackQueryHandler(setLeechType, pattern="leechset", run_async=True)

dispatcher.add_handler(leech_set_handler)
dispatcher.add_handler(but_set_handler)
dispatcher.add_handler(set_thumb_handler)
dispatcher.add_handler(users_settings_handler)

