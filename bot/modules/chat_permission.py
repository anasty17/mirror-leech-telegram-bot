from .. import user_data
from ..helper.ext_utils.bot_utils import update_user_ldata, new_task
from ..helper.ext_utils.db_handler import database
from ..helper.telegram_helper.message_utils import send_message


@new_task
async def authorize(_, message):
    msg = message.text.split()
    thread_id = None
    if len(msg) > 1:
        if "|" in msg:
            chat_id, thread_id = list(map(int, msg[1].split("|")))
        else:
            chat_id = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        chat_id = (
            reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
        )
    else:
        if message.is_topic_message:
            thread_id = message.message_thread_id
        chat_id = message.chat.id
    if chat_id in user_data and user_data[chat_id].get("AUTH"):
        if (
            thread_id is not None
            and thread_id in user_data[chat_id].get("thread_ids", [])
            or thread_id is None
        ):
            msg = "Already Authorized!"
        else:
            if "thread_ids" in user_data[chat_id]:
                user_data[chat_id]["thread_ids"].append(thread_id)
            else:
                user_data[chat_id]["thread_ids"] = [thread_id]
            msg = "Authorized"
    else:
        update_user_ldata(chat_id, "AUTH", True)
        if thread_id is not None:
            update_user_ldata(chat_id, "thread_ids", [thread_id])
        await database.update_user_data(chat_id)
        msg = "Authorized"
    await send_message(message, msg)


@new_task
async def unauthorize(_, message):
    msg = message.text.split()
    thread_id = None
    if len(msg) > 1:
        if "|" in msg:
            chat_id, thread_id = list(map(int, msg[1].split("|")))
        else:
            chat_id = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        chat_id = (
            reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
        )
    else:
        if message.is_topic_message:
            thread_id = message.message_thread_id
        chat_id = message.chat.id
    if chat_id in user_data and user_data[chat_id].get("AUTH"):
        if thread_id is not None and thread_id in user_data[chat_id].get(
            "thread_ids", []
        ):
            user_data[chat_id]["thread_ids"].remove(thread_id)
        else:
            update_user_ldata(chat_id, "AUTH", False)
        await database.update_user_data(chat_id)
        msg = "Unauthorized"
    else:
        msg = "Already Unauthorized!"
    await send_message(message, msg)


@new_task
async def add_sudo(_, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
    if id_:
        if id_ in user_data and user_data[id_].get("SUDO"):
            msg = "Already Sudo!"
        else:
            update_user_ldata(id_, "SUDO", True)
            await database.update_user_data(id_)
            msg = "Promoted as Sudo"
    else:
        msg = "Give ID or Reply To message of whom you want to Promote."
    await send_message(message, msg)


@new_task
async def remove_sudo(_, message):
    id_ = ""
    msg = message.text.split()
    if len(msg) > 1:
        id_ = int(msg[1].strip())
    elif reply_to := message.reply_to_message:
        id_ = reply_to.from_user.id if reply_to.from_user else reply_to.sender_chat.id
    if id_ and id_ not in user_data or user_data[id_].get("SUDO"):
        update_user_ldata(id_, "SUDO", False)
        await database.update_user_data(id_)
        msg = "Demoted"
    else:
        msg = "Give ID or Reply To message of whom you want to remove from Sudo"
    await send_message(message, msg)
