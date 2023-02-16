#!/usr/bin/env python3
from pyrogram.filters import create

from bot import user_data, OWNER_ID


class CustomFilters:

    async def owner_filter(self, client, message):
        uid = message.from_user.id
        return uid == OWNER_ID

    owner = create(owner_filter)

    async def authorized_user(self, client, message):
        uid = message.from_user.id
        chat_id = message.chat.id
        return bool(uid == OWNER_ID or uid in user_data and (user_data[chat_id].get('is_auth', False) or
                       user_data[uid].get('is_auth', False) or user_data[uid].get('is_sudo', False)))

    authorized = create(authorized_user)

    async def sudo_user(self, client, message):
        uid = message.from_user.id
        return bool(uid == OWNER_ID or uid in user_data and user_data[uid].get('is_sudo'))

    sudo = create(sudo_user)

