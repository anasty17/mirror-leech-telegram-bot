from bot import AUTHORIZED_CHATS, SUDO_USERS, dispatcher, DB_URI
from bot.helper.telegram_helper.message_utils import sendMessage
from telegram.ext import CommandHandler
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.db_handler import DbManger


def authorize(update, context):
    reply_message = update.message.reply_to_message
    if len(context.args) == 1:
        user_id = int(context.args[0])
        if user_id in AUTHORIZED_CHATS:
            msg = 'User Already Authorized!'
        elif DB_URI is not None:
            msg = DbManger().user_auth(user_id)
            AUTHORIZED_CHATS.add(user_id)
        else:
            AUTHORIZED_CHATS.add(user_id)
            msg = 'User Authorized'
    elif reply_message:
        # Trying to authorize someone by replying
        user_id = reply_message.from_user.id
        if user_id in AUTHORIZED_CHATS:
            msg = 'User Already Authorized!'
        elif DB_URI is not None:
            msg = DbManger().user_auth(user_id)
            AUTHORIZED_CHATS.add(user_id)
        else:
            AUTHORIZED_CHATS.add(user_id)
            msg = 'User Authorized'
    else:
        # Trying to authorize a chat
        chat_id = update.effective_chat.id
        if chat_id in AUTHORIZED_CHATS:
            msg = 'Chat Already Authorized!'
        elif DB_URI is not None:
            msg = DbManger().user_auth(chat_id)
            AUTHORIZED_CHATS.add(chat_id)
        else:
            AUTHORIZED_CHATS.add(chat_id)
            msg = 'Chat Authorized'
    sendMessage(msg, context.bot, update.message)

def unauthorize(update, context):
    reply_message = update.message.reply_to_message
    if len(context.args) == 1:
        user_id = int(context.args[0])
        if user_id in AUTHORIZED_CHATS:
            if DB_URI is not None:
                msg = DbManger().user_unauth(user_id)
            else:
                msg = 'User Unauthorized'
            AUTHORIZED_CHATS.remove(user_id)
        else:
            msg = 'User Already Unauthorized!'
    elif reply_message:
        # Trying to authorize someone by replying
        user_id = reply_message.from_user.id
        if user_id in AUTHORIZED_CHATS:
            if DB_URI is not None:
                msg = DbManger().user_unauth(user_id)
            else:
                msg = 'User Unauthorized'
            AUTHORIZED_CHATS.remove(user_id)
        else:
            msg = 'User Already Unauthorized!'
    else:
        # Trying to unauthorize a chat
        chat_id = update.effective_chat.id
        if chat_id in AUTHORIZED_CHATS:
            if DB_URI is not None:
                msg = DbManger().user_unauth(chat_id)
            else:
                msg = 'Chat Unauthorized'
            AUTHORIZED_CHATS.remove(chat_id)
        else:
            msg = 'Chat Already Unauthorized!'

    sendMessage(msg, context.bot, update.message)

def addSudo(update, context):
    reply_message = update.message.reply_to_message
    if len(context.args) == 1:
        user_id = int(context.args[0])
        if user_id in SUDO_USERS:
            msg = 'Already Sudo!'
        elif DB_URI is not None:
            msg = DbManger().user_addsudo(user_id)
            SUDO_USERS.add(user_id)
        else:
            SUDO_USERS.add(user_id)
            msg = 'Promoted as Sudo'
    elif reply_message:
        # Trying to authorize someone by replying
        user_id = reply_message.from_user.id
        if user_id in SUDO_USERS:
            msg = 'Already Sudo!'
        elif DB_URI is not None:
            msg = DbManger().user_addsudo(user_id)
            SUDO_USERS.add(user_id)
        else:
            SUDO_USERS.add(user_id)
            msg = 'Promoted as Sudo'
    else:
        msg = "Give ID or Reply To message of whom you want to Promote."
    sendMessage(msg, context.bot, update.message)

def removeSudo(update, context):
    reply_message = update.message.reply_to_message
    if len(context.args) == 1:
        user_id = int(context.args[0])
        if user_id in SUDO_USERS:
            if DB_URI is not None:
                msg = DbManger().user_rmsudo(user_id)
            else:
                msg = 'Demoted'
            SUDO_USERS.remove(user_id)
        else:
            msg = 'Not sudo user to demote!'
    elif reply_message:
        user_id = reply_message.from_user.id
        if user_id in SUDO_USERS:
            if DB_URI is not None:
                msg = DbManger().user_rmsudo(user_id)
            else:
                msg = 'Demoted'
            SUDO_USERS.remove(user_id)
        else:
            msg = 'Not sudo user to demote!'
    else:
        msg = "Give ID or Reply To message of whom you want to remove from Sudo"
    sendMessage(msg, context.bot, update.message)

def sendAuthChats(update, context):
    user = sudo = ''
    user += '\n'.join(f"<code>{uid}</code>" for uid in AUTHORIZED_CHATS)
    sudo += '\n'.join(f"<code>{uid}</code>" for uid in SUDO_USERS)
    sendMessage(f'<b><u>Authorized Chats:</u></b>\n{user}\n<b><u>Sudo Users:</u></b>\n{sudo}', context.bot, update.message)


send_auth_handler = CommandHandler(command=BotCommands.AuthorizedUsersCommand, callback=sendAuthChats,
                                    filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
authorize_handler = CommandHandler(command=BotCommands.AuthorizeCommand, callback=authorize,
                                    filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
unauthorize_handler = CommandHandler(command=BotCommands.UnAuthorizeCommand, callback=unauthorize,
                                    filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
addsudo_handler = CommandHandler(command=BotCommands.AddSudoCommand, callback=addSudo,
                                    filters=CustomFilters.owner_filter, run_async=True)
removesudo_handler = CommandHandler(command=BotCommands.RmSudoCommand, callback=removeSudo,
                                    filters=CustomFilters.owner_filter, run_async=True)

dispatcher.add_handler(send_auth_handler)
dispatcher.add_handler(authorize_handler)
dispatcher.add_handler(unauthorize_handler)
dispatcher.add_handler(addsudo_handler)
dispatcher.add_handler(removesudo_handler)
