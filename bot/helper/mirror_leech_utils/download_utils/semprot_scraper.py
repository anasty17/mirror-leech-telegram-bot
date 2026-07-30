"""Semprot.com thread scraper.

Ports the Go implementation (internal/semprot/service.go) to Python. Scrapes
all external links from every page of a semprot.com XenForo thread. bbCode
images are intentionally skipped — only links are collected.

Cookie auth is required: cookies are read from cookies.txt (Netscape format)
at the repo root, the same file yt-dlp and gallery-dl use.

Pure sync resolver: run via sync_to_async from the caller.
"""

from http.cookiejar import MozillaCookieJar
from os import path as ospath
from re import search
from urllib.parse import urlparse

from lxml.etree import HTML

from ...ext_utils.exceptions import DirectDownloadLinkException


_COOKIES_FILE = "cookies.txt"
_SKIP_HOSTS = ("semprot.com", "gambar123.com")


def _load_cookie_header():
    """Assemble a Cookie header string from cookies.txt. Empty if missing."""
    if not ospath.exists(_COOKIES_FILE):
        return ""
    jar = MozillaCookieJar()
    jar.load(_COOKIES_FILE, ignore_discard=True, ignore_expires=True)
    return "; ".join(f"{c.name}={c.value}" for c in jar)


def _is_external(href):
    if href.startswith(("mailto:", "#", "/")):
        return False
    if not href.startswith(("http://", "https://")):
        return False
    return not any(h in href for h in _SKIP_HOSTS)


def _page_num(href):
    m = search(r"/page-(\d+)", href)
    return int(m.group(1)) if m else 0


def _parse(html):
    """Return (title, canonical, last_page, [external links]) from one page."""
    doc = HTML(html)
    title = (doc.xpath("//title/text()") or [""])[0].strip()
    canonical = (doc.xpath('//link[@rel="canonical"]/@href') or [""])[0]
    last_page = 1
    links = []
    for href in doc.xpath("//a/@href"):
        if (pg := _page_num(href)) > last_page:
            last_page = pg
        if _is_external(href):
            links.append(href)
    return title, canonical, last_page, links


def scrape_thread(url):
    """Scrape all pages of a semprot thread. Returns (title, sorted links)."""
    from curl_cffi import requests as cffi_requests

    cookie = _load_cookie_header()
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if cookie:
        headers["Cookie"] = cookie

    links = set()
    try:
        with cffi_requests.Session(impersonate="chrome136", timeout=30) as s:
            s.headers.update(headers)

            r1 = s.get(url, allow_redirects=True)
            if r1.status_code != 200:
                raise DirectDownloadLinkException(
                    f"ERROR: semprot: page 1 status {r1.status_code}"
                )
            title, canonical, last_page, page_links = _parse(r1.text)
            links.update(page_links)

            base = canonical or url
            if not base.endswith("/"):
                base += "/"

            for i in range(2, last_page + 1):
                pr = s.get(f"{base}page-{i}", allow_redirects=True)
                if pr.status_code != 200:
                    continue
                links.update(_parse(pr.text)[3])
    except DirectDownloadLinkException:
        raise
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: semprot scrape failed: {e}") from e

    return title, sorted(links)
