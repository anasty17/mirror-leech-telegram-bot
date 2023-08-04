#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command

from bot import bot
from bot.helper.mirror_utils.gdrive_utlis.count import gdCount
from bot.helper.telegram_helper.message_utils import deleteMessage, sendMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.bot_utils import is_gdrive_link, sync_to_async, new_task, get_readable_file_size


@new_task
async def countNode(_, message):
    args = message.text.split()
    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    link = args[1] if len(args) > 1 else ''
    if len(link) == 0 and (reply_to := message.reply_to_message):
        link = reply_to.text.split(maxsplit=1)[0].strip()

    if is_gdrive_link(link):
        msg = await sendMessage(message, f"Counting: <code>{link}</code>")
        name, mime_type, size, files, folders = await sync_to_async(gdCount().count, link, message.from_user.id)
        if mime_type is None:
            await sendMessage(message, name)
            return
        await deleteMessage(msg)
        msg = f'<b>Name: </b><code>{name}</code>'
        msg += f'\n\n<b>Size: </b>{get_readable_file_size(size)}'
        msg += f'\n\n<b>Type: </b>{mime_type}'
        if mime_type == 'Folder':
            msg += f'\n<b>SubFolders: </b>{folders}'
            msg += f'\n<b>Files: </b>{files}'
        msg += f'\n\n<b>cc: </b>{tag}'
    else:
        msg = 'Send Gdrive link along with command or by replying to the link by command'

    await sendMessage(message, msg)


bot.add_handler(MessageHandler(countNode, filters=command(
    BotCommands.CountCommand) & CustomFilters.authorized))
