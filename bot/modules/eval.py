#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from os import path as ospath, getcwd, chdir
from traceback import format_exc
from textwrap import indent
from io import StringIO, BytesIO
from contextlib import redirect_stdout

from bot import LOGGER, bot
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import sendFile, sendMessage
from bot.helper.ext_utils.bot_utils import sync_to_async, new_task

namespaces = {}


def namespace_of(message):
    if message.chat.id not in namespaces:
        namespaces[message.chat.id] = {
            '__builtins__': globals()['__builtins__'],
            'bot': bot,
            'message': message,
            'user': message.from_user or message.sender_chat,
            'chat': message.chat}

    return namespaces[message.chat.id]


def log_input(message):
    LOGGER.info(
        f"IN: {message.text} (user={message.from_user.id}, chat={message.chat.id})")


async def send(msg, message):
    if len(str(msg)) > 2000:
        with BytesIO(str.encode(msg)) as out_file:
            out_file.name = "output.txt"
            await sendFile(message, out_file)
    else:
        LOGGER.info(f"OUT: '{msg}'")
        await sendMessage(message, f"<code>{msg}</code>")


@new_task
async def evaluate(client, message):
    await send(await sync_to_async(do, eval, message), message)


@new_task
async def execute(client, message):
    await send(await sync_to_async(do, exec, message), message)


def cleanup_code(code):
    if code.startswith('```') and code.endswith('```'):
        return '\n'.join(code.split('\n')[1:-1])
    return code.strip('` \n')


def do(func, message):
    log_input(message)
    content = message.text.split(maxsplit=1)[-1]
    body = cleanup_code(content)
    env = namespace_of(message)

    chdir(getcwd())
    with open(ospath.join(getcwd(), 'bot/modules/temp.txt'), 'w') as temp:
        temp.write(body)

    stdout = StringIO()

    to_compile = f'def func():\n{indent(body, "  ")}'

    try:
        exec(to_compile, env)
    except Exception as e:
        return f'{e.__class__.__name__}: {e}'

    func = env['func']

    try:
        with redirect_stdout(stdout):
            func_return = func()
    except Exception as e:
        value = stdout.getvalue()
        return f'{value}{format_exc()}'
    else:
        value = stdout.getvalue()
        result = None
        if func_return is None:
            if value:
                result = f'{value}'
            else:
                try:
                    result = f'{repr(eval(body, env))}'
                except:
                    pass
        else:
            result = f'{value}{func_return}'
        if result:
            return result


async def clear(client, message):
    log_input(message)
    global namespaces
    if message.chat.id in namespaces:
        del namespaces[message.chat.id]
    await send("Locals Cleared.", message)


bot.add_handler(MessageHandler(evaluate, filters=command(
    BotCommands.EvalCommand) & CustomFilters.owner))
bot.add_handler(MessageHandler(execute, filters=command(
    BotCommands.ExecCommand) & CustomFilters.owner))
bot.add_handler(MessageHandler(clear, filters=command(
    BotCommands.ClearLocalsCommand) & CustomFilters.owner))
