from telegram.error import BadRequest
from telegram.message import Message
from telegram.update import Update


def sendMessage(text: str, context, update: Update):
    return context.bot.send_message(update.message.chat_id,
                                    reply_to_message_id=update.message.message_id,
                                    text=text, parse_mode='HTMl')


def editMessage(text: str, context, message: Message):
    try:
        context.bot.edit_message_text(text=text, message_id=message.message_id,
                                      chat_id=message.chat.id,
                                      parse_mode='HTMl')
    except BadRequest:
        pass


def deleteMessage(context, message: Message):
    context.bot.delete_message(chat_id=message.chat.id,
                               message_id=message.message_id)
