# Copyright (C) 2019 The Raphielscape Company LLC.
#
# Licensed under the Raphielscape Public License, Version 1.c (the "License");
# you may not use this file except in compliance with the License.
#
""" Helper Module containing various sites direct links generators. This module is copied and modified as per need
from https://github.com/AvinashReddy3108/PaperplaneExtended . I hereby take no credit of the following code other
than the modifications. See https://github.com/AvinashReddy3108/PaperplaneExtended/commits/master/userbot/modules/direct_links.py
for original authorship. """

from http.cookiejar import MozillaCookieJar
from json import loads
from os import path
from re import findall, match, search, sub
from time import sleep
from urllib.parse import parse_qs, quote, unquote, urlparse
from uuid import uuid4

from bs4 import BeautifulSoup
from cloudscraper import create_scraper
from lk21 import Bypass
from lxml import etree

from bot import config_dict
from bot.helper.ext_utils.bot_utils import get_readable_time, is_share_link
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException

fmed_list = ['fembed.net', 'fembed.com', 'femax20.com', 'fcdn.stream', 'feurl.com', 'layarkacaxxi.icu',
             'naniplay.nanime.in', 'naniplay.nanime.biz', 'naniplay.com', 'mm9842.com']

anonfilesBaseSites = ['anonfiles.com', 'hotfile.io', 'bayfiles.com', 'megaupload.nz', 'letsupload.cc',
                      'filechan.org', 'myfile.is', 'vshare.is', 'rapidshare.nu', 'lolabits.se',
                      'openload.cc', 'share-online.is', 'upvid.cc']


def direct_link_generator(link: str):
    """ direct links generator """
    domain = urlparse(link).hostname
    if not domain:
        raise DirectDownloadLinkException("ERROR: Invalid URL")
    if 'youtube.com' in domain or 'youtu.be' in domain:
        raise DirectDownloadLinkException(
            "ERROR: Use ytdl cmds for Youtube links")
    elif 'yadi.sk' in domain or 'disk.yandex.com' in domain:
        return yandex_disk(link)
    elif 'mediafire.com' in domain:
        return mediafire(link)
    elif 'uptobox.com' in domain:
        return uptobox(link)
    elif 'osdn.net' in domain:
        return osdn(link)
    elif 'github.com' in domain:
        return github(link)
    elif 'hxfile.co' in domain:
        return hxfile(link)
    elif '1drv.ms' in domain:
        return onedrive(link)
    elif 'pixeldrain.com' in domain:
        return pixeldrain(link)
    elif 'antfiles.com' in domain:
        return antfiles(link)
    elif 'streamtape.com' in domain:
        return streamtape(link)
    elif 'racaty' in domain:
        return racaty(link)
    elif '1fichier.com' in domain:
        return fichier(link)
    elif 'solidfiles.com' in domain:
        return solidfiles(link)
    elif 'krakenfiles.com' in domain:
        return krakenfiles(link)
    elif 'upload.ee' in domain:
        return uploadee(link)
    elif 'akmfiles' in domain:
        return akmfiles(link)
    elif 'linkbox' in domain:
        return linkbox(link)
    elif 'shrdsk' in domain:
        return shrdsk(link)
    elif 'letsupload.io' in domain:
        return letsupload(link)
    elif any(x in domain for x in ['wetransfer.com', 'we.tl']):
        return wetransfer(link)
    elif any(x in domain for x in anonfilesBaseSites):
        return anonfilesBased(link)
    elif any(x in domain for x in ['terabox', 'nephobox', '4funbox', 'mirrobox', 'momerybox', 'teraboxapp']):
        return terabox(link)
    elif any(x in domain for x in fmed_list):
        return fembed(link)
    elif any(x in domain for x in ['sbembed.com', 'watchsb.com', 'streamsb.net', 'sbplay.org']):
        return sbembed(link)
    elif is_share_link(link):
        if 'gdtot' in domain:
            return gdtot(link)
        elif 'filepress' in domain:
            return filepress(link)
        else:
            return sharer_scraper(link)
    elif 'zippyshare.com' in domain:
        raise DirectDownloadLinkException('ERROR: R.I.P Zippyshare')
    else:
        raise DirectDownloadLinkException(
            f'No Direct link function found for {link}')


