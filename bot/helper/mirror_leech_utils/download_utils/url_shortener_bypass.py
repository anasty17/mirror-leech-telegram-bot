"""URL shortener bypassers.

Each handler resolves a shortened URL back to its underlying target URL.
Handlers are pure resolvers: input a shortened URL, output the target URL
string (or raise DirectDownloadLinkException). The caller in
direct_link_generator.py is responsible for re-dispatching the returned URL
through the regular host handlers.
"""

from re import search
from urllib.parse import urlparse

from curl_cffi import requests as cffi_requests

from ...ext_utils.exceptions import DirectDownloadLinkException


_OUO_DOMAINS = ("ouo.io", "ouo.press")

_CSRF_PATTERN = (
    r'<input[^>]*\bname="_token"[^>]*\bvalue="([^"]*)"'
    r'|<input[^>]*\bvalue="([^"]*)"[^>]*\bname="_token"'
)


def is_url_shortener(domain):
    if not domain:
        return False
    return any(d in domain for d in _OUO_DOMAINS)


def bypass_shortener(link):
    domain = urlparse(link).hostname or ""
    if any(d in domain for d in _OUO_DOMAINS):
        return _ouo(link)
    raise DirectDownloadLinkException(f"ERROR: No bypasser for {domain}")


def _extract_csrf(html):
    m = search(_CSRF_PATTERN, html)
    if not m:
        return ""
    return next((g for g in m.groups() if g), "")


def _ouo(link):
    """Resolve ouo.io / ouo.press shortlinks.

    Three-step CSRF dance: GET landing → POST /go/<id> → POST /xreallcygo/<id>.
    Cloudflare fronts ouo.io and fingerprints both TLS ClientHello and HTTP/2
    SETTINGS, so curl_cffi's chrome impersonation is required — stdlib
    requests/httpx gets 403.
    """
    normalized = link.replace("ouo.press", "ouo.io")
    parsed = urlparse(normalized)
    short_id = parsed.path.rsplit("/", 1)[-1]
    if not short_id:
        raise DirectDownloadLinkException("ERROR: ouo: id segment kosong")

    base = f"{parsed.scheme}://{parsed.netloc}"
    go_url = f"{base}/go/{short_id}"
    final_url = f"{base}/xreallcygo/{short_id}"

    try:
        with cffi_requests.Session(impersonate="chrome136", timeout=30) as s:
            r1 = s.get(normalized, allow_redirects=True)
            if r1.status_code == 403:
                raise DirectDownloadLinkException(
                    "ERROR: ouo.io memblokir request (403)"
                )
            tok1 = _extract_csrf(r1.text)
            if not tok1:
                raise DirectDownloadLinkException(
                    f"ERROR: ouo: _token tidak ditemukan di halaman awal (status={r1.status_code})"
                )

            r2 = s.post(
                go_url,
                data={"_token": tok1, "x-token": "", "v-token": "vm"},
                headers={"Origin": "https://ouo.io", "Referer": normalized},
                allow_redirects=False,
            )
            if r2.status_code == 403:
                raise DirectDownloadLinkException(
                    "ERROR: ouo.io memblokir request (403)"
                )
            if r2.status_code != 200:
                raise DirectDownloadLinkException(
                    f"ERROR: ouo: /go/ status {r2.status_code}"
                )
            tok2 = _extract_csrf(r2.text)
            if not tok2:
                raise DirectDownloadLinkException(
                    "ERROR: ouo: _token tidak ditemukan di halaman /go/"
                )

            r3 = s.post(
                final_url,
                data={"_token": tok2, "x-token": ""},
                headers={"Origin": "https://ouo.io", "Referer": go_url},
                allow_redirects=False,
            )
            location = r3.headers.get("Location", "")
            if r3.status_code != 302 or not location:
                raise DirectDownloadLinkException(
                    f"ERROR: ouo: /xreallcygo/ status {r3.status_code} (location={location!r})"
                )
            return location
    except DirectDownloadLinkException:
        raise
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: ouo bypass gagal: {e}") from e
