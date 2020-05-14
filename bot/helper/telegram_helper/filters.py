from telegram.ext import BaseFilter
from telegram import Message
from bot import AUTHORIZED_CHATS, OWNER_ID, download_dict, download_dict_lock


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

    class _MirrorOwner(BaseFilter):
        def filter(self, message: Message):
            user_id = message.from_user.id
            if user_id == OWNER_ID:
                return True
            args = str(message.text).split(' ')
            if len(args) > 1:
                # Cancelling by gid
                with download_dict_lock:
                    for message_id, status in download_dict.items():
                        if status.gid == args[1] and status.message.from_user.id == user_id:
                            return True
                    else:
                        return False
            # Cancelling by replying to original mirror message
            reply_user = message.reply_to_message.from_user.id
            return bool(reply_user == user_id)
    mirror_owner_filter = _MirrorOwner()
