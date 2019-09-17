import logging
import configparser
from telegram.ext import Updater

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)


config = configparser.ConfigParser()
config.read('bot/config.ini')


def getConfig(name: str):
   return config['DEFAULT'][name]
                    
LOGGER = logging.getLogger(__name__)

try:
    if bool(config['DEFAULT']['_____REMOVE_THIS_LINE_____']):
        logging.ERROR('The README.md file there to be read! Exiting now!')
        exit()
except KeyError:
    pass
   
BOT_TOKEN = getConfig('BOT_TOKEN')
updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher