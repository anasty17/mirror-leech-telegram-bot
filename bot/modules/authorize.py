from pyrogram.filters import command
from pyrogram.handlers import MessageHandler

from bot import user_data, config_dict, bot
from ..helper.ext_utils.bot_utils import update_user_ldata, handler_new_task
from ..helper.ext_utils.db_handler import database
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import send_message


@handler_new_task
async def authorize(_, message):
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
    else:
        id_ = message.chat.id
    if id_ in user_data and user_data[id_].get("is_auth"):
        msg = "Already Authorized!"
    else:
        update_user_ldata(id_, "is_auth", True)
        if config_dict["DATABASE_URL"]:
            await database.update_user_data(id_)
        msg = "Authorized"
    await send_message(message, msg)


@handler_new_task
async def unauthorize(_, message):
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
    else:
        id_ = message.chat.id
    if id_ not in user_data or user_data[id_].get("is_auth"):
        update_user_ldata(id_, "is_auth", False)
        if config_dict["DATABASE_URL"]:
            await database.update_user_data(id_)
        msg = "Unauthorized"
    else:
        msg = "Already Unauthorized!"
    await send_message(message, msg)


@handler_new_task
async def addSudo(_, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
    if id_:
        if id_ in user_data and user_data[id_].get("is_sudo"):
            msg = "Already Sudo!"
        else:
            update_user_ldata(id_, "is_sudo", True)
            if config_dict["DATABASE_URL"]:
                await database.update_user_data(id_)
            msg = "Promoted as Sudo"
    else:
        msg = "Give ID or Reply To message of whom you want to Promote."
    await send_message(message, msg)


@handler_new_task
async def removeSudo(_, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
    if id_ and id_ not in user_data or user_data[id_].get("is_sudo"):
        update_user_ldata(id_, "is_sudo", False)
        if config_dict["DATABASE_URL"]:
            await database.update_user_data(id_)
        msg = "Demoted"
    else:
        msg = "Give ID or Reply To message of whom you want to remove from Sudo"
    await send_message(message, msg)


bot.add_handler(
    MessageHandler(
        authorize,
        filters=command(BotCommands.AuthorizeCommand, case_sensitive=True)
        & CustomFilters.sudo,
    )
)
bot.add_handler(
    MessageHandler(
        unauthorize,
        filters=command(BotCommands.UnAuthorizeCommand, case_sensitive=True)
        & CustomFilters.sudo,
    )
)
bot.add_handler(
    MessageHandler(
        addSudo,
        filters=command(BotCommands.AddSudoCommand, case_sensitive=True)
        & CustomFilters.sudo,
    )
)
bot.add_handler(
    MessageHandler(
        removeSudo,
        filters=command(BotCommands.RmSudoCommand, case_sensitive=True)
        & CustomFilters.sudo,
    )
)
