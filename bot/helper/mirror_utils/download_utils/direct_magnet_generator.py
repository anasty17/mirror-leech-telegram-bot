# Magnet Scraper Implement By - @VarnaX-279

import re
import time
import cfscrape
from bs4 import BeautifulSoup

from bot.helper.ext_utils import bot_utils
from bot.helper.ext_utils.exceptions import DirectTorrentMagnetException

def direct_magnet_generator(link: str):
    if 'thepiratebay.org/' in link:
        return get_tpy(link)
    elif re.match(r'https?://.*1337x.*\/torrent\/\S+', link):
        return get_1337x(link)
    elif re.match(r'https?://.*rarbg.*\/torrent\/\S+', link):
        raise DirectTorrentMagnetException("Can't extract magnet from rarbg official domains.\nUse rargb.to")
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

def get_torrent_magnet(url, is2nd=False) -> str:
    scraper = cfscrape.create_scraper()
    try:
        source = scraper.get(url)
        soup = BeautifulSoup(source.content, 'lxml')
        magnet_soup = soup.find('a', attrs={'href': re.compile("^magnet")})
        magnet = magnet_soup.get('href')
        return magnet
    except AttributeError:
        raise DirectTorrentMagnetException('No magnet to export')
    except ValueError as e:
        if str(e).startswith('Unable to identify Cloudflare'):
            if is2nd:
                raise DirectTorrentMagnetException('ERROR: Detected a Cloudflare version 2 challenge, Unable to bypass this challenge.')
            else:
                return get_torrent_magnet(url, is2nd=True)
        else:
            raise DirectTorrentMagnetException(f"Magnet Extracting Error:- {e}")
