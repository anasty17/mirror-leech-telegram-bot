#!/usr/bin/env python3
from asyncio import sleep
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex

from bot import download_dict, bot, download_dict_lock, OWNER_ID, user_data
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, auto_delete_message
from bot.helper.ext_utils.bot_utils import getDownloadByGid, getAllDownload, MirrorStatus, new_task
from bot.helper.telegram_helper import button_build


async def cancel_mirror(client, message):
    user_id = message.from_user.id
    msg = message.text.split()
    if len(msg) > 1:
        gid = msg[1]
        dl = await getDownloadByGid(gid)
        if not dl:
            await sendMessage(message, f"GID: <code>{gid}</code> Not Found.")
            return
    elif reply_to_id := message.reply_to_message_id:
        omsg_id = reply_to_id
        async with download_dict_lock:
            dl = download_dict.get(omsg_id, None)
        if not dl:
            await sendMessage(message, "This is not an active task!")
            return
    elif len(msg) == 1:
        msg = "Reply to an active Command message which was used to start the download" \
              f" or send <code>/{BotCommands.CancelMirror} GID</code> to cancel it!"
        await sendMessage(message, msg)
        return

    if OWNER_ID != user_id and dl.message.from_user.id != user_id and \
       (user_id not in user_data or not user_data[user_id].get('is_sudo')):
        await sendMessage(message, "This task is not for you!")
        return
    obj = dl.download()
    await obj.cancel_download()

@new_task
async def cancel_all(status):
    gid = ''
    while dl := await getAllDownload(status):
        if dl.gid() != gid:
            gid = dl.gid()
            obj = dl.download()
            await obj.cancel_download()
            await sleep(1)

@new_task
async def cancell_all_buttons(client, message):
    async with download_dict_lock:
        count = len(download_dict)
    if count == 0:
        await sendMessage(message, "No active tasks!")
        return
    buttons = button_build.ButtonMaker()
    buttons.ibutton("Downloading", f"canall {MirrorStatus.STATUS_DOWNLOADING}")
    buttons.ibutton("Uploading", f"canall {MirrorStatus.STATUS_UPLOADING}")
    buttons.ibutton("Seeding", f"canall {MirrorStatus.STATUS_SEEDING}")
    buttons.ibutton("Cloning", f"canall {MirrorStatus.STATUS_CLONING}")
    buttons.ibutton("Extracting", f"canall {MirrorStatus.STATUS_EXTRACTING}")
    buttons.ibutton("Archiving", f"canall {MirrorStatus.STATUS_ARCHIVING}")
    buttons.ibutton("QueuedDl", f"canall {MirrorStatus.STATUS_QUEUEDL}")
    buttons.ibutton("QueuedUp", f"canall {MirrorStatus.STATUS_QUEUEUP}")
    buttons.ibutton("Paused", f"canall {MirrorStatus.STATUS_PAUSED}")
    buttons.ibutton("All", "canall all")
    buttons.ibutton("Close", "canall close")
    button = buttons.build_menu(2)
    can_msg = await sendMessage(message, 'Choose tasks to cancel.', button)
    await auto_delete_message(message, can_msg)

@new_task
async def cancel_all_update(client, query):
    data = query.data.split()
    message = query.message
    await query.answer()
    if data[1] == 'close':
        await message.reply_to_message.delete()
        await message.delete()
    else:
        await cancel_all(data[1])


bot.add_handler(MessageHandler(cancel_mirror, filters=command(BotCommands.CancelMirror) & CustomFilters.authorized))
bot.add_handler(MessageHandler(cancell_all_buttons, filters=command(BotCommands.CancelAllCommand) & CustomFilters.sudo))
bot.add_handler(CallbackQueryHandler(cancel_all_update, filters=regex("^canall") & CustomFilters.sudo))