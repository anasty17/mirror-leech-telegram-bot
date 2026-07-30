"""Generic /bypass dispatcher.

Routes a URL to the right thread scraper by domain. Currently only semprot is
registered; add another `if domain` branch to support more sites.
"""

from urllib.parse import urlparse

from ...ext_utils.exceptions import DirectDownloadLinkException
from .semprot_scraper import scrape_thread


def bypass_scrape(link, keyword=""):
    """Return (title, links). Filter to links containing keyword if given."""
    domain = urlparse(link).hostname or ""
    if "semprot.com" in domain:
        title, links = scrape_thread(link)
        if keyword:
            n = keyword.lower()
            links = [l for l in links if n in l.lower()]
        return title, links
    raise DirectDownloadLinkException(f"ERROR: No bypass scraper for {domain}")
