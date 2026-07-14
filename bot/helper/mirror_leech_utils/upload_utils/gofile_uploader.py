from logging import getLogger
from os import path as ospath, walk
from time import time
from uuid import uuid4
from asyncio import CancelledError

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
import aiohttp

from ....core.config_manager import Config
from ...ext_utils.bot_utils import sync_to_async

LOGGER = getLogger(__name__)

_SERVERS_URL = "https://api.gofile.io/servers"
_UPLOAD_CHUNK = 1024 * 1024


class MultipartFileStream:
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
        async with client.get(_SERVERS_URL) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"GoFile server lookup failed [{response.status}]: "
                    f"{(await response.text())[:200]}"
                )
            try:
                payload = await response.json()
            except ValueError as exc:
                raise RuntimeError(
                    f"GoFile returned non-JSON server response: {(await response.text())[:200]}"
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
        stream = MultipartFileStream(
            self, file_path, await aiopath.getsize(file_path), token=self._token
        )
        headers = {"Content-Type": stream.content_type}
        async with client.post(upload_url, data=stream, headers=headers) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"GoFile upload failed [{response.status}]: {(await response.text())[:200]}"
                )
            try:
                payload = await response.json()
            except ValueError as exc:
                raise RuntimeError(
                    f"GoFile returned non-JSON upload response: {(await response.text())[:200]}"
                ) from exc
            if payload.get("status") != "ok":
                raise RuntimeError(f"GoFile upload failed: {payload}")
            file_data = (payload.get("data") or {})
            link = file_data.get("downloadPage") or file_data.get("url")
            if not link:
                raise RuntimeError(f"GoFile upload missing link: {payload}")
            return link
    async def cancel_task(self):
        self._listener.is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self._listener.name}")
        await self._listener.on_upload_error("your upload has been stopped!")
