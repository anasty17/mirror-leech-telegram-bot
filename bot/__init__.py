import logging
import configparser
import aria2p
import threading
from telegram.ext import Updater

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

config = configparser.ConfigParser()
config.read('bot/config.ini')


def getConfig(name: str):
    return config['DEFAULT'][name]


LOGGER = logging.getLogger(__name__)

try:
    if bool(getConfig('_____REMOVE_THIS_LINE_____')):
        logging.ERROR('The README.md file there to be read! Exiting now!')
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
status_reply_dict = {}
download_dict = {}
# Stores list of users and chats the bot is authorized to use in
AUTHORIZED_CHATS = []
with open('authorized_chats.txt', 'r+') as f:
    lines = f.readlines()
    for line in lines:
        LOGGER.info(line.split())
        AUTHORIZED_CHATS.append(int(line.split()[0]))
try:
    BOT_TOKEN = getConfig('BOT_TOKEN')
    parent_id = getConfig('GDRIVE_FOLDER_ID')
    DOWNLOAD_DIR = getConfig('DOWNLOAD_DIR')
    if DOWNLOAD_DIR[-1] != '/' or DOWNLOAD_DIR[-1] != '\\':
        DOWNLOAD_DIR = DOWNLOAD_DIR + '/'
    DOWNLOAD_STATUS_UPDATE_INTERVAL = int(getConfig('DOWNLOAD_STATUS_UPDATE_INTERVAL'))
    OWNER_ID = int(getConfig('OWNER_ID'))
except KeyError as e:
    LOGGER.error("One or more env variables missing! Exiting now")
    exit(1)

updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher
