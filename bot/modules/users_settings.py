from os import remove as osremove, path as ospath, mkdir
from PIL import Image
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from time import sleep, time
from functools import partial
from html import escape

from bot import user_data, dispatcher, config_dict, DATABASE_URL, IS_PREMIUM_USER, MAX_SPLIT_SIZE
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage, sendPhoto
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.ext_utils.bot_utils import update_user_ldata

handler_dict = {}

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

    buttons.sbutton("Leech Splits", f"userset {user_id} lss")
    if user_dict and user_dict.get('split_size'):
        split_size = user_dict['split_size']
    else:
        split_size = config_dict['LEECH_SPLIT_SIZE']

    if not user_dict and config_dict['EQUAL_SPLITS'] or user_dict and user_dict.get('equal_splits'):
        equal_splits = 'Enabled'
    else:
        equal_splits = 'Disabled'

    buttons.sbutton("YT-DLP Quality", f"userset {user_id} ytq")
    if user_dict and user_dict.get('yt_ql'):
        ytq = user_dict['yt_ql']
    elif config_dict['YT_DLP_QUALITY']:
        ytq = config_dict['YT_DLP_QUALITY']
    else:
        ytq = 'None'

    buttons.sbutton("Thumbnail", f"userset {user_id} sthumb")
    thumbmsg = "Exists" if ospath.exists(thumbpath) else "Not Exists"
    buttons.sbutton("Close", f"userset {user_id} close")
    text = f"<u>Settings for <a href='tg://user?id={user_id}'>{name}</a></u>\n"\
           f"Leech Type is <b>{ltype}</b>\n"\
           f"Custom Thumbnail <b>{thumbmsg}</b>\n"\
           f"Leech Split Size is <b>{split_size}</b>\n"\
           f"Equal Splits is <b>{equal_splits}</b>\n"\
           f"YT-DLP Quality is <b><code>{escape(ytq)}</code></b>"
    return text, buttons.build_menu(1)

def update_user_settings(message, from_user):
    msg, button = get_user_settings(from_user)
    editMessage(msg, message, button)

def user_settings(update, context):
    msg, button = get_user_settings(update.message.from_user)
    sendMessage(msg, context.bot, update.message, button)

def set_yt_quality(update, context, omsg):
    message = update.message
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = message.text
    update_user_ldata(user_id, 'yt_ql', value)
    update.message.delete()
    update_user_settings(omsg, message.from_user)
    if DATABASE_URL:
        DbManger().update_user_data(user_id)

def set_thumb(update, context, omsg):
    message = update.message
    user_id = message.from_user.id
    handler_dict[user_id] = False
    path = "Thumbnails/"
    if not ospath.isdir(path):
        mkdir(path)
    photo_dir = message.photo[-1].get_file().download()
    user_id = message.from_user.id
    des_dir = ospath.join(path, f'{user_id}.jpg')
    Image.open(photo_dir).convert("RGB").save(des_dir, "JPEG")
    osremove(photo_dir)
    update_user_ldata(user_id, 'thumb', des_dir)
    update.message.delete()
    update_user_settings(omsg, message.from_user)
    if DATABASE_URL:
        DbManger().update_thumb(user_id, des_dir)

def leech_split_size(update, context, omsg):
    message = update.message
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = min(int(message.text), MAX_SPLIT_SIZE)
    update_user_ldata(user_id, 'split_size', value)
    update.message.delete()
    update_user_settings(omsg, message.from_user)
    if DATABASE_URL:
        DbManger().update_user_data(user_id)

