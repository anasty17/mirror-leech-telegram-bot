from logging import getLogger, FileHandler, StreamHandler, INFO, basicConfig, error as log_error, info as log_info, warning as log_warning
from socket import setdefaulttimeout
from faulthandler import enable as faulthandler_enable
from telegram.ext import Updater as tgUpdater
from qbittorrentapi import Client as qbClient
from aria2p import API as ariaAPI, Client as ariaClient
from os import remove as osremove, path as ospath, environ
from requests import get as rget
from json import loads as jsonloads
from subprocess import Popen, run as srun, check_output
from time import sleep, time
from threading import Thread, Lock
from dotenv import load_dotenv
from pyrogram import Client, enums
from asyncio import get_event_loop

main_loop = get_event_loop()

faulthandler_enable()

setdefaulttimeout(600)

botStartTime = time()

basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[FileHandler('log.txt'), StreamHandler()],
                    level=INFO)

LOGGER = getLogger(__name__)

load_dotenv('config.env', override=True)

NETRC_URL = environ.get('NETRC_URL', '')
if len(NETRC_URL) != 0:
    try:
        res = rget(NETRC_URL)
        if res.status_code == 200:
            with open('.netrc', 'wb+') as f:
                f.write(res.content)
        else:
            log_error(f"Failed to download .netrc {res.status_code}")
    except Exception as e:
        log_error(f"NETRC_URL: {e}")

SERVER_PORT = environ.get('SERVER_PORT', '')
if len(SERVER_PORT) == 0:
    SERVER_PORT = 80

Popen(f"gunicorn web.wserver:app --bind 0.0.0.0:{SERVER_PORT}", shell=True)
srun(["qbittorrent-nox", "-d", "--profile=."])
if not ospath.exists('.netrc'):
    srun(["touch", ".netrc"])
srun(["cp", ".netrc", "/root/.netrc"])
srun(["chmod", "600", ".netrc"])
srun(["chmod", "+x", "aria.sh"])
srun("./aria.sh", shell=True)
sleep(0.5)

Interval = []
QbInterval = []
DRIVES_NAMES = []
DRIVES_IDS = []
INDEX_URLS = []

try:
    if bool(getConfig('_____REMOVE_THIS_LINE_____')):
        log_error('The README.md file there to be read! Exiting now!')
        exit()
except:
    pass

aria2 = ariaAPI(
    ariaClient(
        host="http://localhost",
        port=6800,
        secret="",
    )
)

def get_client():
    return qbClient(host="localhost", port=8090, VERIFY_WEBUI_CERTIFICATE=False, REQUESTS_ARGS={'timeout': (30, 60)})

download_dict_lock = Lock()
status_reply_dict_lock = Lock()
# Key: update.effective_chat.id
# Value: telegram.Message
status_reply_dict = {}
# Key: update.message.message_id
# Value: An object of Status
download_dict = {}
# key: rss_title
# value: [rss_feed, last_link, last_title, filter]
rss_dict = {}

AUTHORIZED_CHATS = set()
SUDO_USERS = set()
AS_DOC_USERS = set()
AS_MEDIA_USERS = set()
EXTENSION_FILTER = set(['.aria2'])

def getConfig(name: str):
    return environ[name]

try:
    BOT_TOKEN = getConfig('BOT_TOKEN')
    parent_id = getConfig('GDRIVE_FOLDER_ID')
    DOWNLOAD_DIR = getConfig('DOWNLOAD_DIR')
    if not DOWNLOAD_DIR.endswith("/"):
        DOWNLOAD_DIR = DOWNLOAD_DIR + '/'
    DOWNLOAD_STATUS_UPDATE_INTERVAL = int(getConfig('DOWNLOAD_STATUS_UPDATE_INTERVAL'))
    OWNER_ID = int(getConfig('OWNER_ID'))
    AUTO_DELETE_MESSAGE_DURATION = int(getConfig('AUTO_DELETE_MESSAGE_DURATION'))
    TELEGRAM_API = getConfig('TELEGRAM_API')
    TELEGRAM_HASH = getConfig('TELEGRAM_HASH')
except:
    log_error("One or more env variables missing! Exiting now")
    exit(1)

aid = environ.get('AUTHORIZED_CHATS', '')
aid = aid.split()
for _id in aid:
    AUTHORIZED_CHATS.add(int(_id.strip()))

aid = environ.get('SUDO_USERS', '')
aid = aid.split()
for _id in aid:
    SUDO_USERS.add(int(_id.strip()))

fx = environ.get('EXTENSION_FILTER', '')
if len(fx) > 0:
    fx = fx.split()
    for x in fx:
        EXTENSION_FILTER.add(x.strip().lower())


IS_PREMIUM_USER = False
USER_SESSION_STRING = environ.get('USER_SESSION_STRING', '')
if len(USER_SESSION_STRING) == 0:
    log_info("Creating client from BOT_TOKEN")
    app = Client(name='pyrogram', api_id=int(TELEGRAM_API), api_hash=TELEGRAM_HASH, bot_token=BOT_TOKEN, parse_mode=enums.ParseMode.HTML, no_updates=True)
else:
    log_info("Creating client from USER_SESSION_STRING")
    app = Client(name='pyrogram', api_id=int(TELEGRAM_API), api_hash=TELEGRAM_HASH, session_string=USER_SESSION_STRING, parse_mode=enums.ParseMode.HTML, no_updates=True)
    with app:
        IS_PREMIUM_USER = app.me.is_premium

RSS_USER_SESSION_STRING = environ.get('RSS_USER_SESSION_STRING', '')
if len(RSS_USER_SESSION_STRING) == 0:
    rss_session = None
else:
    log_info("Creating client from RSS_USER_SESSION_STRING")
    rss_session = Client(name='rss_session', api_id=int(TELEGRAM_API), api_hash=TELEGRAM_HASH, session_string=RSS_USER_SESSION_STRING, parse_mode=enums.ParseMode.HTML, no_updates=True)

def aria2c_init():
    try:
        log_info("Initializing Aria2c")
        link = "https://linuxmint.com/torrents/lmde-5-cinnamon-64bit.iso.torrent"
        dire = DOWNLOAD_DIR.rstrip("/")
        aria2.add_uris([link], {'dir': dire})
        sleep(3)
        downloads = aria2.get_downloads()
        sleep(20)
        for download in downloads:
            aria2.remove([download], force=True, files=True)
    except Exception as e:
        log_error(f"Aria2c initializing error: {e}")
Thread(target=aria2c_init).start()
sleep(1.5)

MEGA_API_KEY = environ.get('MEGA_API_KEY', '')
if len(MEGA_API_KEY) == 0:
    log_warning('MEGA API KEY not provided!')
    MEGA_API_KEY = None

MEGA_EMAIL_ID = environ.get('MEGA_EMAIL_ID', '')
MEGA_PASSWORD = environ.get('MEGA_PASSWORD', '')
if len(MEGA_EMAIL_ID) == 0 or len(MEGA_PASSWORD) == 0:
    log_warning('MEGA Credentials not provided!')
    MEGA_EMAIL_ID = None
    MEGA_PASSWORD = None

DB_URI = environ.get('DATABASE_URL', '')
if len(DB_URI) == 0:
    DB_URI = None

MAX_SPLIT_SIZE = 4194304000 if IS_PREMIUM_USER else 2097152000

LEECH_SPLIT_SIZE = environ.get('LEECH_SPLIT_SIZE', '')
if len(LEECH_SPLIT_SIZE) == 0 or int(LEECH_SPLIT_SIZE) > MAX_SPLIT_SIZE:
    LEECH_SPLIT_SIZE = MAX_SPLIT_SIZE
else:
    LEECH_SPLIT_SIZE = int(LEECH_SPLIT_SIZE)

DUMP_CHAT = environ.get('DUMP_CHAT', '')
if len(DUMP_CHAT) == 0:
    DUMP_CHAT = None
else:
    DUMP_CHAT = int(DUMP_CHAT)

STATUS_LIMIT = environ.get('STATUS_LIMIT', '')
if len(STATUS_LIMIT) == 0:
    STATUS_LIMIT = None
else:
    STATUS_LIMIT = int(STATUS_LIMIT)

UPTOBOX_TOKEN = environ.get('UPTOBOX_TOKEN', '')
if len(UPTOBOX_TOKEN) == 0:
    UPTOBOX_TOKEN = None

INDEX_URL = environ.get('INDEX_URL', '').rstrip("/")
if len(INDEX_URL) == 0:
    INDEX_URL = None
    INDEX_URLS.append(None)
else:
    INDEX_URLS.append(INDEX_URL)

SEARCH_API_LINK = environ.get('SEARCH_API_LINK', '').rstrip("/")
if len(SEARCH_API_LINK) == 0:
    SEARCH_API_LINK = None

SEARCH_LIMIT = environ.get('SEARCH_LIMIT', '')
if len(SEARCH_LIMIT) == 0:
    SEARCH_LIMIT = 0
else:
    SEARCH_LIMIT = int(SEARCH_LIMIT)

RSS_COMMAND = environ.get('RSS_COMMAND', '')
if len(RSS_COMMAND) == 0:
    RSS_COMMAND = None

CMD_INDEX = environ.get('CMD_INDEX', '')

RSS_CHAT_ID = environ.get('RSS_CHAT_ID', '')
if len(RSS_CHAT_ID) == 0:
    RSS_CHAT_ID = None
else:
    RSS_CHAT_ID = int(RSS_CHAT_ID)

RSS_DELAY = environ.get('RSS_DELAY', '')
if len(RSS_DELAY) == 0:
    RSS_DELAY = 900
else:
    RSS_DELAY = int(RSS_DELAY)

TORRENT_TIMEOUT = environ.get('TORRENT_TIMEOUT', '')
if len(TORRENT_TIMEOUT) == 0:
    TORRENT_TIMEOUT = None
else:
    TORRENT_TIMEOUT = int(TORRENT_TIMEOUT)

BASE_URL = environ.get('BASE_URL_OF_BOT', '').rstrip("/")
if len(BASE_URL) == 0:
    log_warning('BASE_URL_OF_BOT not provided!')
    BASE_URL = None

CUSTOM_FILENAME = environ.get('CUSTOM_FILENAME', '')
if len(CUSTOM_FILENAME) == 0:
    CUSTOM_FILENAME = None

SEARCH_PLUGINS = environ.get('SEARCH_PLUGINS', '')
if len(SEARCH_PLUGINS) == 0:
    SEARCH_PLUGINS = None
else:
    SEARCH_PLUGINS = jsonloads(SEARCH_PLUGINS)

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

IGNORE_PENDING_REQUESTS = environ.get('IGNORE_PENDING_REQUESTS', '')
IGNORE_PENDING_REQUESTS = IGNORE_PENDING_REQUESTS.lower() == 'true'

AS_DOCUMENT = environ.get('AS_DOCUMENT', '')
AS_DOCUMENT = AS_DOCUMENT.lower() == 'true'

EQUAL_SPLITS = environ.get('EQUAL_SPLITS', '')
EQUAL_SPLITS = EQUAL_SPLITS.lower() == 'true'

TOKEN_PICKLE_URL = environ.get('TOKEN_PICKLE_URL', '')
if len(TOKEN_PICKLE_URL) != 0:
    try:
        res = rget(TOKEN_PICKLE_URL)
        if res.status_code == 200:
            with open('token.pickle', 'wb+') as f:
                f.write(res.content)
        else:
            log_error(f"Failed to download token.pickle, link got HTTP response: {res.status_code}")
    except Exception as e:
        log_error(f"TOKEN_PICKLE_URL: {e}")

ACCOUNTS_ZIP_URL = environ.get('ACCOUNTS_ZIP_URL', '')
if len(ACCOUNTS_ZIP_URL) != 0:
    try:
        res = rget(ACCOUNTS_ZIP_URL)
        if res.status_code == 200:
            with open('accounts.zip', 'wb+') as f:
                f.write(res.content)
            srun(["unzip", "-q", "-o", "accounts.zip"])
            srun(["chmod", "-R", "777", "accounts"])
            osremove("accounts.zip")
        else:
            log_error(f"Failed to download accounts.zip, link got HTTP response: {res.status_code}")
    except Exception as e:
        log_error(f"ACCOUNTS_ZIP_URL: {e}")

MULTI_SEARCH_URL = environ.get('MULTI_SEARCH_URL', '')
if len(MULTI_SEARCH_URL) != 0:
    try:
        res = rget(MULTI_SEARCH_URL)
        if res.status_code == 200:
            with open('drive_folder', 'wb+') as f:
                f.write(res.content)
        else:
            log_error(f"Failed to download drive_folder, link got HTTP response: {res.status_code}")
    except Exception as e:
        log_error(f"MULTI_SEARCH_URL: {e}")

YT_COOKIES_URL = environ.get('YT_COOKIES_URL', '')
if len(YT_COOKIES_URL) != 0:
    try:
        res = rget(YT_COOKIES_URL)
        if res.status_code == 200:
            with open('cookies.txt', 'wb+') as f:
                f.write(res.content)
        else:
            log_error(f"Failed to download cookies.txt, link got HTTP response: {res.status_code}")
    except Exception as e:
        log_error(f"YT_COOKIES_URL: {e}")

DRIVES_NAMES.append("Main")
DRIVES_IDS.append(parent_id)
if ospath.exists('drive_folder'):
    with open('drive_folder', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            temp = line.strip().split()
            DRIVES_IDS.append(temp[1])
            DRIVES_NAMES.append(temp[0].replace("_", " "))
            if len(temp) > 2:
                INDEX_URLS.append(temp[2])
            else:
                INDEX_URLS.append(None)

updater = tgUpdater(token=BOT_TOKEN, request_kwargs={'read_timeout': 20, 'connect_timeout': 15})
bot = updater.bot
dispatcher = updater.dispatcher
job_queue = updater.job_queue
botname = bot.username
