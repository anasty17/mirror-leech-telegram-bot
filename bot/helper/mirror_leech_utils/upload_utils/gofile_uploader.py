from logging import getLogger
from os import path as ospath, walk
from time import time
from uuid import uuid4
from asyncio import CancelledError

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from httpx import AsyncByteStream, AsyncClient, HTTPError, Limits, Timeout

from ....core.config_manager import Config
from ...ext_utils.bot_utils import sync_to_async

LOGGER = getLogger(__name__)

_SERVERS_URL = "https://api.gofile.io/servers"
_UPLOAD_CHUNK = 1024 * 1024
_HTTP_TIMEOUT = Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0)


class MultipartFileStream(AsyncByteStream):
    def __init__(self, uploader, file_path, file_size, token=""):
        self._uploader = uploader
        self._file_path = file_path
        self._file_size = file_size
        self.boundary = f"----mltb-gofile-{uuid4().hex}"
        file_name = ospath.basename(file_path).replace('"', "")
        if token := token.strip():
            token_part = f'--{self.boundary}\r\nContent-Disposition: form-data; name="token"\r\n\r\n{token}\r\n'
        else:
            token_part = ""
        self._prefix = (
            f"{token_part}--{self.boundary}\r\n"
            + f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
            + "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        self._suffix = f"\r\n--{self.boundary}--\r\n".encode()
        self.content_length = len(self._prefix) + self._file_size + len(self._suffix)

    async def __aiter__(self):
        yield self._prefix
        async with aiopen(self._file_path, "rb") as fh:
            while True:
                if self._uploader._listener.is_cancelled:
                    raise CancelledError()
                chunk = await fh.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                self._uploader._processed_bytes += len(chunk)
                yield chunk
        yield self._suffix


class GoFileUploader:
    def __init__(self, listener, path):
        self._listener = listener
        self._path = path
        self._token = (Config.GOFILE_API_KEY or "").strip()
        self._processed_bytes = 0
        self._start_time = time()

    @property
    def processed_bytes(self):
        return self._processed_bytes

    @property
    def speed(self):
        try:
            return self._processed_bytes / (time() - self._start_time)
        except Exception:
            return 0

    async def _get_upload_url(self, client):
        response = await client.get(_SERVERS_URL)
        if response.status_code != 200:
            raise RuntimeError(
                f"GoFile server lookup failed [{response.status_code}]: "
                f"{response.text[:200]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"GoFile returned non-JSON server response: {response.text[:200]}"
            ) from exc
        if payload.get("status") != "ok":
            raise RuntimeError(f"GoFile server lookup failed: {payload}")
        servers = payload.get("data", {}).get("servers", [])
        if not servers:
            raise RuntimeError("GoFile server lookup returned no servers")
        if server := servers[0].get("name"):
            return f"https://{server}.gofile.io/uploadFile"
        else:
            raise RuntimeError("GoFile server response missing server name")

    async def _upload_one(self, client, upload_url, file_path):
        if self._listener.is_cancelled:
            raise CancelledError()
        file_size = await aiopath.getsize(file_path)
        stream = MultipartFileStream(self, file_path, file_size, self._token)
        headers = {
            "Content-Type": f"multipart/form-data; boundary={stream.boundary}",
            "Content-Length": str(stream.content_length),
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        LOGGER.info(f"Uploading to GoFile: {file_path}")
        response = await client.post(upload_url, content=stream, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(
                f"GoFile upload failed [{response.status_code}]: {response.text[:200]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"GoFile returned non-JSON upload response: {response.text[:200]}"
            ) from exc
        if payload.get("status") != "ok":
            raise RuntimeError(f"GoFile upload failed: {payload}")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise RuntimeError("GoFile response missing 'data' object")
        if link := (data.get("downloadPage") or "").strip():
            return link
        else:
            raise RuntimeError("GoFile response missing downloadPage")

    async def upload(self):
        files = []
        corrupted = 0
        error = ""
        if await aiopath.isfile(self._path):
            files.append(self._path)
        else:
            walk_data = await sync_to_async(lambda: list(walk(self._path)))
            for root, _, names in walk_data:
                for name in sorted(names):
                    candidate = ospath.join(root, name)
                    if await aiopath.isfile(candidate):
                        files.append(candidate)
        if not files:
            await self._listener.on_upload_error(
                "GoFile: no files were found to upload"
            )
            return
        total_files = len(files)
        try:
            async with AsyncClient(
                timeout=_HTTP_TIMEOUT,
                limits=Limits(max_connections=4, max_keepalive_connections=2),
            ) as client:
                upload_url = await self._get_upload_url(client)
                for file_path in files:
                    try:
                        link = await self._upload_one(client, upload_url, file_path)
                    except (HTTPError, RuntimeError) as exc:
                        LOGGER.error(
                            f"GoFile Upload Error: {exc} - File Path: {file_path}"
                        )
                        error = str(exc)
                        corrupted += 1
                        continue
                    except CancelledError:
                        return
                    if self._listener.is_cancelled:
                        return
                    first_link = first_link or link
        except Exception as exc:
            LOGGER.error(f"GoFile session error: {exc}")
            await self._listener.on_upload_error(f"GoFile: {exc}")
            return

        if total_files <= corrupted:
            await self._listener.on_upload_error(
                f"Files Corrupted or unable to upload. {error or 'Check logs!'}"
            )
            return
        if self._listener.is_cancelled:
            return
        LOGGER.info(
            f"Uploaded To GoFile: {self._listener.name} - {total_files - corrupted} files"
        )
        await self._listener.on_upload_complete(
            first_link,
            files_dict,
            total_files,
            corrupted,
        )

    async def cancel_task(self):
        self._listener.is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self._listener.name}")
        await self._listener.on_upload_error("your upload has been stopped!")
