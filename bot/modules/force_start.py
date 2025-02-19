from .. import (
    task_dict,
    task_dict_lock,
    user_data,
    queued_up,
    queued_dl,
    queue_dict_lock,
)
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import new_task
from ..helper.ext_utils.status_utils import get_task_by_gid
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.message_utils import send_message
from ..helper.ext_utils.task_manager import start_dl_from_queued, start_up_from_queued


@new_task
async def remove_from_queue(_, message):
    user_id = message.from_user.id if message.from_user else message.sender_chat.id
    msg = message.text.split()
    status = msg[1] if len(msg) > 1 and msg[1] in ["fd", "fu"] else ""
    if status and len(msg) > 2 or not status and len(msg) > 1:
        gid = msg[2] if status else msg[1]
        task = await get_task_by_gid(gid)
        if task is None:
            await send_message(message, f"GID: <code>{gid}</code> Not Found.")
            return
    elif reply_to_id := message.reply_to_message_id:
        async with task_dict_lock:
            task = task_dict.get(reply_to_id)
        if task is None:
            await send_message(message, "This is not an active task!")
            return
    elif len(msg) in {1, 2}:
        msg = f"""Reply to an active Command message which was used to start the download/upload.
<code>/{BotCommands.ForceStartCommand[0]}</code> fd (to remove it from download queue) or fu (to remove it from upload queue) or nothing to start remove it from both download and upload queue.
Also send <code>/{BotCommands.ForceStartCommand[0]} GID</code> fu|fd or obly gid to force start by removeing the task rom queue!
Examples:
<code>/{BotCommands.ForceStartCommand[1]}</code> GID fu (force upload)
<code>/{BotCommands.ForceStartCommand[1]}</code> GID (force download and upload)
By reply to task cmd:
<code>/{BotCommands.ForceStartCommand[1]}</code> (force download and upload)
<code>/{BotCommands.ForceStartCommand[1]}</code> fd (force download)
"""
        await send_message(message, msg)
        return
    if (
        Config.OWNER_ID != user_id
        and task.listener.user_id != user_id
        and (user_id not in user_data or not user_data[user_id].get("SUDO"))
    ):
        await send_message(message, "This task is not for you!")
        return
    listener = task.listener
    msg = ""
    async with queue_dict_lock:
        if status == "fu":
            listener.force_upload = True
            if listener.mid in queued_up:
                await start_up_from_queued(listener.mid)
                msg = "Task have been force started to upload!"
            else:
                msg = "Force upload enabled for this task!"
        elif status == "fd":
            listener.force_download = True
            if listener.mid in queued_dl:
                await start_dl_from_queued(listener.mid)
                msg = "Task have been force started to download only!"
            else:
                msg = "This task not in download queue!"
        else:
            listener.force_download = True
            listener.force_upload = True
            if listener.mid in queued_up:
                await start_up_from_queued(listener.mid)
                msg = "Task have been force started to upload!"
            elif listener.mid in queued_dl:
                await start_dl_from_queued(listener.mid)
                msg = "Task have been force started to download and upload will start once download finish!"
            else:
                msg = "This task not in queue!"
    if msg:
        await send_message(message, msg)