def yandex_disk(url: str) -> str:
    """ Yandex.Disk direct link generator
    Based on https://github.com/wldhx/yadisk-direct """
    try:
        link = findall(r'\b(https?://(yadi.sk|disk.yandex.com)\S+)', url)[0][0]
    except IndexError:
        return "No Yandex.Disk links found\n"
    api = 'https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={}'
    cget = create_scraper().request
    try:
        return cget('get', api.format(link)).json()['href']
    except KeyError:
        raise DirectDownloadLinkException(
            "ERROR: File not found/Download limit reached")


def uptobox(url: str) -> str:
    """ Uptobox direct link generator
    based on https://github.com/jovanzers/WinTenCermin and https://github.com/sinoobie/noobie-mirror """
    try:
        link = findall(r'\bhttps?://.*uptobox\.com\S+', url)[0]
    except IndexError:
        raise DirectDownloadLinkException("No Uptobox links found")
    if link := findall(r'\bhttps?://.*\.uptobox\.com/dl\S+', url):
        return link[0]
    cget = create_scraper().request
    try:
        file_id = findall(r'\bhttps?://.*uptobox\.com/(\w+)', url)[0]
        if UPTOBOX_TOKEN := config_dict['UPTOBOX_TOKEN']:
            file_link = f'https://uptobox.com/api/link?token={UPTOBOX_TOKEN}&file_code={file_id}'
        else:
            file_link = f'https://uptobox.com/api/link?file_code={file_id}'
        res = cget('get', file_link).json()
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    if res['statusCode'] == 0:
        return res['data']['dlLink']
    elif res['statusCode'] == 16:
        sleep(1)
        waiting_token = res["data"]["waitingToken"]
        sleep(res["data"]["waiting"])
    elif res['statusCode'] == 39:
        raise DirectDownloadLinkException(
            f"ERROR: Uptobox is being limited please wait {get_readable_time(res['data']['waiting'])}")
    else:
        raise DirectDownloadLinkException(f"ERROR: {res['message']}")
    try:
        res = cget('get', f"{file_link}&waitingToken={waiting_token}").json()
        return res['data']['dlLink']
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")


def mediafire(url: str) -> str:
    if final_link := findall(r'https?:\/\/download\d+\.mediafire\.com\/\S+\/\S+\/\S+', url):
        return final_link[0]
    cget = create_scraper().request
    try:
        url = cget('get', url).url
        page = cget('get', url).text
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    if not (final_link := findall(r"\'(https?:\/\/download\d+\.mediafire\.com\/\S+\/\S+\/\S+)\'", page)):
        raise DirectDownloadLinkException("ERROR: No links found in this page")
    return final_link[0]


def osdn(url: str) -> str:
    """ OSDN direct link generator """
    osdn_link = 'https://osdn.net'
    try:
        link = findall(r'\bhttps?://.*osdn\.net\S+', url)[0]
    except IndexError:
        raise DirectDownloadLinkException("No OSDN links found")
    cget = create_scraper().request
    try:
        page = BeautifulSoup(
            cget('get', link, allow_redirects=True).content, 'lxml')
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    info = page.find('a', {'class': 'mirror_link'})
    link = unquote(osdn_link + info['href'])
    mirrors = page.find('form', {'id': 'mirror-select-form'}).findAll('tr')
    urls = []
    for data in mirrors[1:]:
        mirror = data.find('input')['value']
        urls.append(sub(r'm=(.*)&f', f'm={mirror}&f', link))
    return urls[0]


def github(url: str) -> str:
    """ GitHub direct links generator """
    try:
        findall(r'\bhttps?://.*github\.com.*releases\S+', url)[0]
    except IndexError:
        raise DirectDownloadLinkException("No GitHub Releases links found")
    cget = create_scraper().request
    download = cget('get', url, stream=True, allow_redirects=False)
    try:
        return download.headers["location"]
    except KeyError:
        raise DirectDownloadLinkException("ERROR: Can't extract the link")


def hxfile(url: str) -> str:
    """ Hxfile direct link generator
    Based on https://github.com/zevtyardt/lk21
    """
    try:
        return Bypass().bypass_filesIm(url)
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")


def letsupload(url: str) -> str:
    cget = create_scraper().request
    try:
        res = cget("POST", url)
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if direct_link := findall(r"(https?://letsupload\.io\/.+?)\'", res.text):
        return direct_link[0]
    else:
        raise DirectDownloadLinkException('ERROR: Direct Link not found')


