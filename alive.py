import time
import requests
import os
import logging

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
        except Exception as e:
            logging.error(f"alive.py: {e}")
            time.sleep(2)
            continue
