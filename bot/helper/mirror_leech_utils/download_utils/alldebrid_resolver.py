"""AllDebrid filehost / magnet resolver.

Used by mirror/leech tasks when the ``-ad`` flag is supplied. Calls the
AllDebrid v4 / v4.1 API to unlock filehost links (1fichier, rapidgator,
mega, etc.) **and** to resolve magnet/torrent inputs into a flat list of
unrestricted CDN URLs that the existing ``add_direct_download`` flow
can consume.

Filehost links: ``alldebrid_resolve(link)`` returns either a single
URL string or a multi-file ``dict``.

Magnets / .torrent files: ``alldebrid_resolve_magnet(magnet, ...)``
uploads the magnet, polls ``/v4.1/magnet/status`` until the torrent is
ready, then unlocks each AllDebrid ``/f/`` link to a direct CDN URL.
The poll loop calls a user-supplied ``progress_callback`` so the bot's
status renderer can show torrenting progress while the download is
still on AllDebrid's side.
"""

from __future__ import annotations

import asyncio
import re
import urllib.parse
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urlparse

from httpx import AsyncClient, HTTPError

from bot import LOGGER
from bot.core.config_manager import Config
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException

_API_BASE = "https://api.alldebrid.com/v4.1"
_API_BASE_V4 = "https://api.alldebrid.com/v4"
_AGENT = "mltb"
_TIMEOUT = 30.0
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_MAGNET_POLL_INTERVAL_S = 5.0
_MAGNET_NO_SEED_TIMEOUT_S = 180.0
_MAGNET_MAX_DURATION_S = 7200.0  # 2h
_MAGNET_UNLOCK_CONCURRENCY = 3

# AllDebrid magnet ``statusCode`` values.
_MAGNET_STATUS_READY = 4
_MAGNET_STATUS_LABELS = {
    0: "In queue",
    1: "Downloading",
    2: "Compressing",
    3: "Uploading to AllDebrid",
    4: "Ready",
    5: "Upload failed",
    6: "Internal error",
    7: "Not downloaded (timeout)",
    8: "File too big",
    9: "Internal error",
    10: "Download timeout (72h)",
    11: "Deleted by hoster",
    12: "Processing failed",
    13: "Processing failed",
    14: "Tracker error - no peers/seeders",
    15: "No peers - torrent is dead",
}
_MAGNET_ERROR_CODES = {5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}

# Map a subset of AllDebrid error codes to user-friendly messages.
_FRIENDLY_ERRORS = {
    "AUTH_BAD_APIKEY": "ALLDEBRID_API_KEY is invalid",
    "AUTH_BLOCKED": "AllDebrid account is blocked",
    "AUTH_USER_BANNED": "AllDebrid account is banned",
    "LINK_HOST_NOT_SUPPORTED": "host is not supported by AllDebrid",
    "LINK_HOST_LIMIT_REACHED": "AllDebrid daily limit reached for this host",
    "LINK_HOST_UNAVAILABLE": "host is temporarily unavailable on AllDebrid",
    "LINK_DOWN": "the file is no longer available",
    "LINK_PASS_PROTECTED": "password-protected links are not supported",
    "LINK_TEMPORARY_UNAVAILABLE": "the link is temporarily unavailable",
    "LINK_NOT_SUPPORTED": "this link is not supported by AllDebrid",
    "MAGNET_INVALID_URI": "the magnet URI is malformed",
    "MAGNET_INVALID_FILE": "the .torrent file is invalid",
    "MAGNET_TOO_MANY_ACTIVE": "too many active magnets on AllDebrid",
}


def _api_error_message(error: dict[str, Any], link: str) -> str:
    code = (error.get("code") or "UNKNOWN").strip()
    message = error.get("message") or "Unknown AllDebrid error"
    friendly = _FRIENDLY_ERRORS.get(code, message)
    if link:
        return f"AllDebrid: {friendly} ({code}) for {link}"
    return f"AllDebrid: {friendly} ({code})"


