from asyncio import CancelledError
from base64 import b64encode
from html import escape
from logging import getLogger
from mimetypes import guess_type
from os import path as ospath, walk
from time import time
from urllib.parse import quote, urlparse
from uuid import uuid4

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from httpx import AsyncByteStream, AsyncClient, HTTPError, Limits, Timeout

from ....core.config_manager import Config
from ...ext_utils.bot_utils import sync_to_async
from ...telegram_helper.message_utils import send_message

LOGGER = getLogger(__name__)

_UPLOAD_CHUNK = 1024 * 1024
_HTTP_TIMEOUT = Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0)

IMAGE_HOSTS = {"ibb", "ic"}
IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


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
        self._upload_meta = {}
        self._is_folder = False
        self._root_name = ospath.basename(ospath.normpath(path))

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
        content_type="application/octet-stream",
    ):
        file_size = await aiopath.getsize(file_path)
        stream = MultipartFileStream(
            self,
            file_path,
            file_size,
            fields,
            file_field,
            content_type=content_type,
        )
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
                f"{response.text[:500]}"
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
                f"{self._host} returned non-JSON response "
                f"[{response.status_code}]: {response.text[:500]}"
            ) from exc

    async def _upload_catbox(self, client, file_path):
        size = await aiopath.getsize(file_path)
        if size > 200 * 1024 * 1024:
            raise RuntimeError("Catbox limit is 200 MB per file")
        fields = {
            "reqtype": "fileupload",
            "userhash": (getattr(Config, "CATBOX_USER_HASH", "") or "").strip()
            or None,
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
            raise RuntimeError(f"Catbox bad response: {link[:500]}")
        return link

    async def _create_catbox_album(self, client, links):
        if not links or len(links) > 500:
            return None
        filenames = []
        for link in links:
            name = ospath.basename(urlparse(link).path)
            if name:
                filenames.append(name)
        if not filenames:
            return None
        fields = {
            "reqtype": "createalbum",
            "userhash": (getattr(Config, "CATBOX_USER_HASH", "") or "").strip(),
            "title": self._root_name,
            "desc": "Uploaded by Mirror Leech Telegram Bot",
            "files": " ".join(filenames),
        }
        if not fields["userhash"]:
            del fields["userhash"]
        response = await client.post("https://catbox.moe/user/api.php", data=fields)
        text = response.text.strip()
        if response.status_code >= 400 or not text.startswith("http"):
            raise RuntimeError(
                f"Catbox album creation failed [{response.status_code}]: {text[:500]}"
            )
        return text

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
            raise RuntimeError(f"Litterbox bad response: {link[:500]}")
        return link

    def _pixeldrain_auth(self):
        api_key = (getattr(Config, "PIXELDRAIN_API_KEY", "") or "").strip()
        if not api_key:
            raise RuntimeError("PIXELDRAIN_API_KEY is required")
        credentials = b64encode(f":{api_key}".encode()).decode()
        return f"Basic {credentials}"

    async def _upload_pixeldrain(self, client, file_path):
        file_name = quote(ospath.basename(file_path), safe="")
        file_size = await aiopath.getsize(file_path)
        headers = {
            "Authorization": self._pixeldrain_auth(),
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
                f"{response.text[:500]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"PixelDrain returned non-JSON response: {response.text[:500]}"
            ) from exc
        file_id = payload.get("id")
        if not file_id:
            raise RuntimeError(f"PixelDrain response missing id: {payload}")
        link = f"https://pixeldrain.com/u/{file_id}"
        self._upload_meta[link] = {"id": file_id}
        return link

    async def _create_pixeldrain_list(self, client, links):
        file_ids = [
            self._upload_meta.get(link, {}).get("id")
            for link in links
            if self._upload_meta.get(link, {}).get("id")
        ]
        if not file_ids:
            return None
        response = await client.post(
            "https://pixeldrain.com/api/list",
            headers={"Authorization": self._pixeldrain_auth()},
            json={
                "title": self._root_name,
                "anonymous": False,
                "files": [{"id": file_id} for file_id in file_ids],
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"PixelDrain list creation failed [{response.status_code}]: "
                f"{response.text[:500]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"PixelDrain returned non-JSON list response: {response.text[:500]}"
            ) from exc
        list_id = payload.get("id")
        if not list_id:
            raise RuntimeError(f"PixelDrain list response missing id: {payload}")
        return f"https://pixeldrain.com/l/{list_id}"

    def _viking_remote_path(self, file_path):
        if not self._is_folder:
            return None
        rel_dir = ospath.relpath(ospath.dirname(file_path), self._path)
        remote_path = self._root_name
        if rel_dir != ".":
            rel_dir = rel_dir.replace(ospath.sep, "/")
            remote_path = f"{remote_path}/{rel_dir}"
        return remote_path

    async def _upload_vikingfile(self, client, file_path):
        server_resp = await client.get("https://vikingfile.com/api/get-server")
        if server_resp.status_code >= 400:
            raise RuntimeError(
                f"VikingFile server lookup failed: {server_resp.text[:500]}"
            )
        try:
            server = server_resp.json().get("server")
        except ValueError as exc:
            raise RuntimeError(
                f"VikingFile returned non-JSON server response: {server_resp.text[:500]}"
            ) from exc
        if not server:
            raise RuntimeError("VikingFile response missing server")
        fields = {
            "user": (getattr(Config, "VIKINGFILE_USER_HASH", "") or "").strip(),
            "path": self._viking_remote_path(file_path),
        }
        payload = await self._post_multipart(client, server, file_path, fields, "file")
        link = payload.get("url")
        if not link:
            raise RuntimeError(f"VikingFile response missing url: {payload}")
        return link

    async def _upload_krakenfiles(self, client, file_path):
        api_key = (getattr(Config, "KRAKENFILES_API_KEY", "") or "").strip()
        file_size = await aiopath.getsize(file_path)
        if api_key:
            if file_size > 2_097_152_000:
                raise RuntimeError("KrakenFiles limit is about 2 GB with API key")
        elif file_size > 1_048_576_000:
            raise RuntimeError("KrakenFiles anonymous limit is about 1 GB")

        upload_headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; MLTB/1.0)",
        }
        if api_key:
            upload_headers["X-AUTH-TOKEN"] = api_key

        server_response = await client.get(
            "https://krakenfiles.com/api/server/available",
            headers={
                "Accept": "application/json",
                "User-Agent": upload_headers["User-Agent"],
            },
        )
        if server_response.status_code >= 400:
            raise RuntimeError(
                f"KrakenFiles server lookup failed [{server_response.status_code}]: "
                f"{server_response.text[:500]}"
            )
        try:
            server_payload = server_response.json()
        except ValueError as exc:
            raise RuntimeError(
                "KrakenFiles returned non-JSON server response "
                f"[{server_response.status_code}]: {server_response.text[:500]}"
            ) from exc

        data = server_payload.get("data") or {}
        upload_url = data.get("url")
        server_access_token = data.get("serverAccessToken")
        if not upload_url or not server_access_token:
            raise RuntimeError(
                f"KrakenFiles server response missing url/token: {server_payload}"
            )

        payload = await self._post_multipart(
            client,
            upload_url,
            file_path,
            {"serverAccessToken": server_access_token},
            "file",
            headers=upload_headers,
            json_response=True,
            content_type="text/plain",
        )
        data = payload.get("data") or {}
        link = data.get("url") or payload.get("url")
        if not link:
            message = payload.get("message") or payload.get("error") or payload
            raise RuntimeError(f"KrakenFiles upload response has no url: {message}")
        self._upload_meta[link] = data
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
        data = payload.get("data") or {}
        link = data.get("link")
        if not link:
            raise RuntimeError(f"Imgur response missing link: {payload}")
        self._upload_meta[link] = {
            "id": data.get("id"),
            "deletehash": data.get("deletehash"),
        }
        return link

    async def _create_imgur_album(self, client, links):
        client_id = (getattr(Config, "IMGUR_CLIENT_ID", "") or "").strip()
        deletehashes = [
            self._upload_meta.get(link, {}).get("deletehash")
            for link in links
            if self._upload_meta.get(link, {}).get("deletehash")
        ]
        ids = [
            self._upload_meta.get(link, {}).get("id")
            for link in links
            if self._upload_meta.get(link, {}).get("id")
        ]
        data = {"title": self._root_name}
        if len(deletehashes) == len(links):
            data["deletehashes[]"] = deletehashes
        elif ids:
            data["ids[]"] = ids
        else:
            return None
        response = await client.post(
            "https://api.imgur.com/3/album",
            headers={"Authorization": f"Client-ID {client_id}"},
            data=data,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Imgur album creation failed [{response.status_code}]: "
                f"{response.text[:500]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Imgur returned non-JSON album response: {response.text[:500]}"
            ) from exc
        album_id = (payload.get("data") or {}).get("id")
        if not album_id:
            raise RuntimeError(f"Imgur album response missing id: {payload}")
        return f"https://imgur.com/a/{album_id}"

    async def _upload_imgchest(self, client, file_path, post_id=None):
        token = (getattr(Config, "IMGCHEST_API_KEY", "") or "").strip()
        if not token:
            raise RuntimeError("IMGCHEST_API_KEY is required")
        if post_id:
            url = f"https://api.imgchest.com/v1/post/{post_id}/add"
            fields = {}
        else:
            url = "https://api.imgchest.com/v1/post"
            fields = {"privacy": "hidden"}
            if self._is_folder:
                fields["title"] = self._root_name
        payload = await self._post_multipart(
            client,
            url,
            file_path,
            fields,
            "images[]",
            headers={"Authorization": f"Bearer {token}"},
            json_response=True,
        )
        data = payload.get("data") or {}
        returned_post_id = data.get("id") or post_id
        if not returned_post_id:
            raise RuntimeError(f"ImgChest response missing post id: {payload}")
        images = data.get("images") or []
        file_name = ospath.basename(file_path)
        image_link = None
        for image in reversed(images):
            if image.get("original_name") == file_name and image.get("link"):
                image_link = image["link"]
                break
        if not image_link and images:
            image_link = images[-1].get("link")
        if not image_link:
            raise RuntimeError(f"ImgChest response missing image link: {payload}")
        return (
            returned_post_id,
            f"https://imgchest.com/p/{returned_post_id}",
            image_link,
        )

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
        data = payload.get("data") or {}
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
        if self._host == "ibb":
            return await self._upload_imgbb(client, file_path)
        if self._host == "kf":
            return await self._upload_krakenfiles(client, file_path)

        raise RuntimeError(f"Unknown upload host: {self._host}")

    async def _collect_files(self):
        files = []
        subfolders = 0
        if await aiopath.isfile(self._path):
            files.append(self._path)
            return files, subfolders

        self._is_folder = True
        walk_data = await sync_to_async(lambda: list(walk(self._path)))
        for root, dirs, names in walk_data:
            subfolders += len(dirs)
            for name in sorted(names):
                candidate = ospath.join(root, name)
                if await aiopath.isfile(candidate):
                    files.append(candidate)
        return files, subfolders

    async def _make_collection(self, client, links):
        if not self._is_folder or len(links) < 2:
            return None
        if self._host == "cb":
            return await self._create_catbox_album(client, links)
        if self._host == "pd":
            return await self._create_pixeldrain_list(client, links)
        if self._host == "imgur":
            return await self._create_imgur_album(client, links)
        return None

    async def _send_file_links(self, files_dict):
        if not files_dict:
            return
        header = f"<b>{escape(self._root_name)} — uploaded files</b>\n\n"
        chunk = header
        index = 1
        for link, name in files_dict.items():
            safe_link = escape(link, quote=True)
            safe_name = escape(name)
            line = f"{index}. <a href='{safe_link}'>{safe_name}</a>\n"
            if len((chunk + line).encode()) > 3900:
                await send_message(self._listener.message, chunk)
                chunk = header
            chunk += line
            index += 1
        if chunk != header:
            await send_message(self._listener.message, chunk)

    async def upload(self):
        files, subfolders = await self._collect_files()
        if not files:
            await self._listener.on_upload_error(
                f"{self._host}: no files were found to upload"
            )
            return

        total_files = len(files)
        corrupted = 0
        errors = []
        files_dict = {}
        uploaded_links = []
        collection_link = None

        try:
            async with AsyncClient(
                timeout=_HTTP_TIMEOUT,
                limits=Limits(max_connections=4, max_keepalive_connections=2),
                follow_redirects=True,
            ) as client:
                imgchest_post_id = None
                for file_path in files:
                    try:
                        LOGGER.info(f"Uploading to {self._host}: {file_path}")
                        if self._host == "ic":
                            ext = ospath.splitext(file_path)[1].lower()
                            if ext not in IMAGE_EXTS:
                                raise RuntimeError(
                                    "ic only supports image uploads; skipped: "
                                    f"{ospath.basename(file_path)}"
                                )
                            (
                                imgchest_post_id,
                                imgchest_post_link,
                                link,
                            ) = await self._upload_imgchest(
                                client, file_path, imgchest_post_id
                            )
                            if self._is_folder and uploaded_links:
                                collection_link = imgchest_post_link
                        else:
                            link = await self._upload_one(client, file_path)
                    except (HTTPError, RuntimeError) as exc:
                        LOGGER.error(
                            f"{self._host} Upload Error: {exc} - File Path: {file_path}"
                        )
                        errors.append(f"{ospath.basename(file_path)}: {exc}")
                        corrupted += 1
                        continue
                    except CancelledError:
                        return

                    if self._listener.is_cancelled:
                        return

                    uploaded_links.append(link)
                    files_dict[link] = (
                        ospath.relpath(file_path, self._path)
                        if self._is_folder
                        else ospath.basename(file_path)
                    )

                if uploaded_links and not collection_link:
                    try:
                        collection_link = await self._make_collection(
                            client, uploaded_links
                        )
                    except (HTTPError, RuntimeError) as exc:
                        LOGGER.error(f"{self._host} collection creation error: {exc}")
                        errors.append(f"collection: {exc}")

        except Exception as exc:
            LOGGER.exception(f"{self._host} session error")
            await self._listener.on_upload_error(f"{self._host}: {exc}")
            return

        successful = total_files - corrupted
        if successful <= 0:
            details = "\n".join(errors[-3:]) or "No response detail was returned."
            await self._listener.on_upload_error(
                f"{self._host}: all {total_files} file(s) failed to upload.\n{details}"
            )
            return

        if self._listener.is_cancelled:
            return

        if self._is_folder and successful > 1 and not collection_link:
            await self._send_file_links(files_dict)
        elif (
            self._is_folder
            and successful > 1
            and self._listener.files_links
            and files_dict
        ):
            await self._send_file_links(files_dict)

        cloud_link = collection_link or uploaded_links[0]
        mime_type = (
            "Folder" if self._is_folder else (guess_type(self._path)[0] or "File")
        )

        LOGGER.info(
            f"Uploaded To {self._host}: {self._listener.name} - "
            f"{successful}/{total_files} files"
        )
        await self._listener.on_upload_complete(
            cloud_link,
            successful,
            subfolders,
            mime_type,
        )

    async def cancel_task(self):
        self._listener.is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self._listener.name}")
        await self._listener.on_upload_error("your upload has been stopped!")
