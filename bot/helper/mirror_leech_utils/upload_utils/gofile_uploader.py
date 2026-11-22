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

_API_URL = "https://api.gofile.io"
_SERVERS_URL = f"{_API_URL}/servers"
_UPLOAD_CHUNK = 1024 * 1024
_HTTP_TIMEOUT = Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0)


class MultipartFileStream(AsyncByteStream):
    def __init__(self, uploader, file_path, file_size, token="", folder_id=""):
        self._uploader = uploader
        self._file_path = file_path
        self._file_size = file_size
        self.boundary = f"----mltb-gofile-{uuid4().hex}"
        file_name = ospath.basename(file_path).replace('"', "")
        if token := token.strip():
            token_part = f'--{self.boundary}\r\nContent-Disposition: form-data; name="token"\r\n\r\n{token}\r\n'
        else:
            token_part = ""
        if folder_id:
            token_part += (
                f'--{self.boundary}\r\nContent-Disposition: form-data; name="folderId"'
                f"\r\n\r\n{folder_id}\r\n"
            )
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

    async def _upload_one(self, client, upload_url, file_path, folder_id=""):
        if self._listener.is_cancelled:
            raise CancelledError()
        file_size = await aiopath.getsize(file_path)
        stream = MultipartFileStream(
            self, file_path, file_size, self._token, folder_id
        )
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

    async def _api(self, client, method, url, **kwargs):
        headers = {"Authorization": f"Bearer {self._token}"}
        response = await client.request(method, url, headers=headers, **kwargs)
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"GoFile non-JSON response [{response.status_code}]: {response.text[:200]}"
            ) from exc
        if response.status_code != 200 or payload.get("status") != "ok":
            raise RuntimeError(f"GoFile API error: {payload}")
        return payload.get("data") or {}

    async def _ensure_token(self, client):
        if self._token:
            return
        response = await client.post(f"{_API_URL}/accounts")
        payload = response.json()
        data = payload.get("data") or {}
        if payload.get("status") != "ok" or not data.get("token"):
            raise RuntimeError(f"GoFile guest account creation failed: {payload}")
        self._token = data["token"]

    async def _get_root_folder(self, client):
        account = await self._api(client, "GET", f"{_API_URL}/accounts/getid")
        account_id = account.get("id")
        if not account_id:
            raise RuntimeError("GoFile: unable to get account id")
        info = await self._api(client, "GET", f"{_API_URL}/accounts/{account_id}")
        if root := info.get("rootFolder"):
            return root
        raise RuntimeError("GoFile: root folder not found")

    async def _create_folder(self, client, name, parent_id):
        data = await self._api(
            client,
            "POST",
            f"{_API_URL}/contents/createFolder",
            json={"parentFolderId": parent_id, "folderName": name},
        )
        if not data.get("id"):
            raise RuntimeError("GoFile: folder creation returned no id")
        return data["id"], data.get("code", "")

    async def upload(self):
        corrupted = 0
        uploaded = 0
        folders = 0
        error = ""
        link = ""
        is_file = await aiopath.isfile(self._path)
        # (folder_id, file_path)
        queue = []
        try:
            async with AsyncClient(
                timeout=_HTTP_TIMEOUT,
                limits=Limits(max_connections=4, max_keepalive_connections=2),
            ) as client:
                upload_url = await self._get_upload_url(client)
                if is_file:
                    queue.append(("", self._path))
                else:
                    await self._ensure_token(client)
                    root = await self._get_root_folder(client)
                    top = ospath.basename(ospath.abspath(self._path))
                    top_id, code = await self._create_folder(client, top, root)
                    await self._api(
                        client,
                        "PUT",
                        f"{_API_URL}/contents/{top_id}/update",
                        json={"attribute": "public", "attributeValue": True},
                    )
                    link = f"https://gofile.io/d/{code}" if code else ""
                    folders_map = {ospath.abspath(self._path): top_id}
                    walk_data = await sync_to_async(lambda: list(walk(self._path)))
                    for r, _, names in walk_data:
                        if self._listener.is_cancelled:
                            return
                        r_abs = ospath.abspath(r)
                        if r_abs not in folders_map:
                            parent = folders_map[ospath.dirname(r_abs)]
                            folders_map[r_abs], _ = await self._create_folder(
                                client, ospath.basename(r_abs), parent
                            )
                            folders += 1
                        for name in sorted(names):
                            candidate = ospath.join(r, name)
                            if await aiopath.isfile(candidate):
                                queue.append((folders_map[r_abs], candidate))
                if not queue:
                    await self._listener.on_upload_error(
                        "GoFile: no files were found to upload"
                    )
                    return
                for folder_id, file_path in queue:
                    try:
                        file_link = await self._upload_one(
                            client, upload_url, file_path, folder_id
                        )
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
                    uploaded += 1
                    link = link or file_link
        except CancelledError:
            return
        except Exception as exc:
            LOGGER.error(f"GoFile session error: {exc}")
            await self._listener.on_upload_error(f"GoFile: {exc}")
            return

        if uploaded == 0:
            await self._listener.on_upload_error(
                f"Files Corrupted or unable to upload. {error or 'Check logs!'}"
            )
            return
        if self._listener.is_cancelled:
            return
        LOGGER.info(f"Uploaded To GoFile: {self._listener.name} - {uploaded} files")
        await self._listener.on_upload_complete(
            link,
            uploaded,
            folders,
            "File" if is_file else "Folder",
        )

    async def cancel_task(self):
        self._listener.is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self._listener.name}")
        await self._listener.on_upload_error("your upload has been stopped!")
