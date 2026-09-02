from time import time

from ..core.branding import (
    APP_NAME,
    APP_TAGLINE,
    AUTHORIZED_WELCOME,
    REPOSITORY_URL,
    UNAUTHORIZED_WELCOME,
)
from ..helper.ext_utils.bot_utils import new_task
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import send_message, edit_message, send_file
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.bot_commands import BotCommands


def _start_buttons():
    buttons = ButtonMaker()
    buttons.url_button("💻 Source", REPOSITORY_URL)
    return buttons.build_menu()


@new_task
async def start(_, message):
    reply_markup = _start_buttons()

    if await CustomFilters.authorized(_, message):
        start_string = AUTHORIZED_WELCOME.format(
            name=APP_NAME,
            tagline=APP_TAGLINE,
            help_command=BotCommands.HelpCommand,
        )
        await send_message(message, start_string, reply_markup)
    else:
        start_string = UNAUTHORIZED_WELCOME.format(
            name=APP_NAME,
            tagline=APP_TAGLINE,
        )
        await send_message(message, start_string, reply_markup)


@new_task
async def ping(_, message):
    start_time = int(round(time() * 1000))
    reply = await send_message(message, "🏓 Pinging…")
    end_time = int(round(time() * 1000))
    await edit_message(reply, f"🏓 <b>{APP_NAME}</b> • {end_time - start_time} ms")


@new_task
async def log(_, message):
    await send_file(message, "log.txt")
