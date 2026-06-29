from asyncio import CancelledError
from base64 import b64encode
from logging import getLogger
from os import path as ospath, walk
from time import time
from urllib.parse import quote
from uuid import uuid4

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from httpx import AsyncByteStream, AsyncClient, HTTPError, Limits, Timeout

from ....core.config_manager import Config
from ...ext_utils.bot_utils import sync_to_async

LOGGER = getLogger(__name__)

_UPLOAD_CHUNK = 1024 * 1024
_HTTP_TIMEOUT = Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0)

IMAGE_HOSTS = {"ibb"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}


class MultipartFileStream(AsyncByteStream):
    def __init__(
        self,
        uploader,
        file_path,
        file_size,
        fields,
        file_field,
        content_type="application/octet-stream",
    ):
        self._uploader = uploader
        self._file_path = file_path
        self._file_size = file_size
        self.boundary = f"----mltb-host-{uuid4().hex}"
        file_name = ospath.basename(file_path).replace('"', "")
        parts = []
        for key, value in fields.items():
            if value is None:
                continue
            parts.append(
                f"--{self.boundary}\r\n"
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                f"{value}\r\n"
            )
        parts.append(
            f"--{self.boundary}\r\n"
            f'Content-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        )
        self._prefix = "".join(parts).encode()
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


class RawFileStream(AsyncByteStream):
    def __init__(self, uploader, file_path):
        self._uploader = uploader
        self._file_path = file_path

    async def __aiter__(self):
        async with aiopen(self._file_path, "rb") as fh:
            while True:
                if self._uploader._listener.is_cancelled:
                    raise CancelledError()
                chunk = await fh.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                self._uploader._processed_bytes += len(chunk)
                yield chunk


class HostUploader:
    def __init__(self, listener, path, host):
        self._listener = listener
        self._path = path
        self._host = host
        self._processed_bytes = 0
        self._start_time = time()

    @property
    def host_name(self):
        return self._host

    @property
    def processed_bytes(self):
        return self._processed_bytes

    @property
    def speed(self):
        try:
            return self._processed_bytes / (time() - self._start_time)
        except Exception:
            return 0

    async def _post_multipart(
        self,
        client,
        url,
        file_path,
        fields,
        file_field,
        headers=None,
        json_response=True,
    ):
        file_size = await aiopath.getsize(file_path)
        stream = MultipartFileStream(self, file_path, file_size, fields, file_field)
        req_headers = {
            "Content-Type": f"multipart/form-data; boundary={stream.boundary}",
            "Content-Length": str(stream.content_length),
        }
        if headers:
            req_headers.update(headers)

        response = await client.post(url, content=stream, headers=req_headers)
        if response.status_code >= 400:
            raise RuntimeError(
                f"{self._host} upload failed [{response.status_code}]: "
                f"{response.text[:300]}"
            )
        if not json_response:
            text = response.text.strip()
            if not text:
                raise RuntimeError(f"{self._host} returned empty response")
            return text
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"{self._host} returned non-JSON response: {response.text[:300]}"
            ) from exc

    async def _upload_catbox(self, client, file_path):
        size = await aiopath.getsize(file_path)
        if size > 200 * 1024 * 1024:
            raise RuntimeError("Catbox limit is 200 MB per file")
        fields = {
            "reqtype": "fileupload",
            "userhash": (getattr(Config, "CATBOX_USER_HASH", "") or "").strip() or None,
        }
        link = await self._post_multipart(
            client,
            "https://catbox.moe/user/api.php",
            file_path,
            fields,
            "fileToUpload",
            json_response=False,
        )
        if not link.startswith("http"):
            raise RuntimeError(f"Catbox bad response: {link[:300]}")
        return link

    async def _upload_litterbox(self, client, file_path):
        expiry = (getattr(Config, "LITTERBOX_TIME", "") or "1h").strip()
        if expiry not in {"1h", "12h", "24h", "72h"}:
            expiry = "1h"
        fields = {"reqtype": "fileupload", "time": expiry}
        link = await self._post_multipart(
            client,
            "https://litterbox.catbox.moe/resources/internals/api.php",
            file_path,
            fields,
            "fileToUpload",
            json_response=False,
        )
        if not link.startswith("http"):
            raise RuntimeError(f"Litterbox bad response: {link[:300]}")
        return link

    async def _upload_pixeldrain(self, client, file_path):
        api_key = (getattr(Config, "PIXELDRAIN_API_KEY", "") or "").strip()
        if not api_key:
            raise RuntimeError("PIXELDRAIN_API_KEY is required")
        file_name = quote(ospath.basename(file_path), safe="")
        file_size = await aiopath.getsize(file_path)
        credentials = b64encode(f":{api_key}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(file_size),
        }
        response = await client.put(
            f"https://pixeldrain.com/api/file/{file_name}",
            content=RawFileStream(self, file_path),
            headers=headers,
        )
        if response.status_code not in {200, 201}:
            raise RuntimeError(
                f"PixelDrain upload failed [{response.status_code}]: "
                f"{response.text[:300]}"
            )
        payload = response.json()
        file_id = payload.get("id")
        if not file_id:
            raise RuntimeError(f"PixelDrain response missing id: {payload}")
        return f"https://pixeldrain.com/u/{file_id}"

    async def _upload_vikingfile(self, client, file_path):
        server_resp = await client.get("https://vikingfile.com/api/get-server")
        if server_resp.status_code >= 400:
            raise RuntimeError(f"VikingFile server lookup failed: {server_resp.text[:300]}")
        server = server_resp.json().get("server")
        if not server:
            raise RuntimeError("VikingFile response missing server")
        fields = {"user": (getattr(Config, "VIKINGFILE_USER_HASH", "") or "").strip()}
        payload = await self._post_multipart(client, server, file_path, fields, "file")
        link = payload.get("url")
        if not link:
            raise RuntimeError(f"VikingFile response missing url: {payload}")
        return link

    async def _upload_krakenfiles(self, client, file_path):
        api_key = (getattr(Config, "KRAKENFILES_API_KEY", "") or "").strip()
        file_size = await aiopath.getsize(file_path)
        if api_key:
            if file_size > 2 * 1024 * 1024 * 1024:
                raise RuntimeError("KrakenFiles limit is 2 GB with API key")
        elif file_size > 1 * 1024 * 1024 * 1024:
            raise RuntimeError("KrakenFiles anonymous limit is 1 GB")

        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-AUTH-TOKEN"] = api_key

        server_response = await client.get(
            "https://krakenfiles.com/api/server/available",
            headers={"Accept": "application/json"},
        )
        if server_response.status_code >= 400:
            raise RuntimeError(
                f"KrakenFiles server lookup failed [{server_response.status_code}]: "
                f"{server_response.text[:300]}"
            )
        try:
            server_payload = server_response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"KrakenFiles returned non-JSON server response: "
                f"{server_response.text[:300]}"
            ) from exc

        data = server_payload.get("data", {})
        upload_url = data.get("url")
        server_access_token = data.get("serverAccessToken")
        if not upload_url or not server_access_token:
            raise RuntimeError(f"KrakenFiles server response missing data: {server_payload}")

        payload = await self._post_multipart(
            client,
            upload_url,
            file_path,
            {"serverAccessToken": server_access_token},
            "file",
            headers=headers,
            json_response=True,
        )
        link = payload.get("data", {}).get("url")
        if not link:
            raise RuntimeError(f"KrakenFiles response missing url: {payload}")
        return link

    async def _upload_imgur(self, client, file_path):
        client_id = (getattr(Config, "IMGUR_CLIENT_ID", "") or "").strip()
        if not client_id:
            raise RuntimeError("IMGUR_CLIENT_ID is required")
        payload = await self._post_multipart(
            client,
            "https://api.imgur.com/3/image",
            file_path,
            {},
            "image",
            headers={"Authorization": f"Client-ID {client_id}"},
            json_response=True,
        )
        link = payload.get("data", {}).get("link")
        if not link:
            raise RuntimeError(f"Imgur response missing link: {payload}")
        return link

    async def _upload_imgchest(self, client, file_path):
        token = (getattr(Config, "IMGCHEST_API_KEY", "") or "").strip()
        if not token:
            raise RuntimeError("IMGCHEST_API_KEY is required")
        payload = await self._post_multipart(
            client,
            "https://api.imgchest.com/v1/post",
            file_path,
            {"privacy": "hidden"},
            "images[]",
            headers={"Authorization": f"Bearer {token}"},
            json_response=True,
        )
        post_id = payload.get("data", {}).get("id")
        if not post_id:
            raise RuntimeError(f"ImgChest response missing post id: {payload}")
        return f"https://imgchest.com/p/{post_id}"

    async def _upload_imgbb(self, client, file_path):
        api_key = (getattr(Config, "IMGBB_API_KEY", "") or "").strip()
        if not api_key:
            raise RuntimeError("IMGBB_API_KEY is required")
        size = await aiopath.getsize(file_path)
        if size > 32 * 1024 * 1024:
            raise RuntimeError("ImgBB limit is 32 MB per image")
        payload = await self._post_multipart(
            client,
            f"https://api.imgbb.com/1/upload?key={api_key}",
            file_path,
            {},
            "image",
            json_response=True,
        )
        data = payload.get("data", {})
        link = data.get("url_viewer") or data.get("url") or data.get("display_url")
        if not link:
            raise RuntimeError(f"ImgBB response missing link: {payload}")
        return link

    async def _upload_one(self, client, file_path):
        if self._listener.is_cancelled:
            raise CancelledError()

        ext = ospath.splitext(file_path)[1].lower()
        if self._host in IMAGE_HOSTS and ext not in IMAGE_EXTS:
            raise RuntimeError(
                f"{self._host} only supports image uploads; skipped: "
                f"{ospath.basename(file_path)}"
            )

        if self._host == "cb":
            return await self._upload_catbox(client, file_path)
        if self._host == "lb":
            return await self._upload_litterbox(client, file_path)
        if self._host == "pd":
            return await self._upload_pixeldrain(client, file_path)
        if self._host == "vf":
            return await self._upload_vikingfile(client, file_path)
        if self._host == "imgur":
            return await self._upload_imgur(client, file_path)
        if self._host == "ic":
            return await self._upload_imgchest(client, file_path)
        if self._host == "ibb":
            return await self._upload_imgbb(client, file_path)
        if self._host == "kf":
            return await self._upload_krakenfiles(client, file_path)

        raise RuntimeError(f"Unknown upload host: {self._host}")

    async def upload(self):
        files = []
        corrupted = 0
        error = ""
        files_dict = {}
        first_link = None

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
                f"{self._host}: no files were found to upload"
            )
            return

        total_files = len(files)

        try:
            async with AsyncClient(
                timeout=_HTTP_TIMEOUT,
                limits=Limits(max_connections=4, max_keepalive_connections=2),
            ) as client:
                for file_path in files:
                    try:
                        LOGGER.info(f"Uploading to {self._host}: {file_path}")
                        link = await self._upload_one(client, file_path)
                    except (HTTPError, RuntimeError) as exc:
                        LOGGER.error(
                            f"{self._host} Upload Error: {exc} - File Path: {file_path}"
                        )
                        error = str(exc)
                        corrupted += 1
                        continue
                    except CancelledError:
                        return

                    if self._listener.is_cancelled:
                        return

                    first_link = first_link or link
                    if self._listener.files_links:
                        files_dict[link] = ospath.basename(file_path)

        except Exception as exc:
            LOGGER.error(f"{self._host} session error: {exc}")
            await self._listener.on_upload_error(f"{self._host}: {exc}")
            return

        if total_files <= corrupted:
            await self._listener.on_upload_error(
                f"Files corrupted or unable to upload.\n{error or 'Check logs!'}"
            )
            return

        if self._listener.is_cancelled:
            return

        LOGGER.info(
            f"Uploaded To {self._host}: {self._listener.name} - "
            f"{total_files - corrupted} files"
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
