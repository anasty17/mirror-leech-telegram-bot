from telegram.ext import CommandHandler, run_async
from bot import dispatcher, status_reply_dict, DOWNLOAD_STATUS_UPDATE_INTERVAL
from bot.helper.message_utils import *
from time import sleep
from bot.helper.bot_utils import get_readable_message
from telegram.error import BadRequest

@run_async
def mirror_status(update: Update, context):
    message = get_readable_message()
    if len(message) == 0:
        message = "No active downloads"
        sendMessage(message, context, update)
        return
    index = update.effective_chat.id
    if index in status_reply_dict.keys():
        deleteMessage(context, status_reply_dict[index])
        del status_reply_dict[index]
    kill_thread = False
    while len(message) != 0:
        message = get_readable_message()
        if index in status_reply_dict.keys():
            if len(message) == 0:
                message = "No active downloads"
                editMessage(message, context, status_reply_dict[index])
                break
            try:
                editMessage(message, context, status_reply_dict[index])
            except BadRequest:
                break
        else:
            # If the loop returns here 2nd time, it means the message
            # has been replaced by a new message due to a second /status command in the chat.
            # So we kill the thread by simply breaking the loop
            if kill_thread:
                break
            status_reply_dict[index] = sendMessage(message, context, update)
            kill_thread = True
        sleep(DOWNLOAD_STATUS_UPDATE_INTERVAL)


mirror_status_handler = CommandHandler('status', mirror_status)
dispatcher.add_handler(mirror_status_handler)
