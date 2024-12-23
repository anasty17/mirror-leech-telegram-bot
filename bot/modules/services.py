from time import time

from ..helper.ext_utils.bot_utils import new_task
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import send_message, edit_message, send_file
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.bot_commands import BotCommands


@new_task
async def start(_, message):
    buttons = ButtonMaker()
    buttons.url_button(
        "Repo", "https://www.github.com/anasty17/mirror-leech-telegram-bot"
    )
    buttons.url_button("Code Owner", "https://t.me/anas_tayyar")
    reply_markup = buttons.build_menu(2)
    if await CustomFilters.authorized(_, message):
        start_string = f"""
This bot can mirror from links|tgfiles|torrents|nzb|rclone-cloud to any rclone cloud, Google Drive or to telegram.
Type /{BotCommands.HelpCommand} to get a list of available commands
"""
        await send_message(message, start_string, reply_markup)
    else:
        await send_message(
            message,
            "This bot can mirror from links|tgfiles|torrents|nzb|rclone-cloud to any rclone cloud, Google Drive or to telegram.\n\n⚠️ You Are not authorized user! Deploy your own mirror-leech bot",
            reply_markup,
        )


@new_task
async def ping(_, message):
    start_time = int(round(time() * 1000))
    reply = await send_message(message, "Starting Ping")
    end_time = int(round(time() * 1000))
    await edit_message(reply, f"{end_time - start_time} ms")


@new_task
async def log(_, message):
    await send_file(message, "log.txt")
