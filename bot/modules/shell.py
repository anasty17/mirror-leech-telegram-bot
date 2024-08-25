from io import BytesIO
from pyrogram.filters import command
from pyrogram.handlers import MessageHandler, EditedMessageHandler

from bot import LOGGER, bot
from ..helper.ext_utils.bot_utils import cmd_exec, handler_new_task
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import send_message, send_file


@handler_new_task
async def shell(_, message):
    cmd = message.text.split(maxsplit=1)
    if len(cmd) == 1:
        await send_message(message, "No command to execute was given.")
        return
    cmd = cmd[1]
    stdout, stderr, _ = await cmd_exec(cmd, shell=True)
    reply = ""
    if len(stdout) != 0:
        reply += f"*Stdout*\n<code>{stdout}</code>\n"
        LOGGER.info(f"Shell - {cmd} - {stdout}")
    if len(stderr) != 0:
        reply += f"*Stderr*\n<code>{stderr}</code>"
        LOGGER.error(f"Shell - {cmd} - {stderr}")
    if len(reply) > 3000:
        with BytesIO(str.encode(reply)) as out_file:
            out_file.name = "shell_output.txt"
            await send_file(message, out_file)
    elif len(reply) != 0:
        await send_message(message, reply)
    else:
        await send_message(message, "No Reply")


bot.add_handler(
    MessageHandler(
        shell,
        filters=command(BotCommands.ShellCommand, case_sensitive=True)
        & CustomFilters.owner,
    )
)
bot.add_handler(
    EditedMessageHandler(
        shell,
        filters=command(BotCommands.ShellCommand, case_sensitive=True)
        & CustomFilters.owner,
    )
)
