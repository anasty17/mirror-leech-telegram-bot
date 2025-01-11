from sys import executable
from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, remove
from asyncio import gather, create_subprocess_exec
from os import execl as osexecl

from .. import intervals, scheduler, sabnzbd_client, LOGGER
from ..helper.ext_utils.bot_utils import new_task, sync_to_async
from ..helper.telegram_helper.message_utils import (
    send_message,
    delete_message,
)
from ..helper.ext_utils.db_handler import database
from ..helper.ext_utils.files_utils import clean_all
from ..helper.telegram_helper import button_build
from ..core.mltb_client import TgClient
from ..core.config_manager import Config


@new_task
async def restart_bot(_, message):
    buttons = button_build.ButtonMaker()
    buttons.data_button("Yes!", "botrestart confirm")
    buttons.data_button("Cancel", "botrestart cancel")
    button = buttons.build_menu(2)
    await send_message(message, "Are you sure you want to restart the bot ?!", button)


@new_task
async def restart_sessions(_, message):
    buttons = button_build.ButtonMaker()
    buttons.data_button("Yes!", "sessionrestart confirm")
    buttons.data_button("Cancel", "sessionrestart cancel")
    button = buttons.build_menu(2)
    await send_message(
        message, "Are you sure you want to restart the session(s) ?!", button
    )


async def send_incomplete_task_message(cid, msg_id, msg):
    try:
        if msg.startswith("Restarted Successfully!"):
            await TgClient.bot.edit_message_text(
                chat_id=cid,
                message_id=msg_id,
                text=msg,
                disable_web_page_preview=True,
            )
            await remove(".restartmsg")
        else:
            await TgClient.bot.send_message(
                chat_id=cid,
                text=msg,
                disable_web_page_preview=True,
                disable_notification=True,
            )
    except Exception as e:
        LOGGER.error(e)


async def restart_notification():
    if await aiopath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
    else:
        chat_id, msg_id = 0, 0

    if Config.INCOMPLETE_TASK_NOTIFIER and Config.DATABASE_URL:
        if notifier_dict := await database.get_incomplete_tasks():
            for cid, data in notifier_dict.items():
                msg = "Restarted Successfully!" if cid == chat_id else "Bot Restarted!"
                for tag, links in data.items():
                    msg += f"\n\n{tag}: "
                    for index, link in enumerate(links, start=1):
                        msg += f" <a href='{link}'>{index}</a> |"
                        if len(msg.encode()) > 4000:
                            await send_incomplete_task_message(cid, msg_id, msg)
                            msg = ""
                if msg:
                    await send_incomplete_task_message(cid, msg_id, msg)

    if await aiopath.isfile(".restartmsg"):
        try:
            await TgClient.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id, text="Restarted Successfully!"
            )
        except:
            pass
        await remove(".restartmsg")


@new_task
async def confirm_restart(_, query):
    await query.answer()
    data = query.data.split()
    message = query.message
    await delete_message(message)
    if data[1] == "confirm":
        reply_to = message.reply_to_message
        intervals["stopAll"] = True
        restart_message = await send_message(reply_to, "Restarting...")
        await delete_message(message)
        await TgClient.stop()
        if scheduler.running:
            scheduler.shutdown(wait=False)
        if qb := intervals["qb"]:
            qb.cancel()
        if jd := intervals["jd"]:
            jd.cancel()
        if nzb := intervals["nzb"]:
            nzb.cancel()
        if st := intervals["status"]:
            for intvl in list(st.values()):
                intvl.cancel()
        await sync_to_async(clean_all)
        if sabnzbd_client.LOGGED_IN:
            await gather(
                sabnzbd_client.pause_all(),
                sabnzbd_client.purge_all(True),
                sabnzbd_client.delete_history("all", delete_files=True),
            )
        proc1 = await create_subprocess_exec(
            "pkill",
            "-9",
            "-f",
            "gunicorn|aria2c|qbittorrent-nox|ffmpeg|rclone|java|sabnzbdplus|7z|split",
        )
        proc2 = await create_subprocess_exec("python3", "update.py")
        await gather(proc1.wait(), proc2.wait())
        async with aiopen(".restartmsg", "w") as f:
            await f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
        osexecl(executable, executable, "-m", "bot")
    else:
        await delete_message(message)
