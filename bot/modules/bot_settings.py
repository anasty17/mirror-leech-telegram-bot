from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from functools import partial
from time import time, sleep
from os import remove, rename, path as ospath, environ
from subprocess import run as srun, Popen
from dotenv import load_dotenv

from bot import config_dict, dispatcher, user_data, DB_URI, MAX_SPLIT_SIZE, DRIVES_IDS, DRIVES_NAMES, INDEX_URLS, aria2, GLOBAL_EXTENSION_FILTER, status_reply_dict_lock, Interval, aria2_options, aria2c_global, IS_PREMIUM_USER, download_dict, qbit_options, get_client
from bot.helper.telegram_helper.message_utils import sendFile, sendMarkup, editMessage, update_all_messages
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


def load_config():

    GDRIVE_ID = environ.get('GDRIVE_ID', '')
    if len(GDRIVE_ID) == 0:
        GDRIVE_ID = ''

    AUTHORIZED_CHATS = environ.get('AUTHORIZED_CHATS', '')
    if len(AUTHORIZED_CHATS) != 0:
        aid = AUTHORIZED_CHATS.split()
        for id_ in aid:
            user_data[int(id_.strip())] = {'is_auth': True}

    SUDO_USERS = environ.get('SUDO_USERS', '')
    if len(SUDO_USERS) != 0:
        aid = SUDO_USERS.split()
        for id_ in aid:
            user_data[int(id_.strip())] = {'is_sudo': True}

    EXTENSION_FILTER = environ.get('EXTENSION_FILTER', '')
    if len(EXTENSION_FILTER) > 0:
        fx = EXTENSION_FILTER.split()
        GLOBAL_EXTENSION_FILTER.clear()
        GLOBAL_EXTENSION_FILTER.append('.aria2')
        for x in fx:
            GLOBAL_EXTENSION_FILTER.append(x.strip().lower())

    MEGA_API_KEY = environ.get('MEGA_API_KEY', '')
    if len(MEGA_API_KEY) == 0:
        MEGA_API_KEY = ''

    MEGA_EMAIL_ID = environ.get('MEGA_EMAIL_ID', '')
    MEGA_PASSWORD = environ.get('MEGA_PASSWORD', '')
    if len(MEGA_EMAIL_ID) == 0 or len(MEGA_PASSWORD) == 0:
        MEGA_EMAIL_ID = ''
        MEGA_PASSWORD = ''

    UPTOBOX_TOKEN = environ.get('UPTOBOX_TOKEN', '')
    if len(UPTOBOX_TOKEN) == 0:
        UPTOBOX_TOKEN = ''

    INDEX_URL = environ.get('INDEX_URL', '').rstrip("/")
    if len(INDEX_URL) == 0:
        INDEX_URL = ''

    SEARCH_API_LINK = environ.get('SEARCH_API_LINK', '').rstrip("/")
    if len(SEARCH_API_LINK) == 0:
        SEARCH_API_LINK = ''

    RSS_COMMAND = environ.get('RSS_COMMAND', '')
    if len(RSS_COMMAND) == 0:
        RSS_COMMAND = ''

    LEECH_FILENAME_PERFIX = environ.get('LEECH_FILENAME_PERFIX', '')
    if len(LEECH_FILENAME_PERFIX) == 0:
        LEECH_FILENAME_PERFIX = ''

    SEARCH_PLUGINS = environ.get('SEARCH_PLUGINS', '')
    if len(SEARCH_PLUGINS) == 0:
        SEARCH_PLUGINS = ''

    MAX_SPLIT_SIZE = 4194304000 if IS_PREMIUM_USER else 2097152000

    LEECH_SPLIT_SIZE = environ.get('LEECH_SPLIT_SIZE', '')
    if len(LEECH_SPLIT_SIZE) == 0 or int(LEECH_SPLIT_SIZE) > MAX_SPLIT_SIZE:
        LEECH_SPLIT_SIZE = MAX_SPLIT_SIZE
    else:
        LEECH_SPLIT_SIZE = int(LEECH_SPLIT_SIZE)

    STATUS_UPDATE_INTERVAL = environ.get('STATUS_UPDATE_INTERVAL', '')
    if len(STATUS_UPDATE_INTERVAL) == 0:
        STATUS_UPDATE_INTERVAL = 10
    else:
        STATUS_UPDATE_INTERVAL = int(STATUS_UPDATE_INTERVAL)
    if len(download_dict) != 0:
        with status_reply_dict_lock:
            try:
                if Interval:
                    Interval[0].cancel()
                    Interval.clear()
            except:
                pass
            finally:
                Interval.append(setInterval(STATUS_UPDATE_INTERVAL, update_all_messages))

    AUTO_DELETE_MESSAGE_DURATION = environ.get('AUTO_DELETE_MESSAGE_DURATION', '')
    if len(AUTO_DELETE_MESSAGE_DURATION) == 0:
        AUTO_DELETE_MESSAGE_DURATION = 30
    else:
        AUTO_DELETE_MESSAGE_DURATION = int(AUTO_DELETE_MESSAGE_DURATION)

    SEARCH_LIMIT = environ.get('SEARCH_LIMIT', '')
    SEARCH_LIMIT = 0 if len(SEARCH_LIMIT) == 0 else int(SEARCH_LIMIT)

    DUMP_CHAT = environ.get('DUMP_CHAT', '')
    DUMP_CHAT = '' if len(DUMP_CHAT) == 0 else int(DUMP_CHAT)

    STATUS_LIMIT = environ.get('STATUS_LIMIT', '')
    STATUS_LIMIT = '' if len(STATUS_LIMIT) == 0 else int(STATUS_LIMIT)

    RSS_CHAT_ID = environ.get('RSS_CHAT_ID', '')
    RSS_CHAT_ID = '' if len(RSS_CHAT_ID) == 0 else int(RSS_CHAT_ID)

    RSS_DELAY = environ.get('RSS_DELAY', '')
    RSS_DELAY = 900 if len(RSS_DELAY) == 0 else int(RSS_DELAY)

    CMD_PERFIX = environ.get('CMD_PERFIX', '')

    TELEGRAM_HASH = environ.get('TELEGRAM_HASH', '')

    TELEGRAM_API = environ.get('TELEGRAM_API', '')

    USER_SESSION_STRING = environ.get('USER_SESSION_STRING', '')

    RSS_USER_SESSION_STRING = environ.get('RSS_USER_SESSION_STRING', '')

    TORRENT_TIMEOUT = environ.get('TORRENT_TIMEOUT', '')
    downloads = aria2.get_downloads()
    if len(TORRENT_TIMEOUT) == 0:
        if downloads:
            aria2.set_options({'bt-stop-timeout': '0'}, downloads)
        aria2_options['bt-stop-timeout'] = '0'
    else:
        if downloads:
            aria2.set_options({'bt-stop-timeout': TORRENT_TIMEOUT}, downloads)
        aria2_options['bt-stop-timeout'] = TORRENT_TIMEOUT
        TORRENT_TIMEOUT = int(TORRENT_TIMEOUT)

    INCOMPLETE_TASK_NOTIFIER = environ.get('INCOMPLETE_TASK_NOTIFIER', '')
    INCOMPLETE_TASK_NOTIFIER = INCOMPLETE_TASK_NOTIFIER.lower() == 'true'

    STOP_DUPLICATE = environ.get('STOP_DUPLICATE', '')
    STOP_DUPLICATE = STOP_DUPLICATE.lower() == 'true'

    VIEW_LINK = environ.get('VIEW_LINK', '')
    VIEW_LINK = VIEW_LINK.lower() == 'true'

    IS_TEAM_DRIVE = environ.get('IS_TEAM_DRIVE', '')
    IS_TEAM_DRIVE = IS_TEAM_DRIVE.lower() == 'true'

    USE_SERVICE_ACCOUNTS = environ.get('USE_SERVICE_ACCOUNTS', '')
    USE_SERVICE_ACCOUNTS = USE_SERVICE_ACCOUNTS.lower() == 'true'

    WEB_PINCODE = environ.get('WEB_PINCODE', '')
    WEB_PINCODE = WEB_PINCODE.lower() == 'true'

    AS_DOCUMENT = environ.get('AS_DOCUMENT', '')
    AS_DOCUMENT = AS_DOCUMENT.lower() == 'true'

    EQUAL_SPLITS = environ.get('EQUAL_SPLITS', '')
    EQUAL_SPLITS = EQUAL_SPLITS.lower() == 'true'

    IGNORE_PENDING_REQUESTS = environ.get('IGNORE_PENDING_REQUESTS', '')
    IGNORE_PENDING_REQUESTS = IGNORE_PENDING_REQUESTS.lower() == 'true'

    SERVER_PORT = environ.get('SERVER_PORT', '')
    if len(SERVER_PORT) == 0:
        SERVER_PORT = 80
    else:
        SERVER_PORT = int(SERVER_PORT)

    BASE_URL = environ.get('BASE_URL', '').rstrip("/")
    if len(BASE_URL) == 0:
        BASE_URL = ''
        srun(["pkill", "-9", "-f", "gunicorn"])
    else:
        srun(["pkill", "-9", "-f", "gunicorn"])
        Popen(f"gunicorn web.wserver:app --bind 0.0.0.0:{SERVER_PORT}", shell=True)

    UPSTREAM_REPO = environ.get('UPSTREAM_REPO', '')
    if len(UPSTREAM_REPO) == 0:
       UPSTREAM_REPO = ''

    UPSTREAM_BRANCH = environ.get('UPSTREAM_BRANCH', '')
    if len(UPSTREAM_BRANCH) == 0:
        UPSTREAM_BRANCH = 'master'

    initiate_search_tools()

    config_dict.update({'AS_DOCUMENT': AS_DOCUMENT,
                        'AUTHORIZED_CHATS': AUTHORIZED_CHATS,
                        'AUTO_DELETE_MESSAGE_DURATION': AUTO_DELETE_MESSAGE_DURATION,
                        'BASE_URL': BASE_URL,
                        'CMD_PERFIX': CMD_PERFIX,
                        'DUMP_CHAT': DUMP_CHAT,
                        'EQUAL_SPLITS': EQUAL_SPLITS,
                        'EXTENSION_FILTER': EXTENSION_FILTER,
                        'GDRIVE_ID': GDRIVE_ID,
                        'IGNORE_PENDING_REQUESTS': IGNORE_PENDING_REQUESTS,
                        'INCOMPLETE_TASK_NOTIFIER': INCOMPLETE_TASK_NOTIFIER,
                        'INDEX_URL': INDEX_URL,
                        'IS_TEAM_DRIVE': IS_TEAM_DRIVE,
                        'LEECH_FILENAME_PERFIX': LEECH_FILENAME_PERFIX,
                        'LEECH_SPLIT_SIZE': LEECH_SPLIT_SIZE,
                        'MEGA_API_KEY': MEGA_API_KEY,
                        'MEGA_EMAIL_ID': MEGA_EMAIL_ID,
                        'MEGA_PASSWORD': MEGA_PASSWORD,
                        'RSS_USER_SESSION_STRING': RSS_USER_SESSION_STRING,
                        'RSS_CHAT_ID': RSS_CHAT_ID,
                        'RSS_COMMAND': RSS_COMMAND,
                        'RSS_DELAY': RSS_DELAY,
                        'SEARCH_API_LINK': SEARCH_API_LINK,
                        'SEARCH_LIMIT': SEARCH_LIMIT,
                        'SEARCH_PLUGINS': SEARCH_PLUGINS,
                        'SERVER_PORT': SERVER_PORT,
                        'STATUS_LIMIT': STATUS_LIMIT,
                        'STATUS_UPDATE_INTERVAL': STATUS_UPDATE_INTERVAL,
                        'STOP_DUPLICATE': STOP_DUPLICATE,
                        'SUDO_USERS': SUDO_USERS,
                        'TELEGRAM_API': TELEGRAM_API,
                        'TELEGRAM_HASH': TELEGRAM_HASH,
                        'TORRENT_TIMEOUT': TORRENT_TIMEOUT,
                        'UPSTREAM_REPO': UPSTREAM_REPO,
                        'UPSTREAM_BRANCH': UPSTREAM_BRANCH,
                        'UPTOBOX_TOKEN': UPTOBOX_TOKEN,
                        'USER_SESSION_STRING': USER_SESSION_STRING,
                        'USE_SERVICE_ACCOUNTS': USE_SERVICE_ACCOUNTS,
                        'VIEW_LINK': VIEW_LINK,
                        'WEB_PINCODE': WEB_PINCODE})

    if DB_URI:
        DbManger().update_config(config_dict)

def get_buttons(key=None, edit_type=None):
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
            buttons.sbutton(k, f"botset editvar {k}")
        if STATE == 'view':
            buttons.sbutton('Edit', "botset edit var")
        else:
            buttons.sbutton('View', "botset view var")
        buttons.sbutton('Back', "botset back")
        buttons.sbutton('Close', "botset close")
        for x in range(0, len(config_dict)-1, 10):
            buttons.sbutton(int(x/10), f"botset start var {x}", position='footer')
        msg = f'Bot Variables. Page: {int(START/10)}. State: {STATE}'
    elif key == 'private':
        buttons.sbutton('Back', "botset back")
        buttons.sbutton('Close', "botset close")
        msg = f'Send private file: config.env, token.pickle, accounts.zip, list_drives.txt, cookies.txt or .netrc.\nTimeout: 60 sec'
    elif key == 'aria':
        for k in list(aria2_options.keys())[START:10+START]:
            buttons.sbutton(k, f"botset editaria {k}")
        if STATE == 'view':
            buttons.sbutton('Edit', "botset edit aria")
        else:
            buttons.sbutton('View', "botset view aria")
        buttons.sbutton('Add new key', "botset editaria newkey")
        buttons.sbutton('Back', "botset back")
        buttons.sbutton('Close', "botset close")
        for x in range(0, len(aria2_options)-1, 10):
            buttons.sbutton(int(x/10), f"botset start aria {x}", position='footer')
        msg = f'Aria2c Options. Page: {int(START/10)}. State: {STATE}'
    elif key == 'qbit':
        for k in list(qbit_options.keys())[START:10+START]:
            buttons.sbutton(k, f"botset editqbit {k}")
        if STATE == 'view':
            buttons.sbutton('Edit', "botset edit qbit")
        else:
            buttons.sbutton('View', "botset view qbit")
        buttons.sbutton('Back', "botset back")
        buttons.sbutton('Close', "botset close")
        for x in range(0, len(qbit_options)-1, 10):
            buttons.sbutton(int(x/10), f"botset start qbit {x}", position='footer')
        msg = f'Qbittorrent Options. Page: {int(START/10)}. State: {STATE}'
    elif edit_type == 'editvar':
        buttons.sbutton('Back', "botset back var")
        if key not in ['TELEGRAM_HASH', 'TELEGRAM_API']:
            buttons.sbutton('Default', f"botset resetvar {key}")
        buttons.sbutton('Close', "botset close")
        msg = f'Send a valid value for {key}. Timeout: 60 sec'
    elif edit_type == 'editaria':
        buttons.sbutton('Back', "botset back aria")
        if key != 'newkey':
            buttons.sbutton('Default', f"botset resetaria {key}")
        buttons.sbutton('Close', "botset close")
        if key == 'newkey':
            msg = f'Send a key with value. Example: https-proxy-user:value'
        else:
            msg = f'Send a valid value for {key}. Timeout: 60 sec'
    elif edit_type == 'editqbit':
        buttons.sbutton('Back', "botset back qbit")
        buttons.sbutton('Close', "botset close")
        msg = f'Send a valid value for {key}. Timeout: 60 sec'
    return msg, buttons.build_menu(2)

def update_buttons(message, key=None, edit_type=None):
    msg, button = get_buttons(key, edit_type)
    editMessage(msg, message, button)

def edit_variable(update, context, omsg, key):
    handler_dict[omsg.chat.id] = False
    value = update.message.text
    if value.lower() == 'true':
        value = True
    elif value.lower() == 'false':
        value = False
    elif key == 'STATUS_UPDATE_INTERVAL':
        value = int(value)
        if len(download_dict) != 0:
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
        downloads = aria2.get_downloads()
        if downloads:
            aria2.set_options({'bt-stop-timeout': f'{value}'}, downloads)
        aria2_options['bt-stop-timeout'] = f'{value}'
    elif key == 'LEECH_SPLIT_SIZE':
        value = min(int(value), MAX_SPLIT_SIZE)
    elif key == 'SERVER_PORT':
        value = int(value)
        srun(["pkill", "-9", "-f", "gunicorn"])
        Popen(f"gunicorn web.wserver:app --bind 0.0.0.0:{value}", shell=True)
    elif key == 'EXTENSION_FILTER':
        fx = value.split()
        GLOBAL_EXTENSION_FILTER.clear()
        GLOBAL_EXTENSION_FILTER.append('.aria2')
        for x in fx:
            GLOBAL_EXTENSION_FILTER.append(x.strip().lower())
    elif key in ['SEARCH_PLUGINS', 'SEARCH_API_LINK']:
        initiate_search_tools()
    elif value.isdigit():
        value = int(value)
    config_dict[key] = value
    update_buttons(omsg, 'var')
    update.message.delete()
    if DB_URI:
        DbManger().update_config({key: value})

def edit_aria(update, context, omsg, key):
    handler_dict[omsg.chat.id] = False
    value = update.message.text
    if key == 'newkey':
        key, value = [x.strip() for x in value.split(':', 1)]
    elif value.lower() == 'true':
        value = "true"
    elif value.lower() == 'false':
        value = "false"
    if key in aria2c_global:
        aria2.set_global_options({key: value})
    else:
        downloads = aria2.get_downloads()
        if downloads:
            aria2.set_options({key: value}, downloads)
    aria2_options[key] = value
    update_buttons(omsg, 'aria')
    update.message.delete()
    if DB_URI:
        DbManger().update_aria2(key, value)

def edit_qbit(update, context, omsg, key):
    handler_dict[omsg.chat.id] = False
    value = update.message.text
    if value.lower() == 'true':
        value = True
    elif value.lower() == 'false':
        value = False
    elif key == 'max_ratio':
        value = float(value)
    elif value.isdigit():
        value = int(value)
    client = get_client()
    client.app_set_preferences({key: value})
    qbit_options[key] = value
    update_buttons(omsg, 'qbit')
    update.message.delete()
    if DB_URI:
        DbManger().update_qbittorrent(key, value)

def upload_file(update, context, omsg):
    handler_dict[omsg.chat.id] = False
    doc = update.message.document
    file_name = doc.file_name
    doc.get_file().download(custom_path=file_name)
    if file_name == 'accounts.zip':
        srun(["unzip", "-q", "-o", "accounts.zip"])
        srun(["chmod", "-R", "777", "accounts"])
    elif file_name == 'list_drives.txt':
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
    elif file_name in ['.netrc', 'netrc']:
        if file_name == 'netrc':
            rename('netrc', '.netrc')
            file_name = '.netrc'
        srun(["cp", ".netrc", "/root/.netrc"])
        srun(["chmod", "600", ".netrc"])
    elif file_name == 'config.env':
        load_dotenv('config.env', override=True)
        load_config()
    if '@github.com' in config_dict['UPSTREAM_REPO']:
        buttons = ButtonMaker()
        msg = 'Push to UPSTREAM_REPO ?'
        buttons.sbutton('Yes!', f"botset push {file_name}")
        buttons.sbutton('No', "botset close")
        sendMarkup(msg, context.bot, update.message, buttons.build_menu(2))
    else:
        update.message.delete()
    update_buttons(omsg)
    if DB_URI:
        DbManger().update_private_file(file_name)
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
    elif data[1] in ['var', 'aria', 'qbit']:
        query.answer()
        update_buttons(message, data[1])
    elif data[1] == 'resetvar':
        query.answer()
        value = ''
        if data[2] in default_values:
            value = default_values[data[2]]
        elif data[2] == 'EXTENSION_FILTER':
            GLOBAL_EXTENSION_FILTER.clear()
            GLOBAL_EXTENSION_FILTER.append('.aria2')
        elif data[2] == 'TORRENT_TIMEOUT':
            downloads = aria2.get_downloads()
            if downloads:
                aria2.set_options({'bt-stop-timeout': '0'}, downloads)
            aria2_options['bt-stop-timeout'] = '0'
        elif data[2] == 'BASE_URL':
            srun(["pkill", "-9", "-f", "gunicorn"])
        elif data[2] == 'SERVER_PORT':
            value = 80
            srun(["pkill", "-9", "-f", "gunicorn"])
            Popen("gunicorn web.wserver:app --bind 0.0.0.0:80", shell=True)
        config_dict[data[2]] = value
        if DB_URI:
            DbManger().update_config({data[2]: value})
        update_buttons(message, 'var')
    elif data[1] == 'resetaria':
        aria2_defaults = aria2.client.get_global_option()
        if aria2_defaults[data[2]] == aria2_options[data[2]]:
            query.answer(text='Value already same as you added in aria.sh!')
            return
        query.answer()
        value = aria2_defaults[data[2]]
        aria2_options[data[2]] = value
        if DB_URI:
            DbManger().update_aria2(data[2], value)
    elif data[1] == 'private':
        query.answer()
        if handler_dict.get(message.chat.id):
            handler_dict[message.chat.id] = False
            sleep(0.5)
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
    elif data[1] == 'editvar' and STATE == 'edit':
        if data[2] in ['SUDO_USERS', 'RSS_USER_SESSION_STRING', 'IGNORE_PENDING_REQUESTS', 'CMD_PERFIX',
                       'USER_SESSION_STRING', 'TELEGRAM_HASH', 'TELEGRAM_API', 'AUTHORIZED_CHATS', 'RSS_DELAY']:
            query.answer(text='Restart required for this edit to take effect!', show_alert=True)
        else:
            query.answer()
        if handler_dict.get(message.chat.id):
            handler_dict[message.chat.id] = False
            sleep(0.5)
        start_time = time()
        handler_dict[message.chat.id] = True
        update_buttons(message, data[2], data[1])
        partial_fnc = partial(edit_variable, omsg=message, key=data[2])
        value_handler = MessageHandler(filters=Filters.text & Filters.chat(message.chat.id) &
                        (CustomFilters.owner_filter | CustomFilters.sudo_user), callback=partial_fnc, run_async=True)
        dispatcher.add_handler(value_handler)
        while handler_dict[message.chat.id]:
            if time() - start_time > 60:
                handler_dict[message.chat.id] = False
                update_buttons(message, 'var')
        dispatcher.remove_handler(value_handler)
    elif data[1] == 'editvar' and STATE == 'view':
        value = config_dict[data[2]]
        if len(str(value)) > 200:
            query.answer()
            filename = f"{data[2]}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f'{value}')
            sendFile(context.bot, message, filename)
            return
        elif value == '':
            value = None
        query.answer(text=f'{value}', show_alert=True)
    elif data[1] == 'editaria' and (STATE == 'edit' or data[2] == 'newkey'):
        query.answer()
        if handler_dict.get(message.chat.id):
            handler_dict[message.chat.id] = False
            sleep(0.5)
        start_time = time()
        handler_dict[message.chat.id] = True
        update_buttons(message, data[2], data[1])
        partial_fnc = partial(edit_aria, omsg=message, key=data[2])
        value_handler = MessageHandler(filters=Filters.text & Filters.chat(message.chat.id) &
                        (CustomFilters.owner_filter | CustomFilters.sudo_user), callback=partial_fnc, run_async=True)
        dispatcher.add_handler(value_handler)
        while handler_dict[message.chat.id]:
            if time() - start_time > 60:
                handler_dict[message.chat.id] = False
                update_buttons(message, 'aria')
        dispatcher.remove_handler(value_handler)
    elif data[1] == 'editaria' and STATE == 'view':
        value = aria2_options[data[2]]
        if len(value) > 200:
            query.answer()
            filename = f"{data[2]}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f'{value}')
            sendFile(context.bot, message, filename)
            return
        elif value == '':
            value = None
        query.answer(text=f'{value}', show_alert=True)
    elif data[1] == 'editqbit' and STATE == 'edit':
        query.answer()
        if handler_dict.get(message.chat.id):
            handler_dict[message.chat.id] = False
            sleep(0.5)
        start_time = time()
        handler_dict[message.chat.id] = True
        update_buttons(message, data[2], data[1])
        partial_fnc = partial(edit_qbit, omsg=message, key=data[2])
        value_handler = MessageHandler(filters=Filters.text & Filters.chat(message.chat.id) &
                        (CustomFilters.owner_filter | CustomFilters.sudo_user), callback=partial_fnc, run_async=True)
        dispatcher.add_handler(value_handler)
        while handler_dict[message.chat.id]:
            if time() - start_time > 60:
                handler_dict[message.chat.id] = False
                update_buttons(message, 'var')
        dispatcher.remove_handler(value_handler)
    elif data[1] == 'editqbit' and STATE == 'view':
        value = qbit_options[data[2]]
        if len(str(value)) > 200:
            query.answer()
            filename = f"{data[2]}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f'{value}')
            sendFile(context.bot, message, filename)
            return
        elif value == '':
            value = None
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


def bot_settings(update, context):
    msg, button = get_buttons()
    sendMarkup(msg, context.bot, update.message, button)


bot_settings_handler = CommandHandler(BotCommands.BotSetCommand, bot_settings,
                                      filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
bb_set_handler = CallbackQueryHandler(edit_bot_settings, pattern="botset", run_async=True)

dispatcher.add_handler(bot_settings_handler)
dispatcher.add_handler(bb_set_handler)
