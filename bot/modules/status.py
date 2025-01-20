from psutil import cpu_percent, virtual_memory, disk_usage
from time import time

from .. import (
    task_dict_lock,
    status_dict,
    task_dict,
    bot_start_time,
    intervals,
)
from ..core.config_manager import Config
from ..helper.ext_utils.bot_utils import sync_to_async, new_task
from ..helper.ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
    speed_string_to_bytes,
)
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.message_utils import (
    send_message,
    delete_message,
    auto_delete_message,
    send_status_message,
    update_status_message,
    edit_message,
)
from ..helper.telegram_helper.button_build import ButtonMaker


@new_task
async def task_status(_, message):
    async with task_dict_lock:
        count = len(task_dict)
    if count == 0:
        currentTime = get_readable_time(time() - bot_start_time)
        free = get_readable_file_size(disk_usage(Config.DOWNLOAD_DIR).free)
        msg = f"No Active Tasks!\nEach user can get status for his tasks by adding me or user_id after cmd: /{BotCommands.StatusCommand} me"
        msg += (
            f"\n<b>CPU:</b> {cpu_percent()}% | <b>FREE:</b> {free}"
            f"\n<b>RAM:</b> {virtual_memory().percent}% | <b>UPTIME:</b> {currentTime}"
        )
        reply_message = await send_message(message, msg)
        await auto_delete_message(message, reply_message)
    else:
        text = message.text.split()
        if len(text) > 1:
            user_id = message.from_user.id if text[1] == "me" else int(text[1])
        else:
            user_id = 0
            sid = message.chat.id
            if obj := intervals["status"].get(sid):
                obj.cancel()
                del intervals["status"][sid]
        await send_status_message(message, user_id)
        await delete_message(message)


@new_task
async def status_pages(_, query):
    data = query.data.split()
    key = int(data[1])
    await query.answer()
    if data[2] == "ref":
        await update_status_message(key, force=True)
    elif data[2] in ["nex", "pre"]:
        async with task_dict_lock:
            if data[2] == "nex":
                status_dict[key]["page_no"] += status_dict[key]["page_step"]
            else:
                status_dict[key]["page_no"] -= status_dict[key]["page_step"]
    elif data[2] == "ps":
        async with task_dict_lock:
            status_dict[key]["page_step"] = int(data[3])
    elif data[2] == "st":
        async with task_dict_lock:
            status_dict[key]["status"] = data[3]
        await update_status_message(key, force=True)
    elif data[2] == "ov":
        message = query.message
        tasks = {
            "Download": 0,
            "Upload": 0,
            "Seed": 0,
            "Archive": 0,
            "Extract": 0,
            "Split": 0,
            "QueueDl": 0,
            "QueueUp": 0,
            "Clone": 0,
            "CheckUp": 0,
            "Pause": 0,
            "SamVid": 0,
            "ConvertMedia": 0,
            "FFmpeg": 0,
        }
        dl_speed = 0
        up_speed = 0
        seed_speed = 0
        async with task_dict_lock:
            for download in task_dict.values():
                match await sync_to_async(download.status):
                    case MirrorStatus.STATUS_DOWNLOAD:
                        tasks["Download"] += 1
                        dl_speed += speed_string_to_bytes(download.speed())
                    case MirrorStatus.STATUS_UPLOAD:
                        tasks["Upload"] += 1
                        up_speed += speed_string_to_bytes(download.speed())
                    case MirrorStatus.STATUS_SEED:
                        tasks["Seed"] += 1
                        seed_speed += speed_string_to_bytes(download.seed_speed())
                    case MirrorStatus.STATUS_ARCHIVE:
                        tasks["Archive"] += 1
                    case MirrorStatus.STATUS_EXTRACT:
                        tasks["Extract"] += 1
                    case MirrorStatus.STATUS_SPLIT:
                        tasks["Split"] += 1
                    case MirrorStatus.STATUS_QUEUEDL:
                        tasks["QueueDl"] += 1
                    case MirrorStatus.STATUS_QUEUEUP:
                        tasks["QueueUp"] += 1
                    case MirrorStatus.STATUS_CLONE:
                        tasks["Clone"] += 1
                    case MirrorStatus.STATUS_CHECK:
                        tasks["CheckUp"] += 1
                    case MirrorStatus.STATUS_PAUSED:
                        tasks["Pause"] += 1
                    case MirrorStatus.STATUS_SAMVID:
                        tasks["SamVid"] += 1
                    case MirrorStatus.STATUS_CONVERT:
                        tasks["ConvertMedia"] += 1
                    case MirrorStatus.STATUS_FFMPEG:
                        tasks["FFMPEG"] += 1
                    case _:
                        tasks["Download"] += 1
                        dl_speed += speed_string_to_bytes(download.speed())

        msg = f"""<b>DL:</b> {tasks['Download']} | <b>UP:</b> {tasks['Upload']} | <b>SD:</b> {tasks['Seed']} | <b>AR:</b> {tasks['Archive']}
<b>EX:</b> {tasks['Extract']} | <b>SP:</b> {tasks['Split']} | <b>QD:</b> {tasks['QueueDl']} | <b>QU:</b> {tasks['QueueUp']}
<b>CL:</b> {tasks['Clone']} | <b>CK:</b> {tasks['CheckUp']} | <b>PA:</b> {tasks['Pause']} | <b>SV:</b> {tasks['SamVid']}
<b>CM:</b> {tasks['ConvertMedia']} | <b>FF:</b> {tasks['FFmpeg']}

<b>ODLS:</b> {get_readable_file_size(dl_speed)}/s
<b>OULS:</b> {get_readable_file_size(up_speed)}/s
<b>OSDS:</b> {get_readable_file_size(seed_speed)}/s
"""
        button = ButtonMaker()
        button.data_button("Back", f"status {data[1]} ref")
        await edit_message(message, msg, button.build_menu())
