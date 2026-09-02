from .. import user_data
from ..helper.ext_utils.bot_utils import update_user_ldata, new_task
from ..helper.ext_utils.db_handler import database
from ..helper.telegram_helper.message_utils import send_message


def _parse_target_arg(raw):
    """Parse `chat_id` or `chat_id|thread_id` command targets."""
    target = raw.strip()
    if not target:
        raise ValueError("Target ID cannot be empty")
    if "|" not in target:
        return int(target), None

    chat_part, thread_part = target.split("|", 1)
    if not chat_part or not thread_part:
        raise ValueError("Use chat_id|thread_id for topic authorization")
    return int(chat_part), int(thread_part)


def _reply_target(message):
    reply_to = message.reply_to_message
    if not reply_to or reply_to.id == message.message_thread_id:
        return None
    sender = reply_to.from_user or reply_to.sender_chat
    return sender.id if sender else None


async def _persist_user(chat_id):
    await database.update_user_data(chat_id)


@new_task
async def authorize(_, message):
    parts = message.text.split(maxsplit=1)
    thread_id = None
    try:
        if len(parts) > 1:
            chat_id, thread_id = _parse_target_arg(parts[1])
        elif (reply_target := _reply_target(message)) is not None:
            chat_id = reply_target
        else:
            chat_id = message.chat.id
            if message.topic_message:
                thread_id = message.message_thread_id

        data = user_data.get(chat_id, {})
        if data.get("AUTH"):
            if thread_id is None:
                msg = "Already Authorized!"
            else:
                thread_ids = data.setdefault("thread_ids", [])
                if thread_id in thread_ids:
                    msg = "Already Authorized!"
                else:
                    thread_ids.append(thread_id)
                    await _persist_user(chat_id)
                    msg = "Authorized"
        else:
            update_user_ldata(chat_id, "AUTH", True)
            if thread_id is not None:
                update_user_ldata(chat_id, "thread_ids", [thread_id])
            await _persist_user(chat_id)
            msg = "Authorized"
    except (TypeError, ValueError) as e:
        msg = f"Invalid target: {e}"
    except Exception as e:
        msg = f"Error: {e}"
    await send_message(message, msg)


@new_task
async def unauthorize(_, message):
    parts = message.text.split(maxsplit=1)
    thread_id = None
    try:
        if len(parts) > 1:
            chat_id, thread_id = _parse_target_arg(parts[1])
        elif (reply_target := _reply_target(message)) is not None:
            chat_id = reply_target
        else:
            chat_id = message.chat.id
            if message.topic_message:
                thread_id = message.message_thread_id

        data = user_data.get(chat_id, {})
        if data.get("AUTH"):
            if thread_id is not None:
                thread_ids = data.get("thread_ids", [])
                if thread_id not in thread_ids:
                    msg = "Topic is already unauthorized."
                else:
                    thread_ids.remove(thread_id)
                    await _persist_user(chat_id)
                    msg = "Unauthorized"
            else:
                update_user_ldata(chat_id, "AUTH", False)
                await _persist_user(chat_id)
                msg = "Unauthorized"
        else:
            msg = (
                "Already Unauthorized! Authorized chats added from config must be "
                "removed from config."
            )
    except (TypeError, ValueError) as e:
        msg = f"Invalid target: {e}"
    except Exception as e:
        msg = f"Error: {e}"
    await send_message(message, msg)


@new_task
async def add_sudo(_, message):
    id_ = None
    parts = message.text.split(maxsplit=1)
    try:
        if len(parts) > 1:
            id_ = int(parts[1].strip())
        elif (reply_target := _reply_target(message)) is not None:
            id_ = reply_target

        if id_ is None:
            msg = "Give an ID or reply to the user/chat you want to promote."
        elif user_data.get(id_, {}).get("SUDO"):
            msg = "Already Sudo!"
        else:
            update_user_ldata(id_, "SUDO", True)
            await _persist_user(id_)
            msg = "Promoted as Sudo"
    except (TypeError, ValueError) as e:
        msg = f"Invalid target: {e}"
    except Exception as e:
        msg = f"Error: {e}"
    await send_message(message, msg)


@new_task
async def remove_sudo(_, message):
    id_ = None
    parts = message.text.split(maxsplit=1)
    try:
        if len(parts) > 1:
            id_ = int(parts[1].strip())
        elif (reply_target := _reply_target(message)) is not None:
            id_ = reply_target

        if id_ is None:
            msg = "Give an ID or reply to the user/chat you want to demote."
        elif user_data.get(id_, {}).get("SUDO"):
            update_user_ldata(id_, "SUDO", False)
            await _persist_user(id_)
            msg = "Demoted"
        else:
            msg = (
                "Already Not Sudo! Sudo users added from config must be removed "
                "from config."
            )
    except (TypeError, ValueError) as e:
        msg = f"Invalid target: {e}"
    except Exception as e:
        msg = f"Error: {e}"
    await send_message(message, msg)
