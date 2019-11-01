from telegram.ext import BaseFilter
from bot import AUTHORIZED_CHATS, OWNER_ID


class CustomFilters:
    class _OwnerFilter(BaseFilter):
        def filter(self, message):
            return bool(message.from_user.id == OWNER_ID)

    owner_filter = _OwnerFilter()

    class _AuthorizedUserFilter(BaseFilter):
        def filter(self, message):
            id = message.from_user.id
            return bool(id in AUTHORIZED_CHATS or id == OWNER_ID)

    authorized_user = _AuthorizedUserFilter()

    class _AuthorizedChat(BaseFilter):
        def filter(self, message):
            return bool(message.chat.id in AUTHORIZED_CHATS)

    authorized_chat = _AuthorizedChat()
