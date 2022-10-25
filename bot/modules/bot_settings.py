from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from functools import partial
from time import time
from os import remove, rename, path as ospath
from subprocess import run as srun, Popen

from bot import config_dict, dispatcher, DB_URI, MAX_SPLIT_SIZE, DRIVES_IDS, DRIVES_NAMES, INDEX_URLS, aria2, GLOBAL_EXTENSION_FILTER, LOGGER, status_reply_dict_lock, Interval
from bot.helper.telegram_helper.message_utils import sendMarkup, editMessage, deleteMessage, update_all_messages
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.bot_utils import new_thread, setInterval
from bot.helper.ext_utils.db_handler import DbManger
from bot.modules.search import initiate_search_tools

START = 0
STATE = 'view'
handler_dict = {}
default_values = {'AUTO_DELETE_MESSAGE_DURATION': 30,
                  'UPSTREAM_BRANCH': 'master',
                  'STATUS_UPDATE_INTERVAL': 10,
                  'LEECH_SPLIT_SIZE': MAX_SPLIT_SIZE,
                  'SEARCH_LIMIT': 0,
                  'RSS_DELAY': 900}


def get_buttons(key=None):
    buttons = ButtonMaker()
    if key is None:
        buttons.sbutton('Edit Variables', "botset var")
        buttons.sbutton('Private Files', "botset private")
        buttons.sbutton('Qbit Settings', "botset qbit")
        buttons.sbutton('Aria2c Settings', "botset aria")
        buttons.sbutton('Close', "botset close")
        msg = 'Bot Settings:'
    elif key == 'var':
        for k in list(config_dict.keys())[START:10+START]:
            buttons.sbutton(k, f"botset edtvar {k}")
        if STATE == 'view':
            buttons.sbutton('Edit', "botset edit var")
        else:
            buttons.sbutton('View', "botset view var")
        buttons.sbutton('Back', "botset back")
        buttons.sbutton('Close', "botset close")
        for x in range(0, len(config_dict)-1, 10):
            buttons.sbutton(int(x/10), f"botset start var {x}", position='footer')
        msg = f'Page: {int(START/10)}. Bot Variables:'
    elif key == 'private':
        buttons.sbutton('Back', "botset back")
        buttons.sbutton('Close', "botset close")
        msg = f'Send private file: config.env, token.pickle, accounts.zip, list_drives.txt, cookies.txt or .netrc.\nTimeout: 60 sec'
    else:
        buttons.sbutton('Back', "botset back var")
        if key not in ['TELEGRAM_HASH', 'TELEGRAM_API']:
            buttons.sbutton('Default', f"botset reset {key}")
        buttons.sbutton('Close', "botset close")
        msg = f'Send a valid value for {key}. Timeout: 60 sec'
    return msg, buttons.build_menu(2)

def update_buttons(message, key=None):
    msg, button = get_buttons(key)
    editMessage(msg, message, button)

def edit_variable(update, context, omsg, key):
    handler_dict[omsg.chat.id] = False
    value = update.message.text
    if value.lower() == 'true':
        value = True
        config_dict[key] = value
    elif value.lower() == 'false':
        value = False
        config_dict[key] = value
    elif key == 'STATUS_LIMIT':
        value = int(value)
        with status_reply_dict_lock:
            try:
                if Interval:
                    Interval[0].cancel()
                    Interval.clear()
            except:
                pass
            finally:
                Interval.append(setInterval(value, update_all_messages))
    elif key == 'TORRENT_TIMEOUT':
        value = int(value)
        config_dict[key] = value
        aria2.set_global_options({'bt-stop-timeout': value})
    elif key == 'LEECH_SPLIT_SIZE':
        value = int(value)
        value = min(value, MAX_SPLIT_SIZE)
        config_dict[key] = value
    elif key == 'SERVER_PORT':
        value = int(value)
        srun(["pkill", "-9", "-f", "gunicorn"])
        Popen(f"gunicorn web.wserver:app --bind 0.0.0.0:{value}", shell=True)
        config_dict[key] = value
    elif key == 'EXTENSION_FILTER':
        fx = value.split()
        GLOBAL_EXTENSION_FILTER.clear()
        GLOBAL_EXTENSION_FILTER.append('.aria2')
        for x in fx:
            GLOBAL_EXTENSION_FILTER.append(x.strip().lower())
        config_dict[key] = value
    elif key in ['SEARCH_PLUGINS', 'SEARCH_API_LINK']:
        config_dict[key] = value
        initiate_search_tools()
    elif value.isdigit():
        value = int(value)
        config_dict[key] = value
    else:
        config_dict[key] = value
    update_buttons(omsg, 'var')
    if DB_URI:
        DbManger().update_config(key, value)

