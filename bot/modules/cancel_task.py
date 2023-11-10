from asyncio import sleep
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex

from bot import task_dict, bot, task_dict_lock, OWNER_ID, user_data, multi_tags
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    auto_delete_message,
    deleteMessage,
)
from bot.helper.ext_utils.status_utils import getTaskByGid, getAllTasks, MirrorStatus
from bot.helper.ext_utils.bot_utils import new_task
from bot.helper.telegram_helper import button_build


async def cancel_task(_, message):
    user_id = message.from_user.id if message.from_user else message.sender_chat.id
    msg = message.text.split()
    if len(msg) > 1:
        gid = msg[1]
        if len(gid) == 4:
            multi_tags.discard(gid)
            return
        else:
            task = await getTaskByGid(gid)
            if task is None:
                await sendMessage(message, f"GID: <code>{gid}</code> Not Found.")
                return
    elif reply_to_id := message.reply_to_message_id:
        async with task_dict_lock:
            task = task_dict.get(reply_to_id)
        if task is None:
            await sendMessage(message, "This is not an active task!")
            return
    elif len(msg) == 1:
        msg = (
            "Reply to an active Command message which was used to start the download"
            f" or send <code>/{BotCommands.CancelTaskCommand} GID</code> to cancel it!"
        )
        await sendMessage(message, msg)
        return
    if (
        OWNER_ID != user_id
        and task.listener.user_id != user_id
        and (user_id not in user_data or not user_data[user_id].get("is_sudo"))
    ):
        await sendMessage(message, "This task is not for you!")
        return
    obj = task.task()
    await obj.cancel_task()


async def cancel_multi(_, query):
    data = query.data.split()
    user_id = query.from_user.id
    if user_id != int(data[1]) and not await CustomFilters.sudo("", query):
        await query.answer("Not Yours!", show_alert=True)
        return
    tag = int(data[2])
    if tag in multi_tags:
        multi_tags.discard(int(data[2]))
        msg = "Stopped!"
    else:
        msg = "Already Stopped/Finished!"
    await query.answer(msg, show_alert=True)
    await deleteMessage(query.message)


async def cancel_all(status):
    matches = await getAllTasks(status)
    if not matches:
        return False
    for task in matches:
        obj = task.task()
        await obj.cancel_task()
        await sleep(2)
    return True


async def cancell_all_buttons(_, message):
    async with task_dict_lock:
        count = len(task_dict)
    if count == 0:
        await sendMessage(message, "No active tasks!")
        return
    buttons = button_build.ButtonMaker()
    buttons.ibutton("Downloading", f"canall {MirrorStatus.STATUS_DOWNLOADING}")
    buttons.ibutton("Uploading", f"canall {MirrorStatus.STATUS_UPLOADING}")
    buttons.ibutton("Seeding", f"canall {MirrorStatus.STATUS_SEEDING}")
    buttons.ibutton("Spltting", f"canall {MirrorStatus.STATUS_SPLITTING}")
    buttons.ibutton("Cloning", f"canall {MirrorStatus.STATUS_CLONING}")
    buttons.ibutton("Extracting", f"canall {MirrorStatus.STATUS_EXTRACTING}")
    buttons.ibutton("Archiving", f"canall {MirrorStatus.STATUS_ARCHIVING}")
    buttons.ibutton("QueuedDl", f"canall {MirrorStatus.STATUS_QUEUEDL}")
    buttons.ibutton("QueuedUp", f"canall {MirrorStatus.STATUS_QUEUEUP}")
    buttons.ibutton("Paused", f"canall {MirrorStatus.STATUS_PAUSED}")
    buttons.ibutton("All", "canall all")
    buttons.ibutton("Close", "canall close")
    button = buttons.build_menu(2)
    can_msg = await sendMessage(message, "Choose tasks to cancel.", button)
    await auto_delete_message(message, can_msg)


@new_task
async def cancel_all_update(_, query):
    data = query.data.split()
    message = query.message
    reply_to = message.reply_to_message
    await query.answer()
    if data[1] == "close":
        await deleteMessage(reply_to)
        await deleteMessage(message)
    else:
        res = await cancel_all(data[1])
        if not res:
            await sendMessage(reply_to, f"No matching tasks for {data[1]}!")


bot.add_handler(
    MessageHandler(
        cancel_task,
        filters=command(BotCommands.CancelTaskCommand) & CustomFilters.authorized,
    )
)
bot.add_handler(
    MessageHandler(
        cancell_all_buttons,
        filters=command(BotCommands.CancelAllCommand) & CustomFilters.sudo,
    )
)
bot.add_handler(
    CallbackQueryHandler(
        cancel_all_update, filters=regex("^canall") & CustomFilters.sudo
    )
)
bot.add_handler(CallbackQueryHandler(cancel_multi, filters=regex("^stopm")))
