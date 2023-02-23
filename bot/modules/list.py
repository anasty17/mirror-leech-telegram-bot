#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex

from bot import LOGGER, bot
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.bot_utils import sync_to_async, new_task


async def list_buttons(client, message):
    if len(message.text.split()) == 1:
        return await sendMessage(message, 'Send a search key along with command')
    user_id = message.from_user.id
    buttons = ButtonMaker()
    buttons.ibutton("Folders", f"list_types {user_id} folders")
    buttons.ibutton("Files", f"list_types {user_id} files")
    buttons.ibutton("Both", f"list_types {user_id} both")
    buttons.ibutton("Cancel", f"list_types {user_id} cancel")
    button = buttons.build_menu(2)
    await sendMessage(message, 'Choose option to list.', button)

async def _list_drive(key, message, item_type):
    LOGGER.info(f"listing: {key}")
    gdrive = GoogleDriveHelper()
    msg, button = await sync_to_async(gdrive.drive_list, key, isRecursive=True, itemType=item_type)
    if button:
        await editMessage(message, msg, button)
    else:
        await editMessage(message, f'No result found for <i>{key}</i>')

@new_task
async def select_type(client, query):
    user_id = query.from_user.id
    message = query.message
    key = message.reply_to_message.text.split(maxsplit=1)[1].strip()
    data = query.data.split()
    if user_id != int(data[1]):
        return await query.answer(text="Not Yours!", alert=True)
    elif data[2] == 'cancel':
        await query.answer()
        return await editMessage(message, "list has been canceled!")
    await query.answer()
    item_type = data[2]
    await editMessage(message, f"<b>Searching for <i>{key}</i></b>")
    await _list_drive(key, message, item_type)


bot.add_handler(MessageHandler(list_buttons, filters=command(BotCommands.ListCommand) & CustomFilters.authorized))
bot.add_handler(CallbackQueryHandler(select_type, filters=regex("^list_types")))
