import logging
import os
import threading
import time

import aria2p
import telegram.ext as tg
from dotenv import load_dotenv
import socket
import faulthandler
faulthandler.enable()

socket.setdefaulttimeout(600)

botStartTime = time.time()
if os.path.exists('log.txt'):
    with open('log.txt', 'r+') as f:
        f.truncate(0)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('log.txt'), logging.StreamHandler()],
                    level=logging.INFO)

load_dotenv('config.env')

Interval = []


def getConfig(name: str):
    return os.environ[name]


LOGGER = logging.getLogger(__name__)

try:
    if bool(getConfig('_____REMOVE_THIS_LINE_____')):
        logging.error('The README.md file there to be read! Exiting now!')
        exit()
except KeyError:
    pass

aria2 = aria2p.API(
    aria2p.Client(
        host="http://localhost",
        port=6800,
        secret="",
    )
)

DOWNLOAD_DIR = None
BOT_TOKEN = None

download_dict_lock = threading.Lock()
status_reply_dict_lock = threading.Lock()
# Key: update.effective_chat.id
# Value: telegram.Message
status_reply_dict = {}
# Key: update.message.message_id
# Value: An object of Status
download_dict = {}
# Stores list of users and chats the bot is authorized to use in
AUTHORIZED_CHATS = set()
if os.path.exists('authorized_chats.txt'):
    with open('authorized_chats.txt', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            #    LOGGER.info(line.split())
            AUTHORIZED_CHATS.add(int(line.split()[0]))
try:
    BOT_TOKEN = getConfig('BOT_TOKEN')
    parent_id = getConfig('GDRIVE_FOLDER_ID')
    telegraph_token = getConfig('TELEGRAPH_TOKEN')
    DOWNLOAD_DIR = getConfig('DOWNLOAD_DIR')
    if DOWNLOAD_DIR[-1] != '/' or DOWNLOAD_DIR[-1] != '\\':
        DOWNLOAD_DIR = DOWNLOAD_DIR + '/'
    DOWNLOAD_STATUS_UPDATE_INTERVAL = int(getConfig('DOWNLOAD_STATUS_UPDATE_INTERVAL'))
    OWNER_ID = int(getConfig('OWNER_ID'))
    AUTO_DELETE_MESSAGE_DURATION = int(getConfig('AUTO_DELETE_MESSAGE_DURATION'))
    USER_SESSION_STRING = getConfig('USER_SESSION_STRING')
    TELEGRAM_API = getConfig('TELEGRAM_API')
    TELEGRAM_HASH = getConfig('TELEGRAM_HASH')
except KeyError as e:
    LOGGER.error("One or more env variables missing! Exiting now")
    exit(1)

try:
    MEGA_API_KEY = getConfig('MEGA_API_KEY')
except KeyError:
    logging.warning('MEGA API KEY not provided!')
    MEGA_API_KEY = None
try:
    MEGA_EMAIL_ID = getConfig('MEGA_EMAIL_ID')
    MEGA_PASSWORD = getConfig('MEGA_PASSWORD')
    if len(MEGA_EMAIL_ID) == 0 or len(MEGA_PASSWORD) == 0:
        raise KeyError
except KeyError:
    logging.warning('MEGA Credentials not provided!')
    MEGA_EMAIL_ID = None
    MEGA_PASSWORD = None
try:
    INDEX_URL = getConfig('INDEX_URL')
    if len(INDEX_URL) == 0:
        INDEX_URL = None
except KeyError:
    INDEX_URL = None
try:
    BUTTON_THREE_NAME = getConfig('BUTTON_THREE_NAME')
    BUTTON_THREE_URL = getConfig('BUTTON_THREE_URL')
    if len(BUTTON_THREE_NAME) == 0 or len(BUTTON_THREE_URL) == 0:
        raise KeyError
except KeyError:
    BUTTON_THREE_NAME = None
    BUTTON_THREE_URL = None
try:
    BUTTON_FOUR_NAME = getConfig('BUTTON_FOUR_NAME')
    BUTTON_FOUR_URL = getConfig('BUTTON_FOUR_URL')
    if len(BUTTON_FOUR_NAME) == 0 or len(BUTTON_FOUR_URL) == 0:
        raise KeyError
except KeyError:
    BUTTON_FOUR_NAME = None
    BUTTON_FOUR_URL = None
try:
    BUTTON_FIVE_NAME = getConfig('BUTTON_FIVE_NAME')
    BUTTON_FIVE_URL = getConfig('BUTTON_FIVE_URL')
    if len(BUTTON_FIVE_NAME) == 0 or len(BUTTON_FIVE_URL) == 0:
        raise KeyError
except KeyError:
    BUTTON_FIVE_NAME = None
    BUTTON_FIVE_URL = None
try:
    STOP_DUPLICATE_MIRROR = getConfig('STOP_DUPLICATE_MIRROR')
    if STOP_DUPLICATE_MIRROR.lower() == 'true':
        STOP_DUPLICATE_MIRROR = True
    else:
        STOP_DUPLICATE_MIRROR = False
except KeyError:
    STOP_DUPLICATE_MIRROR = False
try:
    IS_TEAM_DRIVE = getConfig('IS_TEAM_DRIVE')
    if IS_TEAM_DRIVE.lower() == 'true':
        IS_TEAM_DRIVE = True
    else:
        IS_TEAM_DRIVE = False
except KeyError:
    IS_TEAM_DRIVE = False

try:
    USE_SERVICE_ACCOUNTS = getConfig('USE_SERVICE_ACCOUNTS')
    if USE_SERVICE_ACCOUNTS.lower() == 'true':
        USE_SERVICE_ACCOUNTS = True
    else:
        USE_SERVICE_ACCOUNTS = False
except KeyError:
    USE_SERVICE_ACCOUNTS = False

try:
    BLOCK_MEGA_LINKS = getConfig('BLOCK_MEGA_LINKS')
    if BLOCK_MEGA_LINKS.lower() == 'true':
        BLOCK_MEGA_LINKS = True
    else:
        BLOCK_MEGA_LINKS = False
except KeyError:
    BLOCK_MEGA_LINKS = False

try:
    SHORTENER = getConfig('SHORTENER')
    SHORTENER_API = getConfig('SHORTENER_API')
    if len(SHORTENER) == 0 or len(SHORTENER_API) == 0:
        raise KeyError
except KeyError:
    SHORTENER = None
    SHORTENER_API = None

updater = tg.Updater(token=BOT_TOKEN,use_context=True)
bot = updater.bot
dispatcher = updater.dispatcher
