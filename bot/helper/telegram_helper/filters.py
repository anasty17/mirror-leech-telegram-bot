from pyrogram.filters import create

from ... import user_data
from ...core.config_manager import Config


class CustomFilters:
    async def owner_filter(self, _, update):
        user = update.from_user or update.sender_chat
        uid = user.id
        return uid == Config.OWNER_ID

    owner = create(owner_filter)

    async def authorized_user(self, _, update):
        user = update.from_user or update.sender_chat
        uid = user.id
        chat_id = update.chat.id
        thread_id = update.message_thread_id if update.is_topic_message else None
        return bool(
            uid == Config.OWNER_ID
            or (
                uid in user_data
                and (
                    user_data[uid].get("is_auth", False)
                    or user_data[uid].get("is_sudo", False)
                )
            )
            or (
                chat_id in user_data
                and user_data[chat_id].get("is_auth", False)
                and (
                    thread_id is None
                    or thread_id in user_data[chat_id].get("thread_ids", [])
                )
            )
        )

    authorized = create(authorized_user)

    async def sudo_user(self, _, update):
        user = update.from_user or update.sender_chat
        uid = user.id
        return bool(
            uid == Config.OWNER_ID or uid in user_data and user_data[uid].get("is_sudo")
        )

    sudo = create(sudo_user)
