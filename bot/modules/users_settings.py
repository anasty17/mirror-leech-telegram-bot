from os import remove as osremove, path as ospath, mkdir
from threading import Thread
from PIL import Image
from telegram.ext import CommandHandler, CallbackQueryHandler

from bot import user_data, dispatcher, config_dict, DB_URI
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, editMessage, auto_delete_message
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.ext_utils.bot_utils import update_user_ldata


def get_user_settings(from_user):
    user_id = from_user.id
    name = from_user.full_name
    buttons = ButtonMaker()
    thumbpath = f"Thumbnails/{user_id}.jpg"
    user_dict = user_data.get(user_id, False)
    if not user_dict and config_dict['AS_DOCUMENT'] or user_dict and user_dict.get('as_doc'):
        ltype = "DOCUMENT"
        buttons.sbutton("Send As Media", f"userset {user_id} med")
    else:
        ltype = "MEDIA"
        buttons.sbutton("Send As Document", f"userset {user_id} doc")

    if ospath.exists(thumbpath):
        thumbmsg = "Exists"
        buttons.sbutton("Delete Thumbnail", f"userset {user_id} thumb")
    else:
        thumbmsg = "Not Exists"

    buttons.sbutton("Close", f"userset {user_id} close")
    button = buttons.build_menu(1)
    text = f"<u>Settings for <a href='tg://user?id={user_id}'>{name}</a></u>\n"\
           f"Leech Type <b>{ltype}</b>\n"\
           f"Custom Thumbnail <b>{thumbmsg}</b>"
    return text, button

def update_user_settings(message, query):
    msg, button = get_user_settings(query.from_user)
    editMessage(msg, message, button)

def user_settings(update, context):
    msg, button = get_user_settings(update.message.from_user)
    buttons_msg = sendMarkup(msg, context.bot, update.message, button)
    Thread(target=auto_delete_message, args=(context.bot, update.message, buttons_msg)).start()

def edit_user_settings(update, context):
    query = update.callback_query
    message = query.message
    user_id = query.from_user.id
    data = query.data
    data = data.split()
    if user_id != int(data[1]):
        query.answer(text="Not Yours!", show_alert=True)
    elif data[2] == "doc":
        update_user_ldata(user_id, 'as_doc', True)
        if DB_URI:
            DbManger().update_user_data(user_id)
        query.answer(text="Your File Will Deliver As Document!", show_alert=True)
        update_user_settings(message, query)
    elif data[2] == "med":
        update_user_ldata(user_id, 'as_doc', False)
        if DB_URI:
            DbManger().update_user_data(user_id)
        query.answer(text="Your File Will Deliver As Media!", show_alert=True)
        update_user_settings(message, query)
    elif data[2] == "thumb":
        path = f"Thumbnails/{user_id}.jpg"
        if ospath.lexists(path):
            osremove(path)
            update_user_ldata(user_id, 'thumb', '')
            if DB_URI:
                DbManger().update_thumb(user_id)
            query.answer(text="Thumbnail Removed!", show_alert=True)
            update_user_settings(message, query)
        else:
            query.answer(text="Old Settings", show_alert=True)
            update_user_settings(message, query)
    else:
        query.answer()
        query.message.delete()
        query.message.reply_to_message.delete()

def set_thumb(update, context):
    reply_to = update.message.reply_to_message
    if reply_to is not None and reply_to.photo:
        path = "Thumbnails/"
        if not ospath.isdir(path):
            mkdir(path)
        photo_dir = reply_to.photo[-1].get_file().download()
        user_id = update.message.from_user.id
        des_dir = ospath.join(path, f'{user_id}.jpg')
        Image.open(photo_dir).convert("RGB").save(des_dir, "JPEG")
        osremove(photo_dir)
        update_user_ldata(user_id, 'thumb', des_dir)
        if DB_URI:
            DbManger().update_thumb(user_id, des_dir)
        msg = f"Custom thumbnail saved for {update.message.from_user.mention_html(update.message.from_user.first_name)}."
        sendMessage(msg, context.bot, update.message)
    else:
        sendMessage("Reply to a photo to save custom thumbnail.", context.bot, update.message)

def send_users_settings(update, context):
    msg = ''.join(f'<code>{u}</code>: {d}\n' for u, d in user_data.items())
    sendMessage(msg, context.bot, update.message)

users_settings_handler = CommandHandler(BotCommands.UsersCommand, send_users_settings,
                                            filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
user_set_handler = CommandHandler(BotCommands.UserSetCommand, user_settings,
                                   filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
set_thumb_handler = CommandHandler(BotCommands.SetThumbCommand, set_thumb,
                                   filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
but_set_handler = CallbackQueryHandler(edit_user_settings, pattern="userset", run_async=True)

dispatcher.add_handler(user_set_handler)
dispatcher.add_handler(but_set_handler)
dispatcher.add_handler(set_thumb_handler)
dispatcher.add_handler(users_settings_handler)

