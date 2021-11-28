import time
import requests
import os
import logging

from requests.exceptions import RequestException

BASE_URL = os.environ.get('BASE_URL_OF_BOT', None)
try:
    if len(BASE_URL) == 0:
        raise TypeError
except TypeError:
    BASE_URL = None
PORT = os.environ.get('PORT', None)
if PORT is not None and BASE_URL is not None:
    while True:
        try:
            requests.get(BASE_URL).status_code
            time.sleep(600)
        except RequestException as e:
            logging.error(str(e))
            continue
