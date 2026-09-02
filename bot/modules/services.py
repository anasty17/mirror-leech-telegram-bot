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
    buttons.data_button("📖 Commands", "filehub commands")
    buttons.data_button("📊 Task Status", "filehub status")
    buttons.url_button("💻 Source", REPOSITORY_URL)
    return buttons.build_menu(2)


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
async def filehub_menu(_, query):
    action = query.data.split(maxsplit=1)[1] if " " in query.data else "home"

    if action == "commands":
        buttons = ButtonMaker()
        buttons.data_button("⬅️ Back", "filehub home")
        buttons.url_button("💻 Source", REPOSITORY_URL)
        text = (
            f"<b>📖 {APP_NAME} Commands</b>\n\n"
            f"<b>Downloads</b>\n"
            f"/{BotCommands.MirrorCommand[0]} — direct/rclone mirror\n"
            f"/{BotCommands.QbMirrorCommand[0]} — torrent mirror\n"
            f"/{BotCommands.LeechCommand[0]} — download and upload to Telegram\n"
            f"/{BotCommands.YtdlCommand[0]} — yt-dlp download\n\n"
            f"<b>Tasks</b>\n"
            f"/{BotCommands.StatusCommand} — active task status\n"
            f"/{BotCommands.CancelTaskCommand[0]} — cancel a task\n"
            f"/{BotCommands.SelectCommand} — select torrent files\n\n"
            f"Use /{BotCommands.HelpCommand} for full flags and advanced usage."
        )
        await edit_message(query.message, text, buttons.build_menu(2))
    elif action == "status":
        buttons = ButtonMaker()
        buttons.data_button("⬅️ Back", "filehub home")
        text = (
            f"<b>📊 {APP_NAME} Task Status</b>\n\n"
            f"Use /{BotCommands.StatusCommand} to view active downloads/uploads, "
            "progress, speed and ETA.\n\n"
            f"Use /{BotCommands.CancelTaskCommand[0]} to cancel a task."
        )
        await edit_message(query.message, text, buttons.build_menu())
    else:
        text = AUTHORIZED_WELCOME.format(
            name=APP_NAME,
            tagline=APP_TAGLINE,
            help_command=BotCommands.HelpCommand,
        )
        await edit_message(query.message, text, _start_buttons())

    await query.answer()


@new_task
async def ping(_, message):
    start_time = int(round(time() * 1000))
    reply = await send_message(message, "🏓 Pinging…")
    end_time = int(round(time() * 1000))
    await edit_message(reply, f"🏓 <b>{APP_NAME}</b> • {end_time - start_time} ms")


@new_task
async def log(_, message):
    await send_file(message, "log.txt")