def anonfilesBased(url: str) -> str:
    cget = create_scraper().request
    try:
        soup = BeautifulSoup(cget('get', url).content, 'lxml')
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    if sa := soup.find(id="download-url"):
        return sa['href']
    raise DirectDownloadLinkException("ERROR: File not found!")


def fembed(link: str) -> str:
    """ Fembed direct link generator
    Based on https://github.com/zevtyardt/lk21
    """
    try:
        dl_url = Bypass().bypass_fembed(link)
        count = len(dl_url)
        lst_link = [dl_url[i] for i in dl_url]
        return lst_link[count-1]
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")


def sbembed(link: str) -> str:
    """ Sbembed direct link generator
    Based on https://github.com/zevtyardt/lk21
    """
    try:
        dl_url = Bypass().bypass_sbembed(link)
        count = len(dl_url)
        lst_link = [dl_url[i] for i in dl_url]
        return lst_link[count-1]
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")


def onedrive(link: str) -> str:
    """ Onedrive direct link generator
    By https://github.com/junedkh """
    cget = create_scraper().request
    try:
        link = cget('get', link).url
        parsed_link = urlparse(link)
        link_data = parse_qs(parsed_link.query)
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    if not link_data:
        raise DirectDownloadLinkException("ERROR: Unable to find link_data")
    folder_id = link_data.get('resid')
    if not folder_id:
        raise DirectDownloadLinkException('ERROR: folder id not found')
    folder_id = folder_id[0]
    authkey = link_data.get('authkey')
    if not authkey:
        raise DirectDownloadLinkException('ERROR: authkey not found')
    authkey = authkey[0]
    boundary = uuid4()
    headers = {'content-type': f'multipart/form-data;boundary={boundary}'}
    data = f'--{boundary}\r\nContent-Disposition: form-data;name=data\r\nPrefer: Migration=EnableRedirect;FailOnMigratedFiles\r\nX-HTTP-Method-Override: GET\r\nContent-Type: application/json\r\n\r\n--{boundary}--'
    try:
        resp = cget(
            'get', f'https://api.onedrive.com/v1.0/drives/{folder_id.split("!", 1)[0]}/items/{folder_id}?$select=id,@content.downloadUrl&ump=1&authKey={authkey}', headers=headers, data=data).json()
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if "@content.downloadUrl" not in resp:
        raise DirectDownloadLinkException('ERROR: Direct link not found')
    return resp['@content.downloadUrl']


def pixeldrain(url: str) -> str:
    """ Based on https://github.com/yash-dk/TorToolkit-Telegram """
    url = url.strip("/ ")
    file_id = url.split("/")[-1]
    if url.split("/")[-2] == "l":
        info_link = f"https://pixeldrain.com/api/list/{file_id}"
        dl_link = f"https://pixeldrain.com/api/list/{file_id}/zip"
    else:
        info_link = f"https://pixeldrain.com/api/file/{file_id}/info"
        dl_link = f"https://pixeldrain.com/api/file/{file_id}"
    cget = create_scraper().request
    try:
        resp = cget('get', info_link).json()
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    if resp["success"]:
        return dl_link
    else:
        raise DirectDownloadLinkException(
            f"ERROR: Cant't download due {resp['message']}.")


def antfiles(url: str) -> str:
    """ Antfiles direct link generator
    Based on https://github.com/zevtyardt/lk21
    """
    try:
        link = Bypass().bypass_antfiles(url)
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    if not link:
        raise DirectDownloadLinkException("ERROR: Download link not found")
    return link


def streamtape(url: str) -> str:
    """ Streamtape direct link generator
    Based on https://github.com/zevtyardt/lk21
    """
    try:
        link = Bypass().bypass_streamtape(url)
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    if not link:
        raise DirectDownloadLinkException("ERROR: Download link not found")
    return link


def racaty(url: str) -> str:
    """ Racaty direct link generator
    By https://github.com/junedkh """
    cget = create_scraper().request
    try:
        url = cget('GET', url).url
        json_data = {
            'op': 'download2',
            'id': url.split('/')[-1]
        }
        res = cget('POST', url, data=json_data)
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if (direct_link := etree.HTML(res.text).xpath("//a[contains(@id,'uniqueExpirylink')]/@href")):
        return direct_link[0]
    else:
        raise DirectDownloadLinkException('ERROR: Direct link not found')