def upload_file(update, context, omsg):
    handler_dict[omsg.chat.id] = False
    doc = update.message
    doc_path = doc.document.get_file().download()
    LOGGER.info(doc_path)
    if doc_path == 'accounts.zip':
        srun(["unzip", "-q", "-o", "accounts.zip"])
        srun(["chmod", "-R", "777", "accounts"])
    elif doc_path == 'list_drives.txt':
        DRIVES_IDS.clear()
        DRIVES_NAMES.clear()
        INDEX_URLS.clear()
        if GDRIVE_ID := config_dict['GDRIVE_ID']:
            DRIVES_NAMES.append("Main")
            DRIVES_IDS.append(GDRIVE_ID)
            if INDEX_URL := config_dict['INDEX_URL']:
                INDEX_URLS.append(INDEX_URL)
            else:
                INDEX_URLS.append(None)
        with open('list_drives.txt', 'r+') as f:
            lines = f.readlines()
            for line in lines:
                temp = line.strip().split()
                DRIVES_IDS.append(temp[1])
                DRIVES_NAMES.append(temp[0].replace("_", " "))
                if len(temp) > 2:
                    INDEX_URLS.append(temp[2])
                else:
                    INDEX_URLS.append(None)
    elif doc_path in ['.netrc', 'netrc']:
        if doc_path == 'netrc':
            rename('netrc', '.netrc')
            doc_path = '.netrc'
        srun(["cp", ".netrc", "/root/.netrc"])
        srun(["chmod", "600", ".netrc"])
        aria2.set_global_options({'netrc-path': '/usr/src/app/.netrc'})
    if '@github.com' in config_dict['UPSTREAM_REPO']:
        buttons = ButtonMaker()
        msg = 'Push to UPSTREAM_REPO ?'
        buttons.sbutton('Yes!', f"botset push {doc_path}")
        buttons.sbutton('No', "botset close")
        sendMarkup(msg, context.bot, update.message, buttons.build_menu(2))
    else:
        deleteMessage(context.bot, update.message)
    update_buttons(omsg)
    if DB_URI:
        DbManger.update_private_file(doc_path)
    if ospath.exists('accounts.zip'):
        remove('accounts.zip')

