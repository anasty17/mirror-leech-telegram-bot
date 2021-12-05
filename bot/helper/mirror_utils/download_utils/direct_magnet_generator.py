# Magnet Scraper Implement By - @VarnaX-279

import re
import time
import cloudscraper
from bs4 import BeautifulSoup

from cloudscraper.exceptions import CloudflareChallengeError

from bot.helper.ext_utils import bot_utils
from bot.helper.ext_utils.exceptions import DirectTorrentMagnetException

def direct_magnet_generator(link: str):
    ''' Magnet Scraper '''
    if bot_utils.is_magnet(link):
        return link
    if 'thepiratebay' in link:
        return get_tpy(link)
    elif '1337x' in link:
        return get_1337x(link)
    elif 'rarbg' in link:
        raise DirectTorrentMagnetException("We Can't extract magnet from rarbg official.\nUse rargb.to")
    else:
        return get_torrent_magnet(link)

def get_tpy(link):
    tpyid = link.split('?id=')[1]
    tpy_link = f'https://tpb.party/torrent/{tpyid}'
    return get_torrent_magnet(tpy_link)

def get_1337x(link):
    x1337id = link.split('/torrent/')[-1]
    x1337_link = f'https://1337x.to/torrent/{x1337id}'
    return get_torrent_magnet(x1337_link)

def get_torrent_magnet(url, is2nd=False):
    scraper = cloudscraper.create_scraper()
    try:
        source = scraper.get(url)
        soup = BeautifulSoup(source.content, 'lxml')
        magnet_soup = soup.find('a', attrs={'href': re.compile("^magnet")})
        magnet = magnet_soup.get('href')
        return magnet
    except AttributeError:
        print('AttributeError')
        return url
    except CloudflareChallengeError:
        if is2nd:
            raise DirectTorrentMagnetException('Detected a Cloudflare version 2 challenge, Try again')
        else:
            time.sleep(3)
            return get_torrent_magnet(url, is2nd=True)
