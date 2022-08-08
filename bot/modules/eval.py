from os import path as ospath, getcwd, chdir
from traceback import format_exc
from textwrap import indent
from io import StringIO, BytesIO
from telegram import ParseMode
from telegram.ext import CommandHandler
from contextlib import redirect_stdout

from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import sendMessage
from bot import LOGGER, dispatcher

namespaces = {}

def namespace_of(chat, update, bot):
    if chat not in namespaces:
        namespaces[chat] = {
            '__builtins__': globals()['__builtins__'],
            'bot': bot,
            'effective_message': update.effective_message,
            'effective_user': update.effective_user,
            'effective_chat': update.effective_chat,
            'update': update
        }

    return namespaces[chat]

def log_input(update):
    user = update.effective_user.id
    chat = update.effective_chat.id
    LOGGER.info(
        f"IN: {update.effective_message.text} (user={user}, chat={chat})")

def send(msg, bot, update):
    if len(str(msg)) > 2000:
        with BytesIO(str.encode(msg)) as out_file:
            out_file.name = "output.txt"
            bot.send_document(
                chat_id=update.effective_chat.id, document=out_file)
    else:
        LOGGER.info(f"OUT: '{msg}'")
        bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"`{msg}`",
            parse_mode=ParseMode.MARKDOWN)

def evaluate(update, context):
    bot = context.bot
    send(do(eval, bot, update), bot, update)

def execute(update, context):
    bot = context.bot
    send(do(exec, bot, update), bot, update)

def cleanup_code(code):
    if code.startswith('```') and code.endswith('```'):
        return '\n'.join(code.split('\n')[1:-1])
    return code.strip('` \n')

def do(func, bot, update):
    log_input(update)
    content = update.message.text.split(maxsplit=1)[-1]
    body = cleanup_code(content)
    env = namespace_of(update.message.chat_id, update, bot)

    chdir(getcwd())
    with open(
            ospath.join(getcwd(),
                         'bot/modules/temp.txt'),
            'w') as temp:
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

def clear(update, context):
    bot = context.bot
    log_input(update)
    global namespaces
    if update.message.chat_id in namespaces:
        del namespaces[update.message.chat_id]
    send("Cleared locals.", bot, update)

EVAL_HANDLER = CommandHandler(BotCommands.EvalCommand, evaluate, filters=CustomFilters.owner_filter, run_async=True)
EXEC_HANDLER = CommandHandler(BotCommands.ExecCommand, execute, filters=CustomFilters.owner_filter, run_async=True)
CLEAR_HANDLER = CommandHandler(BotCommands.ClearLocalsCommand, clear, filters=CustomFilters.owner_filter, run_async=True)

dispatcher.add_handler(EVAL_HANDLER)
dispatcher.add_handler(EXEC_HANDLER)
dispatcher.add_handler(CLEAR_HANDLER)
