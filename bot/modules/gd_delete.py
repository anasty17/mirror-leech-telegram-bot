from pyrogram.filters import command
from pyrogram.handlers import MessageHandler

from bot import bot, LOGGER
from ..helper.ext_utils.bot_utils import sync_to_async, new_task
from ..helper.ext_utils.links_utils import is_gdrive_link
from ..helper.mirror_leech_utils.gdrive_utils.delete import GoogleDriveDelete
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import auto_delete_message, send_message


@new_task
async def deletefile(_, message):
    args = message.text.split()
    user = message.from_user or message.sender_chat
    if len(args) > 1:
        link = args[1]
    elif reply_to := message.reply_to_message:
        link = reply_to.text.split(maxsplit=1)[0].strip()
    else:
        link = ""
    if is_gdrive_link(link):
        LOGGER.info(link)
        msg = await sync_to_async(GoogleDriveDelete().deletefile, link, user.id)
    else:
        msg = (
            "Send Gdrive link along with command or by replying to the link by command"
        )
    reply_message = await send_message(message, msg)
    await auto_delete_message(message, reply_message)


bot.add_handler(
    MessageHandler(
        deletefile,
        filters=command(BotCommands.DeleteCommand, case_sensitive=True)
        & CustomFilters.authorized,
    )
)
