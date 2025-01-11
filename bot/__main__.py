from signal import signal, SIGINT
from asyncio import gather
from pyrogram.filters import regex
from pyrogram.handlers import CallbackQueryHandler

from . import LOGGER, bot_loop
from .core.config_manager import Config
from .core.startup import (
    load_settings,
    load_configurations,
    save_settings,
    update_aria2_options,
    update_nzb_options,
    update_qb_options,
    update_variables,
)

Config.load()
bot_loop.run_until_complete(load_settings())

from .core.mltb_client import TgClient
from .core.handlers import add_handlers
from .helper.ext_utils.telegraph_helper import telegraph
from .helper.ext_utils.bot_utils import sync_to_async, create_help_buttons, new_task
from .helper.ext_utils.files_utils import clean_all, exit_clean_up
from .helper.ext_utils.jdownloader_booter import jdownloader
from .helper.listeners.aria2_listener import start_aria2_listener
from .helper.telegram_helper.filters import CustomFilters
from .helper.mirror_leech_utils.rclone_utils.serve import rclone_serve_booter
from .helper.telegram_helper.message_utils import (
    send_message,
    edit_message,
    delete_message,
)
from .modules import initiate_search_tools, get_packages_version, restart_notification


@new_task
async def restart_sessions_confirm(_, query):
    data = query.data.split()
    message = query.message
    if data[1] == "confirm":
        reply_to = message.reply_to_message
        restart_message = await send_message(reply_to, "Restarting Session(s)...")
        await delete_message(message)
        await TgClient.reload()
        add_handlers()
        TgClient.bot.add_handler(
            CallbackQueryHandler(
                restart_sessions_confirm,
                filters=regex("^sessionrestart") & CustomFilters.sudo,
            )
        )
        await edit_message(restart_message, "Session(s) Restarted Successfully!")
    else:
        await delete_message(message)


async def main():
    await gather(TgClient.start_bot(), TgClient.start_user())
    await gather(load_configurations(), update_variables())
    await gather(
        sync_to_async(update_qb_options),
        sync_to_async(update_aria2_options),
        update_nzb_options(),
    )
    await gather(
        save_settings(),
        jdownloader.boot(),
        sync_to_async(clean_all),
        initiate_search_tools(),
        get_packages_version(),
        restart_notification(),
        telegraph.create_account(),
        rclone_serve_booter(),
        sync_to_async(start_aria2_listener, wait=False),
    )
    create_help_buttons()
    add_handlers()
    TgClient.bot.add_handler(
        CallbackQueryHandler(
            restart_sessions_confirm,
            filters=regex("^sessionrestart") & CustomFilters.sudo,
        )
    )
    LOGGER.info("Bot Started!")
    signal(SIGINT, exit_clean_up)


bot_loop.run_until_complete(main())
bot_loop.run_forever()
