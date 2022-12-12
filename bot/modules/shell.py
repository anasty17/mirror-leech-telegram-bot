from subprocess import Popen, PIPE
from telegram.ext import CommandHandler

from bot import LOGGER, dispatcher
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands


def shell(update, context):
    message = update.effective_message
    cmd = message.text.split(maxsplit=1)
    if len(cmd) == 1:
        return message.reply_text('No command to execute was given.')
    cmd = cmd[1]
    process = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
    stdout, stderr = process.communicate()
    reply = ''
    stderr = stderr.decode()
    stdout = stdout.decode()
    if len(stdout) != 0:
        reply += f"*Stdout*\n`{stdout}`\n"
        LOGGER.info(f"Shell - {cmd} - {stdout}")
    if len(stderr) != 0:
        reply += f"*Stderr*\n`{stderr}`\n"
        LOGGER.error(f"Shell - {cmd} - {stderr}")
    if len(reply) > 3000:
        with open('shell_output.txt', 'w') as file:
            file.write(reply)
        with open('shell_output.txt', 'rb') as doc:
            context.bot.send_document(
                document=doc,
                filename=doc.name,
                reply_to_message_id=message.message_id,
                chat_id=message.chat_id)
    elif len(reply) != 0:
        message.reply_text(reply, parse_mode='Markdown')
    else:
        message.reply_text('No Reply', parse_mode='Markdown')


SHELL_HANDLER = CommandHandler(BotCommands.ShellCommand, shell, filters=CustomFilters.owner_filter)

dispatcher.add_handler(SHELL_HANDLER)
