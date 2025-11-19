from re import compile as re_compile, I, S, escape
from pytdbot.types import Message

from ... import user_data, auth_chats, sudo_users
from ...core.config_manager import Config
from ...core.telegram_client import TgManager


class CustomFilters:

    def owner_filter(_, event, pattern=None):
        if pattern:
            match = pattern.match(event.text)
            if not match:
                return False
        return event.from_id == Config.OWNER_ID

    def authorized_user(_, event, pattern=None):
        if pattern:
            match = pattern.match(event.text)
            if not match:
                return False
        uid = event.from_id
        chat_id = event.chat_id
        thread_id = (
            event.topic_id.forum_topic_id
            if event.topic_id and event.topic_id.getType() == "messageTopicForum"
            else None
        )
        return bool(
            uid == Config.OWNER_ID
            or (
                uid in user_data
                and (
                    user_data[uid].get("AUTH", False)
                    or user_data[uid].get("SUDO", False)
                )
            )
            or (
                chat_id in user_data
                and user_data[chat_id].get("AUTH", False)
                and (
                    thread_id is None
                    or thread_id in user_data[chat_id].get("thread_ids", [])
                )
            )
            or uid in sudo_users
            or uid in auth_chats
            or chat_id in auth_chats
            and (
                auth_chats[chat_id]
                and thread_id
                and thread_id in auth_chats[chat_id]
                or not auth_chats[chat_id]
            )
        )

    def sudo_user(self, event, pattern=None):
        uid = event.from_id if isinstance(event, Message) else event.sender_user_id
        if pattern:
            match = pattern.match(event.text)
            if not match:
                return False
        return bool(
            uid == Config.OWNER_ID
            or uid in user_data
            and user_data[uid].get("SUDO")
            or uid in sudo_users
        )

    def public_user(self, event, pattern=None):
        if pattern:
            match = pattern.match(event.text)
            return bool(match)


def match_cmd(cmd):
    if not isinstance(cmd, list):
        return re_compile(rf"^/{cmd}(?:@{TgManager.NAME})?(?:\s+.*)?$", flags=I | S)
    pattern = "|".join(escape(c) for c in cmd)
    return re_compile(rf"^/({pattern})(?:@{TgManager.NAME})?(?:\s+.*)?$", flags=I | S)
