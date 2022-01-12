# Implemented by https://github.com/junedkh

import random

from pyshorteners import Shortener as pyShortener
from requests import get as rget
from base64 import b64encode
from urllib.parse import quote
from urllib3 import disable_warnings

from bot import LOGGER, SHORTENER, SHORTENER_API


def short_url(longurl):
    if SHORTENER is None and SHORTENER_API is None:
        return longurl

    if "shorte.st" in SHORTENER:
        disable_warnings()
        link = rget(f'http://api.shorte.st/stxt/{SHORTENER_API}/{longurl}', verify=False).text
    elif "linkvertise" in SHORTENER:
        url = quote(b64encode(longurl.encode("utf-8")))
        linkvertise = [
            f"https://link-to.net/{SHORTENER_API}/{random.random() * 1000}/dynamic?r={url}",
            f"https://up-to-down.net/{SHORTENER_API}/{random.random() * 1000}/dynamic?r={url}",
            f"https://direct-link.net/{SHORTENER_API}/{random.random() * 1000}/dynamic?r={url}",
            f"https://file-link.net/{SHORTENER_API}/{random.random() * 1000}/dynamic?r={url}"]
        link = random.choice(linkvertise)
    elif "bitly.com" in SHORTENER:
        s = pyShortener(api_key=SHORTENER_API)
        link = s.bitly.short(longurl)
    elif "ouo.io" in SHORTENER:
        disable_warnings()
        link = rget(f'http://ouo.io/api/{SHORTENER_API}?s={longurl}', verify=False).text
    else:
        link = rget(f'https://{SHORTENER}/api?api={SHORTENER_API}&url={longurl}&format=text').text

    if len(link) == 0:
        LOGGER.error("Something is Wrong with the url shortener")
        return longurl
    return link
