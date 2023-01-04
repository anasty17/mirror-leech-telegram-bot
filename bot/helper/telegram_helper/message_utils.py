from time import sleep, time
from telegram.error import RetryAfter
from pyrogram.errors import FloodWait
from io import BytesIO

from bot import config_dict, LOGGER, status_reply_dict, status_reply_dict_lock, Interval, bot, rss_session
from bot.helper.ext_utils.bot_utils import get_readable_message, setInterval


def sendMessage(text, bot, message, reply_markup=None):
    try:
        return bot.sendMessage(message.chat_id, reply_to_message_id=message.message_id,
                               text=text, reply_markup=reply_markup)
    except RetryAfter as r:
        LOGGER.warning(str(r))
        sleep(r.retry_after * 1.5)
        return sendMessage(text, bot, message, reply_markup)
    except Exception as e:
        LOGGER.error(str(e))
        return

def sendPhoto(text, bot, message, photo):
    try:
        return bot.sendPhoto(message.chat_id, photo, text, reply_to_message_id=message.message_id)
    except RetryAfter as r:
        LOGGER.warning(str(r))
        sleep(r.retry_after * 1.5)
        return sendPhoto(text, bot, message, photo)
    except Exception as e:
        LOGGER.error(str(e))
        return

def editMessage(text, message, reply_markup=None):
    try:
        bot.editMessageText(text=text, message_id=message.message_id, chat_id=message.chat.id, reply_markup=reply_markup)
    except RetryAfter as r:
        LOGGER.warning(str(r))
        sleep(r.retry_after * 1.5)
        return editMessage(text, message, reply_markup)
    except Exception as e:
        LOGGER.error(str(e))
        return str(e)

def sendRss(text, bot):
    if not rss_session:
        try:
            return bot.sendMessage(config_dict['RSS_CHAT_ID'], text)
        except RetryAfter as r:
            LOGGER.warning(str(r))
            sleep(r.retry_after * 1.5)
            return sendRss(text, bot)
        except Exception as e:
            LOGGER.error(str(e))
            return
    else:
        try:
            with rss_session:
                return rss_session.send_message(config_dict['RSS_CHAT_ID'], text, disable_web_page_preview=True)
        except FloodWait as e:
            LOGGER.warning(str(e))
            sleep(e.value * 1.5)
            return sendRss(text, bot)
        except Exception as e:
            LOGGER.error(str(e))
            return

def deleteMessage(bot, message):
    try:
        bot.deleteMessage(chat_id=message.chat.id, message_id=message.message_id)
    except:
        pass

def sendLogFile(bot, message):
    with open('log.txt', 'rb') as f:
        bot.sendDocument(document=f, filename=f.name, reply_to_message_id=message.message_id,
                         chat_id=message.chat_id)

def sendFile(bot, message, txt, fileName, caption=""):
    try:
        with BytesIO(str.encode(txt)) as document:
            document.name = fileName
            return bot.sendDocument(document=document, reply_to_message_id=message.message_id,
                                    caption=caption, chat_id=message.chat_id)
    except RetryAfter as r:
        LOGGER.warning(str(r))
        sleep(r.retry_after * 1.5)
        return sendFile(bot, message, txt, fileName, caption)
    except Exception as e:
        LOGGER.error(str(e))
        return

def auto_delete_message(bot, cmd_message=None, bot_message=None):
    if config_dict['AUTO_DELETE_MESSAGE_DURATION'] != -1:
        sleep(config_dict['AUTO_DELETE_MESSAGE_DURATION'])
        if cmd_message is not None:
            deleteMessage(bot, cmd_message)
        if bot_message is not None:
            deleteMessage(bot, bot_message)

def delete_all_messages():
    with status_reply_dict_lock:
        for data in list(status_reply_dict.values()):
            try:
                deleteMessage(bot, data[0])
                del status_reply_dict[data[0].chat.id]
            except Exception as e:
                LOGGER.error(str(e))

def update_all_messages(force=False):
    with status_reply_dict_lock:
        if not status_reply_dict or not Interval or (not force and time() - list(status_reply_dict.values())[0][1] < 3):
            return
        for chat_id in status_reply_dict:
            status_reply_dict[chat_id][1] = time()

    msg, buttons = get_readable_message()
    if msg is None:
        return
    with status_reply_dict_lock:
        for chat_id in status_reply_dict:
            if status_reply_dict[chat_id] and msg != status_reply_dict[chat_id][0].text:
                rmsg = editMessage(msg, status_reply_dict[chat_id][0], buttons)
                if rmsg == "Message to edit not found":
                    del status_reply_dict[chat_id]
                    return
                status_reply_dict[chat_id][0].text = msg
                status_reply_dict[chat_id][1] = time()

def sendStatusMessage(msg, bot):
    progress, buttons = get_readable_message()
    if progress is None:
        return
    with status_reply_dict_lock:
        if msg.chat.id in status_reply_dict:
            message = status_reply_dict[msg.chat.id][0]
            deleteMessage(bot, message)
            del status_reply_dict[msg.chat.id]
        message = sendMessage(progress, bot, msg, buttons)
        status_reply_dict[msg.chat.id] = [message, time()]
        if not Interval:
            Interval.append(setInterval(config_dict['STATUS_UPDATE_INTERVAL'], update_all_messages))