async def _call_api(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make a single AllDebrid API call and return the inner ``data`` dict.

    Raises ``DirectDownloadLinkException`` on HTTP/JSON/business errors so
    the existing ``mirror_leech`` flow can surface a friendly message.
    """
    headers = {"User-Agent": _USER_AGENT}
    try:
        async with AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
            request_kwargs: dict[str, Any] = {"params": params or {}}
            if data is not None:
                request_kwargs["data"] = data
            if files is not None:
                request_kwargs["files"] = files
            response = await client.request(method, url, **request_kwargs)
            response.raise_for_status()
            payload = response.json()
    except HTTPError as exc:
        raise DirectDownloadLinkException(
            f"ERROR: AllDebrid network error: {exc}"
        ) from exc
    except ValueError as exc:
        raise DirectDownloadLinkException(
            f"ERROR: AllDebrid returned malformed JSON: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise DirectDownloadLinkException(
            "ERROR: AllDebrid returned an unexpected payload shape"
        )

    if payload.get("status") != "success":
        error = payload.get("error") or {}
        raise DirectDownloadLinkException(
            f"ERROR: {_api_error_message(error, params.get('link', '') if params else '')}"
        )

    inner = payload.get("data")
    if not isinstance(inner, dict):
        raise DirectDownloadLinkException(
            "ERROR: AllDebrid response missing 'data' object"
        )
    return inner


def _ensure_api_key() -> str:
    if api_key := (Config.ALLDEBRID_API_KEY or "").strip():
        return api_key
    else:
        raise DirectDownloadLinkException("ERROR: ALLDEBRID_API_KEY is not configured")


def _basename_from_url(link: str) -> str:
    parsed = urlparse(link)
    name = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return name or "file"


# ── filehost link unlock ──────────────────────────────────────────────


async def alldebrid_resolve(link: str) -> str | dict[str, Any]:
    """Resolve a filehost link via AllDebrid.

    Returns either:
        - ``str``: a single unrestricted CDN URL.
        - ``dict``: a multi-file payload compatible with the existing
          ``add_direct_download`` flow (``{"contents": [...],
          "title": str, "total_size": int}``).

    Raises ``DirectDownloadLinkException`` when the API rejects the link
    or the configuration is incomplete.
    """
    api_key = _ensure_api_key()
    params = {"agent": _AGENT, "apikey": api_key, "link": link}

    data = await _call_api("GET", f"{_API_BASE_V4}/link/unlock", params=params)

    direct = data.get("link")
    filename = data.get("filename") or _basename_from_url(link)
    filesize = int(data.get("filesize") or 0)
    streams = data.get("streams") or []

    if isinstance(direct, str) and direct:
        LOGGER.info(f"AllDebrid unlocked {link[:80]} -> {direct[:80]}...")
        return direct

    if isinstance(streams, list) and streams:
        # Some hosts (notably mega folders) return a list of children
        # rather than a single ``link``. Fall back to ``infos`` to enumerate.
        contents: list[dict[str, Any]] = []
        for entry in streams:
            if stream_url := entry.get("link") or entry.get("url"):
                contents.append(
                    {
                        "filename": entry.get("filename") or filename,
                        "path": entry.get("filename") or filename,
                        "url": stream_url,
                        "size": int(entry.get("filesize") or 0),
                        "headers": {},
                    }
                )
        if contents:
            return {
                "contents": contents,
                "title": filename,
                "total_size": filesize or sum(c["size"] for c in contents),
            }

    raise DirectDownloadLinkException(
        f"ERROR: AllDebrid did not return a usable download link for {link}"
    )


async def alldebrid_check_supported(link: str) -> bool:
    """Best-effort host support probe.

    Used by callers that want to decide whether to try AllDebrid before
    falling back to the generic direct-link generator. A failure here is
    not fatal; we return ``False`` and let the caller try the fallback
    chain.
    """
    try:
        api_key = _ensure_api_key()
    except DirectDownloadLinkException:
        return False

    try:
        data = await _call_api(
            "GET",
            f"{_API_BASE}/user/hosts",
            params={"agent": _AGENT, "apikey": api_key},
        )
    except DirectDownloadLinkException:
        return False

    domain = (urlparse(link).netloc or "").lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain:
        return False

    hosts = data.get("hosts") or {}
    if not isinstance(hosts, dict):
        return False

    for host_info in hosts.values():
        if not isinstance(host_info, dict) or not host_info.get("status"):
            continue
        for host_domain in host_info.get("domains") or []:
            host_domain = str(host_domain).lower()
            if domain == host_domain or domain.endswith(f".{host_domain}"):
                return True
    return False


# ── magnet / torrent helpers ──────────────────────────────────────────


def _extract_infohash(magnet: str) -> str:
    """Return normalized lowercase BTIH hash from a magnet URI, or empty."""
    try:
        params = urllib.parse.parse_qs(urllib.parse.urlparse(magnet).query)
        for xt in params.get("xt", []):
            if match := re.match(r"urn:btih:([A-Za-z0-9]+)", xt, flags=re.I):
                return match[1].lower()
    except:
        pass
    return ""


def _canonicalize_magnet(magnet: str) -> str:
    """Strip the magnet URI down to a minimal form AllDebrid parses reliably."""
    infohash = _extract_infohash(magnet)
    if not infohash:
        return magnet
    try:
        params = urllib.parse.parse_qs(urllib.parse.urlparse(magnet).query)
        dn = params.get("dn", [""])[0]
    except:
        dn = ""
    canonical = f"magnet:?xt=urn:btih:{infohash}"
    if dn:
        canonical += "&dn=" + urllib.parse.quote(dn, safe="")
    return canonical


def _flatten_files(
    nodes: list[Any],
    result: list[dict[str, Any]] | None = None,
    prefix: str = "",
) -> list[dict[str, Any]]:
    """Recursively flatten the AllDebrid file tree.

    Folder nodes carry an ``e`` key with the children. File nodes carry
    ``n`` (name), ``s`` (size in bytes) and ``l`` (the AllDebrid ``/f/``
    link that still needs unlocking).
    """
    if result is None:
        result = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if "e" in node and isinstance(node["e"], list):
            folder_name = node.get("n", "")
            new_prefix = f"{prefix}{folder_name}/" if folder_name else prefix
            _flatten_files(node["e"], result, new_prefix)
        else:
            filename = node.get("n", "unknown")
            result.append(
                {
                    "filename": filename,
                    "path": f"{prefix}{filename}",
                    "size": int(node.get("s", 0) or 0),
                    "link": node.get("l", ""),
                }
            )
    return result


async def _post_form(url: str, fields: list[tuple[str, Any]]) -> dict[str, Any]:
    """POST to the AllDebrid API with a form payload.

    NOTE: httpx on Python 3.14 mis-detects a *list of tuples* request body
    as a sync stream and raises "Attempted to send a sync request with an
    AsyncClient instance". Convert the fields to a plain dict (single value
    per key) which httpx sends correctly on 3.14.
    """
    api_key = _ensure_api_key()
    params = {"agent": _AGENT, "apikey": api_key}
    data = dict(fields)
    return await _call_api("POST", url, params=params, data=data)


async def upload_magnet(magnet: str) -> dict[str, Any]:
    """Upload a magnet URI to AllDebrid; returns the magnet entry dict.

    Falls back to a canonicalized URI and then the bare info-hash if the
    full magnet is rejected with ``MAGNET_INVALID_URI`` /
    ``MAGNET_INVALID_FILE``.
    """
    LOGGER.info("Uploading magnet to AllDebrid")
    candidates: list[str] = []
    for candidate in (magnet, _canonicalize_magnet(magnet), _extract_infohash(magnet)):
        candidate = (candidate or "").strip()
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    last_error: Optional[Exception] = None
    for idx, candidate in enumerate(candidates, start=1):
        try:
            LOGGER.info(
                f"AllDebrid magnet upload attempt {idx}/{len(candidates)}: {candidate[:120]}"
            )
            data = await _post_form(
                f"{_API_BASE_V4}/magnet/upload",
                [("magnets[]", candidate)],
            )
            magnets = data.get("magnets") or []
            if not magnets:
                raise DirectDownloadLinkException(
                    "ERROR: AllDebrid returned no magnet data"
                )
            entry = magnets[0]
            if "error" in entry:
                err = entry["error"]
                raise DirectDownloadLinkException(
                    f"ERROR: {_api_error_message(err, '')}"
                )
            return entry
        except DirectDownloadLinkException as exc:
            last_error = exc
            text = str(exc)
            retryable = any(
                code in text for code in ("MAGNET_INVALID_FILE", "MAGNET_INVALID_URI")
            )
            if idx < len(candidates) and retryable:
                LOGGER.warning(
                    f"AllDebrid magnet upload failed; retrying with normalized magnet: {exc}"
                )
                continue
            raise

    if last_error is not None:
        raise last_error
    raise DirectDownloadLinkException(
        "ERROR: AllDebrid magnet upload failed for unknown reason"
    )


async def upload_torrent(torrent_bytes: bytes, filename: str) -> dict[str, Any]:
    """Upload a ``.torrent`` file via ``/magnet/upload/file``."""
    LOGGER.info(f"Uploading torrent file to AllDebrid: {filename}")
    api_key = _ensure_api_key()
    params = {"agent": _AGENT, "apikey": api_key}
    files = {
        "files[]": (filename, torrent_bytes, "application/x-bittorrent"),
    }
    data = await _call_api(
        "POST",
        f"{_API_BASE_V4}/magnet/upload/file",
        params=params,
        files=files,
    )
    items = data.get("files") or []
    if not items:
        raise DirectDownloadLinkException("ERROR: AllDebrid returned no torrent data")
    entry = items[0]
    if "error" in entry:
        raise DirectDownloadLinkException(
            f"ERROR: {_api_error_message(entry['error'], '')}"
        )
    return entry


async def get_magnet_status(magnet_id: int) -> dict[str, Any]:
    """Single-magnet status lookup against ``/v4.1/magnet/status``."""
    data = await _post_form(
        f"{_API_BASE}/magnet/status",
        [("id", str(magnet_id))],
    )
    magnets = data.get("magnets")
    if not magnets:
        raise DirectDownloadLinkException(
            f"ERROR: AllDebrid returned no status for magnet {magnet_id}"
        )
    if isinstance(magnets, dict):
        return magnets
    if isinstance(magnets, list):
        return magnets[0]
    raise DirectDownloadLinkException(
        "ERROR: AllDebrid returned unexpected magnet status payload"
    )


async def delete_magnet(magnet_id: int) -> bool:
    """Best-effort: delete a magnet from the AllDebrid history."""
    try:
        await _post_form(
            f"{_API_BASE_V4}/magnet/delete",
            [("ids[]", str(magnet_id))],
        )
        LOGGER.info(f"Deleted AllDebrid magnet {magnet_id}")
        return True
    except DirectDownloadLinkException as exc:
        LOGGER.warning(f"Failed to delete AllDebrid magnet {magnet_id}: {exc}")
        return False


async def get_magnet_files(magnet_id: int) -> list[dict[str, Any]]:
    """Return the flat list of files for a completed magnet.

    Each entry has ``filename``, ``path``, ``size`` and ``link`` (the
    AllDebrid ``/f/`` link that still needs ``link/unlock``).
    """
    data = await _post_form(
        f"{_API_BASE_V4}/magnet/files",
        [("id[]", str(magnet_id))],
    )
    magnets = data.get("magnets") or []
    if not magnets:
        raise DirectDownloadLinkException(
            f"ERROR: AllDebrid returned no files for magnet {magnet_id}"
        )
    entry = magnets[0]
    if "error" in entry:
        raise DirectDownloadLinkException(
            f"ERROR: {_api_error_message(entry['error'], '')}"
        )
    return _flatten_files(entry.get("files") or [])


async def _unlock_alldebrid_link(link: str) -> dict[str, Any]:
    """Resolve an AllDebrid ``/f/`` link to a direct CDN URL."""
    api_key = _ensure_api_key()
    params = {"agent": _AGENT, "apikey": api_key}
    return await _call_api(
        "POST",
        f"{_API_BASE_V4}/link/unlock",
        params=params,
        data={"link": link},
    )


async def _resolve_unlocked_files(
    raw_files: list[dict[str, Any]],
    *,
    progress_callback: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
) -> list[dict[str, Any]]:
    """Unlock each AllDebrid ``/f/`` link in parallel (bounded)."""
    semaphore = asyncio.Semaphore(_MAGNET_UNLOCK_CONCURRENCY)
    resolved: list[Optional[dict[str, Any]]] = [None] * len(raw_files)

    async def _unlock(index: int, file_entry: dict[str, Any]) -> None:
        async with semaphore:
            if not file_entry.get("link"):
                return
            try:
                unlocked = await _unlock_alldebrid_link(file_entry["link"])
            except DirectDownloadLinkException as exc:
                LOGGER.warning(
                    f"AllDebrid unlock failed for {file_entry.get('filename', '?')}: {exc}"
                )
                return
            direct = unlocked.get("link") or ""
            if not direct:
                return
            entry = {
                "filename": unlocked.get("filename")
                or file_entry.get("filename")
                or "file",
                "path": file_entry.get("path") or unlocked.get("filename") or "file",
                "url": direct,
                "size": int(unlocked.get("filesize") or file_entry.get("size") or 0),
                "headers": {},
            }
            resolved[index] = entry
            if progress_callback is not None:
                await progress_callback(
                    {"unlock_done": index + 1, "unlock_total": len(raw_files)}
                )

    await asyncio.gather(*(_unlock(idx, entry) for idx, entry in enumerate(raw_files)))

    return [entry for entry in resolved if entry is not None]


async def alldebrid_resolve_magnet(
    magnet: str,
    *,
    progress_callback: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    poll_interval: float = _MAGNET_POLL_INTERVAL_S,
    no_seed_timeout: float = _MAGNET_NO_SEED_TIMEOUT_S,
    max_duration: float = _MAGNET_MAX_DURATION_S,
) -> dict[str, Any]:
    """Resolve a magnet URI into the multi-file payload for direct download.

    Returns ``{"magnet_id": int, "title": str, "total_size": int,
    "contents": [...]}`` where ``contents`` matches the format consumed
    by ``add_direct_download``. ``magnet_id`` is included so the caller
    can call :func:`delete_magnet` on cancellation/cleanup.

    ``progress_callback`` (optional) receives status snapshots as
    ``{"phase": "torrent" | "unlock", ...}`` so callers can drive a
    progress UI.
    """
    _ensure_api_key()
    if not magnet:
        raise DirectDownloadLinkException("ERROR: empty magnet URI")

    entry = await upload_magnet(magnet)
    magnet_id = int(entry.get("id") or 0)
    if not magnet_id:
        raise DirectDownloadLinkException("ERROR: AllDebrid did not return a magnet id")

    name = entry.get("name") or _basename_from_url(magnet) or "torrent"

    try:
        no_seed_since = 0.0
        loop = asyncio.get_event_loop()
        start_time = loop.time()

        while True:
            if is_cancelled is not None and is_cancelled():
                raise DirectDownloadLinkException(
                    "ERROR: AllDebrid magnet cancelled by user"
                )

            status = await get_magnet_status(magnet_id)
            status_code = int(status.get("statusCode", 0) or 0)
            seeders = int(status.get("seeders", 0) or 0)

            if progress_callback is not None:
                await progress_callback({"phase": "torrent", **status})

            if status_code == _MAGNET_STATUS_READY:
                break

            if status_code in _MAGNET_ERROR_CODES:
                label = _MAGNET_STATUS_LABELS.get(
                    status_code, status.get("status", "unknown")
                )
                raise DirectDownloadLinkException(
                    f"ERROR: AllDebrid - {label} (code {status_code})"
                )

            now = loop.time()
            if seeders == 0:
                if no_seed_since == 0.0:
                    no_seed_since = now
                elif now - no_seed_since >= no_seed_timeout:
                    raise DirectDownloadLinkException(
                        f"ERROR: AllDebrid no-seed timeout after {int(no_seed_timeout)}s"
                    )
            else:
                no_seed_since = 0.0

            if now - start_time >= max_duration:
                raise DirectDownloadLinkException(
                    f"ERROR: AllDebrid magnet exceeded {int(max_duration)}s"
                )

            await asyncio.sleep(poll_interval)

        raw_files = await get_magnet_files(magnet_id)
        if not raw_files:
            raise DirectDownloadLinkException(
                "ERROR: AllDebrid returned no files for the magnet"
            )

        resolved = await _resolve_unlocked_files(
            raw_files, progress_callback=progress_callback
        )
        if not resolved:
            raise DirectDownloadLinkException(
                "ERROR: AllDebrid could not unlock any of the magnet files"
            )

        total_size = sum(item.get("size", 0) for item in resolved) or int(
            entry.get("size") or 0
        )

        return {
            "magnet_id": magnet_id,
            "title": name,
            "total_size": total_size,
            "contents": resolved,
        }

    except:
        # Best-effort cleanup; do NOT shadow the original exception.
        try:
            await delete_magnet(magnet_id)
        except:
            pass
        raise


async def alldebrid_resolve_torrent(
    torrent_bytes: bytes,
    filename: str,
    **kwargs,
) -> dict[str, Any]:
    """Same flow as :func:`alldebrid_resolve_magnet` but for ``.torrent`` bytes."""
    _ensure_api_key()
    entry = await upload_torrent(torrent_bytes, filename)
    magnet_id = int(entry.get("id") or 0)
    if not magnet_id:
        raise DirectDownloadLinkException(
            "ERROR: AllDebrid did not return a magnet id for the torrent file"
        )
    # Reuse the polling/unlock pipeline by feeding back the magnet id.
    # We can't reuse alldebrid_resolve_magnet directly because it
    # uploads its own magnet, so we duplicate the wait loop minimally.
    name = entry.get("name") or filename or "torrent"

    progress_callback = kwargs.get("progress_callback")
    is_cancelled = kwargs.get("is_cancelled")
    poll_interval = float(kwargs.get("poll_interval", _MAGNET_POLL_INTERVAL_S))
    no_seed_timeout = float(kwargs.get("no_seed_timeout", _MAGNET_NO_SEED_TIMEOUT_S))
    max_duration = float(kwargs.get("max_duration", _MAGNET_MAX_DURATION_S))

    try:
        no_seed_since = 0.0
        loop = asyncio.get_event_loop()
        start_time = loop.time()
        while True:
            if is_cancelled is not None and is_cancelled():
                raise DirectDownloadLinkException(
                    "ERROR: AllDebrid magnet cancelled by user"
                )

            status = await get_magnet_status(magnet_id)
            status_code = int(status.get("statusCode", 0) or 0)
            seeders = int(status.get("seeders", 0) or 0)

            if progress_callback is not None:
                await progress_callback({"phase": "torrent", **status})

            if status_code == _MAGNET_STATUS_READY:
                break

            if status_code in _MAGNET_ERROR_CODES:
                label = _MAGNET_STATUS_LABELS.get(
                    status_code, status.get("status", "unknown")
                )
                raise DirectDownloadLinkException(
                    f"ERROR: AllDebrid - {label} (code {status_code})"
                )

            now = loop.time()
            if seeders == 0:
                if no_seed_since == 0.0:
                    no_seed_since = now
                elif now - no_seed_since >= no_seed_timeout:
                    raise DirectDownloadLinkException(
                        f"ERROR: AllDebrid no-seed timeout after {int(no_seed_timeout)}s"
                    )
            else:
                no_seed_since = 0.0

            if now - start_time >= max_duration:
                raise DirectDownloadLinkException(
                    f"ERROR: AllDebrid magnet exceeded {int(max_duration)}s"
                )

            await asyncio.sleep(poll_interval)

        raw_files = await get_magnet_files(magnet_id)
        if not raw_files:
            raise DirectDownloadLinkException(
                "ERROR: AllDebrid returned no files for the torrent"
            )
        resolved = await _resolve_unlocked_files(
            raw_files, progress_callback=progress_callback
        )
        if not resolved:
            raise DirectDownloadLinkException(
                "ERROR: AllDebrid could not unlock any of the torrent files"
            )
        total_size = sum(item.get("size", 0) for item in resolved) or int(
            entry.get("size") or 0
        )
        return {
            "magnet_id": magnet_id,
            "title": name,
            "total_size": total_size,
            "contents": resolved,
        }
    except:
        try:
            await delete_magnet(magnet_id)
        except:
            pass
        raise