def edit_user_settings(update, context):
    query = update.callback_query
    message = query.message
    user_id = query.from_user.id
    data = query.data
    data = data.split()
    thumb_path = f"Thumbnails/{user_id}.jpg"
    user_dict = user_data.get(user_id, False)
    if user_id != int(data[1]):
        query.answer(text="Not Yours!", show_alert=True)
    elif data[2] == "doc":
        update_user_ldata(user_id, 'as_doc', True)
        query.answer()
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == "med":
        update_user_ldata(user_id, 'as_doc', False)
        query.answer()
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == 'vthumb':
        query.answer()
        handler_dict[user_id] = False
        sendPhoto(f"Thumbnail for <a href='tg://user?id={user_id}'>{query.from_user.full_name}</a>",
                   context.bot, message, open(thumb_path, 'rb'))
        update_user_settings(message, query.from_user)
    elif data[2] == "dthumb":
        handler_dict[user_id] = False
        if ospath.lexists(thumb_path):
            query.answer()
            osremove(thumb_path)
            update_user_ldata(user_id, 'thumb', '')
            update_user_settings(message, query.from_user)
            if DATABASE_URL:
                DbManger().update_thumb(user_id)
        else:
            query.answer(text="Old Settings", show_alert=True)
            update_user_settings(message, query.from_user)
    elif data[2] == "sthumb":
        query.answer()
        if handler_dict.get(user_id):
            handler_dict[user_id] = False
            sleep(0.5)
        start_time = time()
        handler_dict[user_id] = True
        buttons = ButtonMaker()
        if ospath.exists(thumb_path):
            buttons.sbutton("View Thumbnail", f"userset {user_id} vthumb")
            buttons.sbutton("Delete Thumbnail", f"userset {user_id} dthumb")
        buttons.sbutton("Back", f"userset {user_id} back")
        buttons.sbutton("Close", f"userset {user_id} close")
        editMessage('Send a photo to save it as custom thumbnail. Timeout: 60 sec', message, buttons.build_menu(1))
        partial_fnc = partial(set_thumb, omsg=message)
        photo_handler = MessageHandler(filters=Filters.photo & Filters.chat(message.chat.id) & Filters.user(user_id),
                                       callback=partial_fnc)
        dispatcher.add_handler(photo_handler)
        while handler_dict[user_id]:
            if time() - start_time > 60:
                handler_dict[user_id] = False
                update_user_settings(message, query.from_user)
        dispatcher.remove_handler(photo_handler)
    elif data[2] == 'ytq':
        query.answer()
        if handler_dict.get(user_id):
            handler_dict[user_id] = False
            sleep(0.5)
        start_time = time()
        handler_dict[user_id] = True
        buttons = ButtonMaker()
        buttons.sbutton("Back", f"userset {user_id} back")
        if user_dict and user_dict.get('yt_ql'):
            buttons.sbutton("Remove YT-DLP Quality", f"userset {user_id} rytq", 'header')
        buttons.sbutton("Close", f"userset {user_id} close")
        rmsg = f'''
Send YT-DLP Qaulity. Timeout: 60 sec
Examples:
1. <code>{escape('bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]')}</code> this will give 1080p-mp4.
2. <code>{escape('bv*[height<=720][ext=webm]+ba/b[height<=720]')}</code> this will give 720p-webm.
Check all available qualities options <a href="https://github.com/yt-dlp/yt-dlp#filtering-formats">HERE</a>.
        '''
        editMessage(rmsg, message, buttons.build_menu(1))
        partial_fnc = partial(set_yt_quality, omsg=message)
        value_handler = MessageHandler(filters=Filters.text & Filters.chat(message.chat.id) & Filters.user(user_id),
                                       callback=partial_fnc)
        dispatcher.add_handler(value_handler)
        while handler_dict[user_id]:
            if time() - start_time > 60:
                handler_dict[user_id] = False
                update_user_settings(message, query.from_user)
        dispatcher.remove_handler(value_handler)
    elif data[2] == 'rytq':
        query.answer()
        handler_dict[user_id] = False
        update_user_ldata(user_id, 'yt_ql', '')
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == 'lss':
        query.answer()
        if handler_dict.get(user_id):
            handler_dict[user_id] = False
            sleep(0.5)
        start_time = time()
        handler_dict[user_id] = True
        buttons = ButtonMaker()
        if user_dict and user_dict.get('split_size'):
            buttons.sbutton("Reset Split Size", f"userset {user_id} rlss")
        if not user_dict and config_dict['EQUAL_SPLITS'] or user_dict and user_dict.get('equal_splits'):
            buttons.sbutton("Disable Equal Splits", f"userset {user_id} esplits")
        else:
            buttons.sbutton("Enable Equal Splits", f"userset {user_id} esplits")
        buttons.sbutton("Back", f"userset {user_id} back")
        buttons.sbutton("Close", f"userset {user_id} close")
        editMessage(f'Send Leech split size in bytes. IS_PREMIUM_USER: {IS_PREMIUM_USER}. Timeout: 60 sec', message, buttons.build_menu(1))
        partial_fnc = partial(leech_split_size, omsg=message)
        size_handler = MessageHandler(filters=Filters.text & Filters.chat(message.chat.id) & Filters.user(user_id),
                                      callback=partial_fnc)
        dispatcher.add_handler(size_handler)
        while handler_dict[user_id]:
            if time() - start_time > 60:
                handler_dict[user_id] = False
                update_user_settings(message, query.from_user)
        dispatcher.remove_handler(size_handler)
    elif data[2] == 'rlss':
        query.answer()
        handler_dict[user_id] = False
        update_user_ldata(user_id, 'split_size', '')
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == 'esplits':
        query.answer()
        handler_dict[user_id] = False
        update_user_ldata(user_id, 'equal_splits', not bool(user_dict and user_dict.get('equal_splits')))
        update_user_settings(message, query.from_user)
        if DATABASE_URL:
            DbManger().update_user_data(user_id)
    elif data[2] == 'back':
        query.answer()
        handler_dict[user_id] = False
        update_user_settings(message, query.from_user)
    else:
        query.answer()
        handler_dict[user_id] = False
        query.message.delete()
        query.message.reply_to_message.delete()

def send_users_settings(update, context):
    msg = ''.join(f'<code>{u}</code>: {escape(str(d))}\n\n' for u, d in user_data.items())
    if msg:
        sendMessage(msg, context.bot, update.message)
    else:
        sendMessage('No users data!', context.bot, update.message)

users_settings_handler = CommandHandler(BotCommands.UsersCommand, send_users_settings,
                                            filters=CustomFilters.owner_filter | CustomFilters.sudo_user)
user_set_handler = CommandHandler(BotCommands.UserSetCommand, user_settings,
                                   filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
but_set_handler = CallbackQueryHandler(edit_user_settings, pattern="userset")

dispatcher.add_handler(user_set_handler)
dispatcher.add_handler(but_set_handler)
dispatcher.add_handler(users_settings_handler)

