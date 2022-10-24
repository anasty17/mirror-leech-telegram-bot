from telegram.ext import MessageFilter
from telegram import Message
from bot import user_data, OWNER_ID


class CustomFilters:
    class __OwnerFilter(MessageFilter):
        def filter(self, message: Message):
            return message.from_user.id == OWNER_ID

    owner_filter = __OwnerFilter()

    class __AuthorizedUserFilter(MessageFilter):
        def filter(self, message: Message):
            uid = message.from_user.id
            return uid == OWNER_ID or uid in user_data and (user_data[uid].get('is_auth') or user_data[uid].get('is_sudo'))

    authorized_user = __AuthorizedUserFilter()

    class __AuthorizedChat(MessageFilter):
        def filter(self, message: Message):
            uid = message.chat.id
            return uid in user_data and user_data[uid].get('is_auth')

    authorized_chat = __AuthorizedChat()

    class __SudoUser(MessageFilter):
        def filter(self, message: Message):
            uid = message.from_user.id
            return uid in user_data and user_data[uid].get('is_sudo')

    sudo_user = __SudoUser()

    @staticmethod
    def owner_query(uid):
        return uid == OWNER_ID or uid in user_data and user_data[uid].get('is_sudo')
