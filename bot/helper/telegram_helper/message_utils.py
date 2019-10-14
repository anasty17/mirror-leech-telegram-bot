from telegram.message import Message
from telegram.update import Update
import time
from bot import AUTO_DELETE_MESSAGE_DURATION


def sendMessage(text: str, context, update: Update):
    return context.bot.send_message(update.message.chat_id,
                                    reply_to_message_id=update.message.message_id,
                                    text=text, parse_mode='HTMl')


def editMessage(text: str, context, message: Message):
    context.bot.edit_message_text(text=text, message_id=message.message_id,
                                  chat_id=message.chat.id,
                                  parse_mode='HTMl')


def deleteMessage(context, message: Message):
    context.bot.delete_message(chat_id=message.chat.id,
                               message_id=message.message_id)


def sendLogFile(context, update: Update):
    with open('log.txt', 'rb') as f:
        context.bot.send_document(document=f, filename=f.name,
                                  reply_to_message_id=update.message.message_id,
                                  chat_id=update.message.chat_id)


def auto_delete_message(context, cmd_message: Message, bot_message: Message):
    if AUTO_DELETE_MESSAGE_DURATION != -1:
        time.sleep(AUTO_DELETE_MESSAGE_DURATION)
        try:
            # Skip if None is passed meaning we don't want to delete bot xor cmd message
            deleteMessage(context, cmd_message)
            deleteMessage(context, bot_message)
        except AttributeError:
            pass
