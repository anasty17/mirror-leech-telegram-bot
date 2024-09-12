from aiofiles.os import path as aiopath, remove
from asyncio import gather
from signal import signal, SIGINT

from bot import (
    bot,
    LOGGER,
    config_dict,
)
from .helper.ext_utils.telegraph_helper import telegraph
from .helper.ext_utils.bot_utils import (
    sync_to_async,
    create_help_buttons,
)
from .helper.ext_utils.db_handler import database
from .helper.ext_utils.files_utils import clean_all, exit_clean_up
from .helper.ext_utils.jdownloader_booter import jdownloader
from .helper.listeners.aria2_listener import start_aria2_listener
from .helper.mirror_leech_utils.rclone_utils.serve import rclone_serve_booter
from .modules import (
    authorize,
    basic_commands,
    bot_settings,
    cancel_task,
    clone,
    exec,
    file_selector,
    force_start,
    gd_count,
    gd_delete,
    gd_search,
    help,
    mirror_leech,
    shell,
    status,
    users_settings,
    ytdlp,
    
)


async def restart_notification():
    if await aiopath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
    else:
        chat_id, msg_id = 0, 0

    async def send_incomplete_task_message(cid, msg):
        try:
            if msg.startswith("Restarted Successfully!"):
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=msg_id, text=msg
                )
                await remove(".restartmsg")
            else:
                await bot.send_message(
                    chat_id=cid,
                    text=msg,
                    disable_web_page_preview=True,
                    disable_notification=True,
                )
        except Exception as e:
            LOGGER.error(e)

    if config_dict["INCOMPLETE_TASK_NOTIFIER"] and config_dict["DATABASE_URL"]:
        if notifier_dict := await database.get_incomplete_tasks():
            for cid, data in notifier_dict.items():
                msg = "Restarted Successfully!" if cid == chat_id else "Bot Restarted!"
                for tag, links in data.items():
                    msg += f"\n\n{tag}: "
                    for index, link in enumerate(links, start=1):
                        msg += f" <a href='{link}'>{index}</a> |"
                        if len(msg.encode()) > 4000:
                            await send_incomplete_task_message(cid, msg)
                            msg = ""
                if msg:
                    await send_incomplete_task_message(cid, msg)

    if await aiopath.isfile(".restartmsg"):
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id, text="Restarted Successfully!"
            )
        except:
            pass
        await remove(".restartmsg")


async def main():
    if config_dict["DATABASE_URL"]:
        await database.db_load()
    await gather(
        jdownloader.initiate(),
        sync_to_async(clean_all),
        bot_settings.initiate_search_tools(),
        restart_notification(),
        telegraph.create_account(),
        rclone_serve_booter(),
        sync_to_async(start_aria2_listener, wait=False),
    )
    create_help_buttons()

    
    LOGGER.info("Bot Started!")
    signal(SIGINT, exit_clean_up)


bot.loop.run_until_complete(main())
bot.loop.run_forever()
