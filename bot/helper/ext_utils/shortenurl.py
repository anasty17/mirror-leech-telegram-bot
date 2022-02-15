# Implemented by https://github.com/junedkh

from random import random, choice

from cfscrape import create_scraper
from base64 import b64encode
from urllib.parse import quote, unquote
from urllib3 import disable_warnings

from bot import LOGGER, SHORTENER, SHORTENER_API


def short_url(longurl):
    if SHORTENER is None and SHORTENER_API is None:
        return longurl
    cget = create_scraper().get
    try:
        unquote(longurl).encode('ascii')
        if "{" in unquote(longurl) or "}" in unquote(longurl):
            raise TypeError
    except (UnicodeEncodeError, TypeError):
        longurl = cget('http://tinyurl.com/api-create.php', params=dict(url=longurl)).text
    if "shorte.st" in SHORTENER:
        disable_warnings()
        link = cget(f'http://api.shorte.st/stxt/{SHORTENER_API}/{longurl}', verify=False).text
    elif "linkvertise" in SHORTENER:
        url = quote(b64encode(longurl.encode("utf-8")))
        linkvertise = [
            f"https://link-to.net/{SHORTENER_API}/{random() * 1000}/dynamic?r={url}",
            f"https://up-to-down.net/{SHORTENER_API}/{random() * 1000}/dynamic?r={url}",
            f"https://direct-link.net/{SHORTENER_API}/{random() * 1000}/dynamic?r={url}",
            f"https://file-link.net/{SHORTENER_API}/{random() * 1000}/dynamic?r={url}"]
        link = choice(linkvertise)
    elif "bitly.com" in SHORTENER:
        shorten_url = "https://api-ssl.bit.ly/v4/shorten"
        params = {"long_url": longurl}
        headers = {"Authorization": f"Bearer {SHORTENER_API}"}
        response = create_scraper().post(shorten_url, json=params, headers=headers).json()
        link = response["link"]
    elif "ouo.io" in SHORTENER:
        disable_warnings()
        link = cget(f'http://ouo.io/api/{SHORTENER_API}?s={longurl}', verify=False).text
    else:
        link = cget(f'https://{SHORTENER}/api?api={SHORTENER_API}&url={quote(longurl)}&format=text').text

    if len(link) == 0:
        LOGGER.error("Something is Wrong with the url shortener")
        return longurl
    return link