def fichier(link: str) -> str:
    """ 1Fichier direct link generator
    Based on https://github.com/Maujar
    """
    regex = r"^([http:\/\/|https:\/\/]+)?.*1fichier\.com\/\?.+"
    gan = match(regex, link)
    if not gan:
        raise DirectDownloadLinkException(
            "ERROR: The link you entered is wrong!")
    if "::" in link:
        pswd = link.split("::")[-1]
        url = link.split("::")[-2]
    else:
        pswd = None
        url = link
    cget = create_scraper().request
    try:
        if pswd is None:
            req = cget('post', url)
        else:
            pw = {"pass": pswd}
            req = cget('post', url, data=pw)
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    if req.status_code == 404:
        raise DirectDownloadLinkException(
            "ERROR: File not found/The link you entered is wrong!")
    soup = BeautifulSoup(req.content, 'lxml')
    if soup.find("a", {"class": "ok btn-general btn-orange"}):
        if dl_url := soup.find("a", {"class": "ok btn-general btn-orange"})["href"]:
            return dl_url
        raise DirectDownloadLinkException(
            "ERROR: Unable to generate Direct Link 1fichier!")
    elif len(soup.find_all("div", {"class": "ct_warn"})) == 3:
        str_2 = soup.find_all("div", {"class": "ct_warn"})[-1]
        if "you must wait" in str(str_2).lower():
            if numbers := [int(word) for word in str(str_2).split() if word.isdigit()]:
                raise DirectDownloadLinkException(
                    f"ERROR: 1fichier is on a limit. Please wait {numbers[0]} minute.")
            else:
                raise DirectDownloadLinkException(
                    "ERROR: 1fichier is on a limit. Please wait a few minutes/hour.")
        elif "protect access" in str(str_2).lower():
            raise DirectDownloadLinkException(
                "ERROR: This link requires a password!\n\n<b>This link requires a password!</b>\n- Insert sign <b>::</b> after the link and write the password after the sign.\n\n<b>Example:</b> https://1fichier.com/?smmtd8twfpm66awbqz04::love you\n\n* No spaces between the signs <b>::</b>\n* For the password, you can use a space!")
        else:
            raise DirectDownloadLinkException(
                "ERROR: Failed to generate Direct Link from 1fichier!")
    elif len(soup.find_all("div", {"class": "ct_warn"})) == 4:
        str_1 = soup.find_all("div", {"class": "ct_warn"})[-2]
        str_3 = soup.find_all("div", {"class": "ct_warn"})[-1]
        if "you must wait" in str(str_1).lower():
            if numbers := [int(word) for word in str(str_1).split() if word.isdigit()]:
                raise DirectDownloadLinkException(
                    f"ERROR: 1fichier is on a limit. Please wait {numbers[0]} minute.")
            else:
                raise DirectDownloadLinkException(
                    "ERROR: 1fichier is on a limit. Please wait a few minutes/hour.")
        elif "bad password" in str(str_3).lower():
            raise DirectDownloadLinkException(
                "ERROR: The password you entered is wrong!")
        else:
            raise DirectDownloadLinkException(
                "ERROR: Error trying to generate Direct Link from 1fichier!")
    else:
        raise DirectDownloadLinkException(
            "ERROR: Error trying to generate Direct Link from 1fichier!")


def solidfiles(url: str) -> str:
    """ Solidfiles direct link generator
    Based on https://github.com/Xonshiz/SolidFiles-Downloader
    By https://github.com/Jusidama18 """
    cget = create_scraper().request
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36'
        }
        pageSource = cget('get', url, headers=headers).text
        mainOptions = str(
            search(r'viewerOptions\'\,\ (.*?)\)\;', pageSource).group(1))
        return loads(mainOptions)["downloadUrl"]
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")


