from .helper.message_utils import sendMessage
from telegram.ext import run_async
from bot import AUTHORIZED_CHATS, dispatcher
from telegram.ext import CommandHandler
from .helper.telegram_helper.filters import CustomFilters
from telegram.ext import Filters
from telegram import Update


@run_async
def authorize(update: Update, context):
    reply_message = update.message.reply_to_message
    with open('authorized_chats.txt', 'a') as file:
        if reply_message is None:
            chat_id = update.effective_chat.id
            if chat_id not in AUTHORIZED_CHATS:
                file.write(f'{chat_id}\n')
                AUTHORIZED_CHATS.append(chat_id)
                sendMessage('Chat authorized', context, update)
            else:
                sendMessage('Already authorized chat', context, update)
        else:
            user_id = reply_message.from_user.id
            if user_id not in AUTHORIZED_CHATS:
                file.write(f'{user_id}\n')
                AUTHORIZED_CHATS.append(user_id)


authorize_handler = CommandHandler(command='authorize', callback=authorize,
                                   filters=CustomFilters.owner_filter & Filters.group)
dispatcher.add_handler(authorize_handler)

