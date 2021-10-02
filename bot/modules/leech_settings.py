# Implement By - @anasty17 (https://github.com/SlamDevs/slam-mirrorbot/commit/d888a1e7237f4633c066f7c2bbfba030b83ad616)
# (c) https://github.com/SlamDevs/slam-mirrorbot
# All rights reserved

import os
import threading

from PIL import Image
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup

from bot import AS_DOC_USERS, AS_MEDIA_USERS, dispatcher, AS_DOCUMENT, app, AUTO_DELETE_MESSAGE_DURATION
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, auto_delete_message
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper import button_build


def leechSet(update, context):
    user_id = update.message.from_user.id
    path = f"Thumbnails/{user_id}.jpg"
    msg = f"Leech Type for {user_id} user is "
    if (
        user_id in AS_DOC_USERS
        or user_id not in AS_MEDIA_USERS
        and AS_DOCUMENT
    ):
        msg += "DOCUMENT"
    else:
        msg += "MEDIA"
    msg += "\nCustom Thumbnail "
    msg += "exists" if os.path.exists(path) else "not exists"
    buttons = button_build.ButtonMaker()
    buttons.sbutton("As Document", f"doc {user_id}")
    buttons.sbutton("As Media", f"med {user_id}")
    buttons.sbutton("Delete Thumbnail", f"thumb {user_id}")
    if AUTO_DELETE_MESSAGE_DURATION == -1:
        buttons.sbutton("Close", f"closeset {user_id}")
    button = InlineKeyboardMarkup(buttons.build_menu(2))
    choose_msg = sendMarkup(msg, context.bot, update, button)
    threading.Thread(target=auto_delete_message, args=(context.bot, update.message, choose_msg)).start()

def setLeechType(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split(" ")
    if user_id != int(data[1]):
        query.answer(text="Not Yours!", show_alert=True)
    elif data[0] == "doc":
        if (
            user_id in AS_DOC_USERS
            or user_id not in AS_MEDIA_USERS
            and AS_DOCUMENT
        ):
            query.answer(text="Already As Document!", show_alert=True)
        elif user_id in AS_MEDIA_USERS:
            AS_MEDIA_USERS.remove(user_id)
            AS_DOC_USERS.add(user_id)
            query.answer(text="Done!", show_alert=True)
        else:
            AS_DOC_USERS.add(user_id)
            query.answer(text="Done!", show_alert=True)
    elif data[0] == "med":
        if user_id in AS_DOC_USERS:
            AS_DOC_USERS.remove(user_id)
            AS_MEDIA_USERS.add(user_id)
            query.answer(text="Done!", show_alert=True)
        elif user_id in AS_MEDIA_USERS or not AS_DOCUMENT:
            query.answer(text="Already As Media!", show_alert=True)
        else:
            AS_MEDIA_USERS.add(user_id)
            query.answer(text="Done!", show_alert=True)
    elif data[0] == "thumb":
        path = f"Thumbnails/{user_id}.jpg"
        if os.path.lexists(path):
            os.remove(path)
            query.answer(text="Done!", show_alert=True)
        else:
            query.answer(text="No Thumbnail To Delete!", show_alert=True)
    elif data[0] == "closeset":
        query.message.delete()

def setThumb(update, context):
    user_id = update.message.from_user.id
    reply_to = update.message.reply_to_message
    if reply_to is not None and reply_to.photo:
        path = "Thumbnails"
        if not os.path.exists(path):
            os.mkdir(path)
        photo_msg = app.get_messages(update.message.chat.id, reply_to_message_ids=update.message.message_id)
        photo_dir = app.download_media(photo_msg, file_name=path)
        des_dir = os.path.join(path, str(user_id) + ".jpg")
        # Image.open(photo_dir).convert("RGB").save(photo_dir)
        img = Image.open(photo_dir)
        img.thumbnail((480, 320))
        # img.resize((480, 320))
        img.save(des_dir, "JPEG")
        os.remove(photo_dir)
        sendMessage(f"Custom thumbnail saved for <code>{user_id}</code> user.", context.bot, update)
    else:
        sendMessage("Reply to a photo to save custom thumbnail.", context.bot, update)

leech_set_handler = CommandHandler(BotCommands.LeechSetCommand, leechSet, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
set_thumbnail_handler = CommandHandler(BotCommands.SetThumbCommand, setThumb, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
as_doc_handler = CallbackQueryHandler(setLeechType, pattern="doc", run_async=True)
as_media_handler = CallbackQueryHandler(setLeechType, pattern="med", run_async=True)
del_thumb_handler = CallbackQueryHandler(setLeechType, pattern="thumb", run_async=True)
close_set_handler = CallbackQueryHandler(setLeechType, pattern="closeset", run_async=True)
dispatcher.add_handler(leech_set_handler)
dispatcher.add_handler(as_doc_handler)
dispatcher.add_handler(as_media_handler)
dispatcher.add_handler(close_set_handler)
dispatcher.add_handler(set_thumbnail_handler)
dispatcher.add_handler(del_thumb_handler)