def krakenfiles(page_link: str) -> str:
    """ krakenfiles direct link generator
    Based on https://github.com/tha23rd/py-kraken
    By https://github.com/junedkh """
    cget = create_scraper().request
    try:
        page_resp = cget('get', page_link)
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    soup = BeautifulSoup(page_resp.text, "lxml")
    try:
        token = soup.find("input", id="dl-token")["value"]
    except:
        raise DirectDownloadLinkException(
            f"ERROR: Page link is wrong: {page_link}")
    hashes = [
        item["data-file-hash"]
        for item in soup.find_all("div", attrs={"data-file-hash": True})
    ]
    if not hashes:
        raise DirectDownloadLinkException(
            f"ERROR: Hash not found for : {page_link}")
    dl_hash = hashes[0]
    payload = f'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name="token"\r\n\r\n{token}\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW--'
    headers = {
        "content-type": "multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW",
        "cache-control": "no-cache",
        "hash": dl_hash,
    }
    dl_link_resp = cget(
        'post', f"https://krakenfiles.com/download/{hash}", data=payload, headers=headers)
    dl_link_json = dl_link_resp.json()
    if "url" in dl_link_json:
        return dl_link_json["url"]
    else:
        raise DirectDownloadLinkException(
            f"ERROR: Failed to acquire download URL from kraken for : {page_link}")


def uploadee(url: str) -> str:
    """ uploadee direct link generator
    By https://github.com/iron-heart-x"""
    cget = create_scraper().request
    try:
        soup = BeautifulSoup(cget('get', url).content, 'lxml')
        sa = soup.find('a', attrs={'id': 'd_l'})
        return sa['href']
    except:
        raise DirectDownloadLinkException(
            f"ERROR: Failed to acquire download URL from upload.ee for : {url}")


def terabox(url) -> str:
    if not path.isfile('terabox.txt'):
        raise DirectDownloadLinkException("ERROR: terabox.txt not found")
    session = create_scraper()
    try:
        res = session.request('GET', url)
        key = res.url.split('?surl=')[-1]
        jar = MozillaCookieJar('terabox.txt')
        jar.load()
        session.cookies.update(jar)
        res = session.request(
            'GET', f'https://www.terabox.com/share/list?app_id=250528&shorturl={key}&root=1')
        result = res.json()['list']
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
    if len(result) > 1:
        raise DirectDownloadLinkException(
            "ERROR: Can't download mutiple files")
    result = result[0]
    if result['isdir'] != '0':
        raise DirectDownloadLinkException("ERROR: Can't download folder")
    return result['dlink']


def filepress(url):
    cget = create_scraper().request
    try:
        url = cget('GET', url).url
        raw = urlparse(url)
        json_data = {
            'id': raw.path.split('/')[-1],
            'method': 'publicDownlaod',
        }
        api = f'{raw.scheme}://{raw.hostname}/api/file/downlaod/'
        res = cget('POST', api, headers={
                   'Referer': f'{raw.scheme}://{raw.hostname}'}, json=json_data).json()
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if 'data' not in res:
        raise DirectDownloadLinkException(f'ERROR: {res["statusText"]}')
    return f'https://drive.google.com/uc?id={res["data"]}&export=download'


def gdtot(url):
    cget = create_scraper().request
    try:
        res = cget('GET', f'https://gdbot.xyz/file/{url.split("/")[-1]}')
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    token_url = etree.HTML(res.content).xpath(
        "//a[contains(@class,'inline-flex items-center justify-center')]/@href")
    if not token_url:
        try:
            url = cget('GET', url).url
            p_url = urlparse(url)
            res = cget(
                "GET", f"{p_url.scheme}://{p_url.hostname}/ddl/{url.split('/')[-1]}")
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
        if (drive_link := findall(r"myDl\('(.*?)'\)", res.text)) and "drive.google.com" in drive_link[0]:
            return drive_link[0]
        else:
            raise DirectDownloadLinkException(
                'ERROR: Drive Link not found, Try in your broswer')
    token_url = token_url[0]
    try:
        token_page = cget('GET', token_url)
    except Exception as e:
        raise DirectDownloadLinkException(
            f'ERROR: {e.__class__.__name__} with {token_url}')
    path = findall('\("(.*?)"\)', token_page.text)
    if not path:
        raise DirectDownloadLinkException('ERROR: Cannot bypass this')
    path = path[0]
    raw = urlparse(token_url)
    final_url = f'{raw.scheme}://{raw.hostname}{path}'
    return sharer_scraper(final_url)