@new_thread
def edit_bot_settings(update, context):
    query = update.callback_query
    message = query.message
    user_id = query.from_user.id
    data = query.data
    data = data.split()
    if not CustomFilters.owner_query(user_id):
        query.answer(text="You don't have premision to use these buttons!", show_alert=True)
    elif data[1] == 'close':
        query.answer()
        handler_dict[message.chat.id] = False
        query.message.delete()
        query.message.reply_to_message.delete()
    elif data[1] == 'back':
        query.answer()
        handler_dict[message.chat.id] = False
        key = data[2] if len(data) == 3 else None
        update_buttons(message, key)
    elif data[1] == 'var':
        query.answer()
        update_buttons(message, 'var')
    elif data[1] == 'reset':
        query.answer()
        value = ''
        if data[2] in default_values:
            value = default_values[data[2]]
        elif data[2] == 'EXTENSION_FILTER':
            GLOBAL_EXTENSION_FILTER.clear()
            GLOBAL_EXTENSION_FILTER.append('.aria2')
        elif data[2] == 'TORRENT_TIMEOUT':
            aria2.set_global_options({'bt-stop-timeout': 0})
        elif data[2] == 'BASE_URL':
            srun(["pkill", "-9", "-f", "gunicorn"])
        elif data[2] == 'SERVER_PORT':
            value = 80
            srun(["pkill", "-9", "-f", "gunicorn"])
            Popen("gunicorn web.wserver:app --bind 0.0.0.0:80", shell=True)
        config_dict[data[2]] = value
        if DB_URI:
            DbManger().update_config(data[2], value)
        update_buttons(message, 'var')
    elif data[1] == 'private':
        query.answer()
        start_time = time()
        handler_dict[message.chat.id] = True
        update_buttons(message, 'private')
        partial_fnc = partial(upload_file, omsg=message)
        file_handler = MessageHandler(filters=Filters.document & Filters.chat(message.chat.id) &
                        (CustomFilters.owner_filter | CustomFilters.sudo_user), callback=partial_fnc, run_async=True)
        dispatcher.add_handler(file_handler)
        while handler_dict[message.chat.id]:
            if time() - start_time > 60:
                handler_dict[message.chat.id] = False
                update_buttons(message)
        dispatcher.remove_handler(file_handler)
    elif data[1] == 'edtvar' and STATE == 'edit':
        if data[2] in ['SUDO_USERS', 'RSS_USER_SESSION_STRING', 'IGNORE_PENDING_REQUESTS', 'CMD_PERFIX',
                       'USER_SESSION_STRING', 'TELEGRAM_HASH', 'TELEGRAM_API', 'AUTHORIZED_CHATS', 'RSS_DELAY']:
            query.answer(text='Restart required for this edit to take effect!', show_alert=True)
        else:
            query.answer()
        start_time = time()
        handler_dict[message.chat.id] = True
        update_buttons(message, data[2])
        partial_fnc = partial(edit_variable, omsg=message, key=data[2])
        value_handler = MessageHandler(filters=Filters.text & Filters.chat(message.chat.id) &
                        (CustomFilters.owner_filter | CustomFilters.sudo_user), callback=partial_fnc, run_async=True)
        dispatcher.add_handler(value_handler)
        while handler_dict[message.chat.id]:
            if time() - start_time > 60:
                handler_dict[message.chat.id] = False
                update_buttons(message, 'var')
        dispatcher.remove_handler(value_handler)
    elif data[1] == 'edtvar' and STATE == 'view':
        value = config_dict[data[2]]
        if value == '':
            value = 'None'
        query.answer(text=f'{value}', show_alert=True)
    elif data[1] == 'edit':
        query.answer()
        globals()['STATE'] = 'edit'
        update_buttons(message, data[2])
    elif data[1] == 'view':
        query.answer()
        globals()['STATE'] = 'view'
        update_buttons(message, data[2])
    elif data[1] == 'start':
        query.answer()
        if START != int(data[3]):
            globals()['START'] = int(data[3])
            update_buttons(message, data[2])
    elif data[1] == 'push':
        query.answer()
        srun([f"git add -f {data[2]} \
                && git commit -sm botsettings -q \
                && git push origin {config_dict['UPSTREAM_BRANCH']} -q"], shell=True)
        query.message.delete()
        query.message.reply_to_message.delete()
    elif data[1] == 'qbit':
        query.answer(text='Soon!', show_alert=True)
    elif data[1] == 'aria':
        query.answer(text='Soon!', show_alert=True)

def bot_settings(update, context):
    msg, button = get_buttons()
    sendMarkup(msg, context.bot, update.message, button)


bot_settings_handler = CommandHandler(BotCommands.BotSetCommand, bot_settings,
                                      filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
bb_set_handler = CallbackQueryHandler(edit_bot_settings, pattern="botset", run_async=True)

dispatcher.add_handler(bot_settings_handler)
dispatcher.add_handler(bb_set_handler)
