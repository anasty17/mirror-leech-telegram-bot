from telegram.ext import CommandHandler

from bot import user_data, dispatcher, DB_URI
from bot.helper.telegram_helper.message_utils import sendMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.ext_utils.bot_utils import update_user_ldata


def authorize(update, context):
    reply_message = update.message.reply_to_message
    if len(context.args) == 1:
        id_ = int(context.args[0])
    elif reply_message:
        id_ = reply_message.from_user.id
    else:
        id_ = update.effective_chat.id
    if id_ in user_data and user_data[id_].get('is_auth'):
        msg = 'Already Authorized!'
    else:
        update_user_ldata(id_, 'is_auth', True)
        if DB_URI:
            DbManger().update_user_data(id_)
        msg = 'Authorized'
    sendMessage(msg, context.bot, update.message)

def unauthorize(update, context):
    reply_message = update.message.reply_to_message
    if len(context.args) == 1:
        id_ = int(context.args[0])
    elif reply_message:
        id_ = reply_message.from_user.id
    else:
        id_ = update.effective_chat.id
    if id_ not in user_data or user_data[id_].get('is_auth'):
        update_user_ldata(id_, 'is_auth', False)
        if DB_URI:
            DbManger().update_user_data(id_)
        msg = 'Unauthorized'
    else:
        msg = 'Already Unauthorized!'
    sendMessage(msg, context.bot, update.message)

def addSudo(update, context):
    id_ = ""
    reply_message = update.message.reply_to_message
    if len(context.args) == 1:
        id_ = int(context.args[0])
    elif reply_message:
        id_ = reply_message.from_user.id
    if id_:
        if id_ in user_data and user_data[id_].get('is_sudo'):
            msg = 'Already Sudo!'
        else:
            update_user_ldata(id_, 'is_sudo', True)
            if DB_URI:
                DbManger().update_user_data(id_)
            msg = 'Promoted as Sudo'
    else:
        msg = "Give ID or Reply To message of whom you want to Promote."
    sendMessage(msg, context.bot, update.message)

def removeSudo(update, context):
    id_ = ""
    reply_message = update.message.reply_to_message
    if len(context.args) == 1:
        id_ = int(context.args[0])
    elif reply_message:
        id_ = reply_message.from_user.id
    if id_ and id_ not in user_data or user_data[id_].get('is_sudo'):
        update_user_ldata(id_, 'is_sudo', False)
        if DB_URI:
            DbManger().update_user_data(id_)
        msg = 'Demoted'
    else:
        msg = "Give ID or Reply To message of whom you want to remove from Sudo"
    sendMessage(msg, context.bot, update.message)


authorize_handler = CommandHandler(BotCommands.AuthorizeCommand, authorize,
                                   filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
unauthorize_handler = CommandHandler(BotCommands.UnAuthorizeCommand, unauthorize,
                                   filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
addsudo_handler = CommandHandler(BotCommands.AddSudoCommand, addSudo,
                                   filters=CustomFilters.owner_filter, run_async=True)
removesudo_handler = CommandHandler(BotCommands.RmSudoCommand, removeSudo,
                                   filters=CustomFilters.owner_filter, run_async=True)

dispatcher.add_handler(authorize_handler)
dispatcher.add_handler(unauthorize_handler)
dispatcher.add_handler(addsudo_handler)
dispatcher.add_handler(removesudo_handler)
