from json import JSONDecodeError
from urllib.parse import quote

from httpx import AsyncClient, Timeout

from ...core.config_manager import Config

SHORTENER_HOSTS = {
    "spoome": "spoo.me",
    "xgd": "x.gd",
    "tly": "t.ly",
    "cleanuri": "CleanURI",
    "isgd": "is.gd",
}

_TIMEOUT = Timeout(connect=15.0, read=30.0, write=30.0, pool=15.0)


def normalize_url(url):
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def _response_text(response):
    return response.text[:500].strip()


def _make_client():
    proxy = (Config.URL_SHORTENER_PROXY or "").strip()
    kwargs = {
        "timeout": _TIMEOUT,
        "follow_redirects": False,
    }

    if not proxy:
        return AsyncClient(**kwargs)

    try:
        return AsyncClient(proxy=proxy, **kwargs)
    except TypeError:
        return AsyncClient(proxies=proxy, **kwargs)


async def _json(response, host):
    if response.status_code >= 400:
        raise RuntimeError(
            f"{host} failed [{response.status_code}]: {_response_text(response)}"
        )
    try:
        return response.json()
    except (JSONDecodeError, ValueError) as exc:
        raise RuntimeError(
            f"{host} returned non-JSON response: {_response_text(response)}"
        ) from exc


async def shorten_url(url, host=None):
    host = (host or Config.URL_SHORTENER or "spoome").strip().lower()
    if host not in SHORTENER_HOSTS:
        raise RuntimeError(f"Unsupported shortener host: {host}")

    url = normalize_url(url)

    async with _make_client() as client:
        if host == "spoome":
            response = await client.post(
                "https://spoo.me/",
                data={"url": url},
                headers={"Accept": "application/json"},
            )
            data = await _json(response, "spoo.me")
            short_url = data.get("short_url") or data.get("shortUrl")

        elif host == "xgd":
            response = await client.get(
                f"https://x.gd/api.php?url={quote(url, safe='')}"
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"x.gd failed [{response.status_code}]: {_response_text(response)}"
                )
            short_url = response.text.strip()

        elif host == "tly":
            token = (Config.TLY_API_TOKEN or "").strip()
            if not token:
                raise RuntimeError("TLY_API_TOKEN is required for t.ly")

            response = await client.post(
                "https://api.t.ly/api/v1/link/shorten",
                json={
                    "long_url": url,
                    "domain": "https://t.ly/",
                    "format": "json",
                    "include_qr_code": False,
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            data = await _json(response, "t.ly")
            nested_data = data.get("data") if isinstance(data.get("data"), dict) else {}
            short_url = (
                data.get("short_url")
                or data.get("shortUrl")
                or data.get("short_link")
                or data.get("url")
                or nested_data.get("short_url")
                or nested_data.get("shortUrl")
                or nested_data.get("short_link")
                or nested_data.get("url")
            )

        elif host == "cleanuri":
            response = await client.post(
                "https://cleanuri.com/api/v1/shorten",
                data={"url": url},
            )
            data = await _json(response, "CleanURI")
            short_url = data.get("result_url")

        elif host == "isgd":
            response = await client.get(
                "https://is.gd/create.php",
                params={"format": "json", "url": url},
            )
            data = await _json(response, "is.gd")
            short_url = data.get("shorturl")

    if not short_url:
        raise RuntimeError(f"{SHORTENER_HOSTS[host]} response missing short URL")

    return short_url, SHORTENER_HOSTS[host]