def sharer_scraper(url):
    cget = create_scraper().request
    try:
        url = cget('GET', url).url
        raw = urlparse(url)
        header = {
            "useragent": "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/534.10 (KHTML, like Gecko) Chrome/7.0.548.0 Safari/534.10"}
        res = cget('GET', url, headers=header)
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    key = findall('"key",\s+"(.*?)"', res.text)
    if not key:
        raise DirectDownloadLinkException("ERROR: Key not found!")
    key = key[0]
    if not etree.HTML(res.content).xpath("//button[@id='drc']"):
        raise DirectDownloadLinkException(
            "ERROR: This link don't have direct download button")
    boundary = uuid4()
    headers = {
        'Content-Type': f'multipart/form-data; boundary=----WebKitFormBoundary{boundary}',
        'x-token': raw.hostname,
        'useragent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/534.10 (KHTML, like Gecko) Chrome/7.0.548.0 Safari/534.10'
    }

    data = f'------WebKitFormBoundary{boundary}\r\nContent-Disposition: form-data; name="action"\r\n\r\ndirect\r\n' \
        f'------WebKitFormBoundary{boundary}\r\nContent-Disposition: form-data; name="key"\r\n\r\n{key}\r\n' \
        f'------WebKitFormBoundary{boundary}\r\nContent-Disposition: form-data; name="action_token"\r\n\r\n\r\n' \
        f'------WebKitFormBoundary{boundary}--\r\n'
    try:
        res = cget("POST", url, cookies=res.cookies,
                   headers=headers, data=data).json()
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if "url" not in res:
        raise DirectDownloadLinkException(
            'ERROR: Drive Link not found, Try in your broswer')
    if "drive.google.com" in res["url"]:
        return res["url"]
    try:
        res = cget('GET', res["url"])
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if (drive_link := etree.HTML(res.content).xpath("//a[contains(@class,'btn')]/@href")) and "drive.google.com" in drive_link[0]:
        return drive_link[0]
    else:
        raise DirectDownloadLinkException(
            'ERROR: Drive Link not found, Try in your broswer')


def wetransfer(url):
    cget = create_scraper().request
    try:
        url = cget('GET', url).url
        json_data = {
            'security_hash': url.split('/')[-1],
            'intent': 'entire_transfer'
        }
        res = cget(
            'POST', f'https://wetransfer.com/api/v4/transfers/{url.split("/")[-2]}/download', json=json_data).json()
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if "direct_link" in res:
        return res["direct_link"]
    elif "message" in res:
        raise DirectDownloadLinkException(f"ERROR: {res['message']}")
    elif "error" in res:
        raise DirectDownloadLinkException(f"ERROR: {res['error']}")
    else:
        raise DirectDownloadLinkException("ERROR: cannot find direct link")


def akmfiles(url):
    cget = create_scraper().request
    try:
        url = cget('GET', url).url
        json_data = {
            'op': 'download2',
            'id': url.split('/')[-1]
        }
        res = cget('POST', url, data=json_data)
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if (direct_link := etree.HTML(res.content).xpath("//a[contains(@class,'btn btn-dow')]/@href")):
        return direct_link[0]
    else:
        raise DirectDownloadLinkException('ERROR: Direct link not found')


def shrdsk(url):
    cget = create_scraper().request
    try:
        url = cget('GET', url).url
        res = cget(
            'GET', f'https://us-central1-affiliate2apk.cloudfunctions.net/get_data?shortid={url.split("/")[-1]}')
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if res.status_code != 200:
        raise DirectDownloadLinkException(
            f'ERROR: Status Code {res.status_code}')
    res = res.json()
    if ("type" in res and res["type"].lower() == "upload" and "video_url" in res):
        return res["video_url"]
    raise DirectDownloadLinkException("ERROR: cannot find direct link")


def linkbox(url):
    cget = create_scraper().request
    try:
        url = cget('GET', url).url
        res = cget(
            'GET', f'https://www.linkbox.to/api/file/detail?itemId={url.split("/")[-1]}').json()
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if 'data' not in res:
        raise DirectDownloadLinkException('ERROR: Data not found!!')
    data = res['data']
    if not data:
        raise DirectDownloadLinkException('ERROR: Data is None!!')
    if 'itemInfo' not in data:
        raise DirectDownloadLinkException('ERROR: itemInfo not found!!')
    itemInfo = data['itemInfo']
    if 'url' not in itemInfo:
        raise DirectDownloadLinkException('ERROR: url not found in itemInfo!!')
    if "name" not in itemInfo:
        raise DirectDownloadLinkException(
            'ERROR: Name not found in itemInfo!!')
    name = quote(itemInfo["name"])
    raw = itemInfo['url'].split("/", 3)[-1]
    return f'https://wdl.nuplink.net/{raw}&filename={name}'
