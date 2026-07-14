from logging import getLogger
from time import time
from os import path as ospath, walk
import traceback
from aiofiles.os import path as aiopath
from aiofiles import open as aiopen
from asyncio import CancelledError
from httpx import AsyncClient, Limits, Timeout, HTTPError

from ...ext_utils.bot_utils import sync_to_async
from ...ext_utils.files_utils import get_mime_type
from ....core.config_manager import Config

LOGGER = getLogger(__name__)

_UPLOAD_BASE = "https://w.buzzheavier.com"

_HTTP_TIMEOUT = Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0)


class BuzzHeavierUploader:

    def __init__(self, listener, path):
        self._listener = listener
        self._path = path
        self._processed_bytes = 0
        self._start_time = time()
        self._files = 0
        self._folders = 0
        self._root_id_cache = None
        self._client = None
        self._account_id = (Config.BUZZHEAVIER_ACCOUNT_ID or "").strip()
        self.user_settings()

    def user_settings(self):
        if self._listener.up_dest.startswith("mt:"):
            self._account_id = self._listener.user_dict.get(
                "BUZZHEAVIER_ACCOUNT_ID", ""
            ).strip()
            if not self._account_id:
                raise ValueError(
                    "BUZZHEAVIER_ACCOUNT_ID is required to be filled in user settings to upload to your own account!"
                )
            self._listener.up_dest = (
                self._listener.up_dest.removeprefix("mt:")
                .removeprefix("bh")
                .removeprefix(":")
                or self._listener.user_dict.get("BUZZHEAVIER_FOLDER_ID", "").strip()
            )
        self._listener.up_dest = self._listener.up_dest.removeprefix("bh").removeprefix(
            ":"
        )

    @property
    def processed_bytes(self):
        return self._processed_bytes

    @property
    def speed(self):
        try:
            return self._processed_bytes / (time() - self._start_time)
        except:
            return 0

    def _get_chunk_size(self, file_size: int) -> int:
        if file_size < 10 * 1024 * 1024:
            return 512 * 1024
        elif file_size < 100 * 1024 * 1024:
            return 2 * 1024 * 1024
        elif file_size < 1024 * 1024 * 1024:
            return 4 * 1024 * 1024
        else:
            return 8 * 1024 * 1024

    async def _stream_file(self, file_path, chunk_size):

        async with aiopen(file_path, "rb") as fh:
            while True:
                if self._listener.is_cancelled:
                    raise CancelledError()

                chunk = await fh.read(chunk_size)
                if not chunk:
                    return

                self._processed_bytes += len(chunk)
                yield chunk

    async def _get_root_id(self):
        if self._root_id_cache:
            return self._root_id_cache

        resp = await self._client.get(
            "https://buzzheavier.com/api/fs",
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Root fetch failed: {resp.text[:200]}")

        data = resp.json()
        root_id = (data.get("data") or {}).get("id")

        if not root_id:
            raise RuntimeError("Root id not found")

        self._root_id_cache = root_id
        return root_id

    async def _create_directory(self, name, parent_id):
        if not parent_id:
            parent_id = await self._get_root_id()

        resp = await self._client.post(
            f"https://buzzheavier.com/api/fs/{parent_id}",
            json={"name": name},
        )

        if resp.status_code not in (200, 201):
            if resp.status_code == 409:
                res = await self._client.get(
                    f"https://buzzheavier.com/api/fs/{parent_id}"
                )
                if res.status_code == 200:
                    data = res.json()
                    for item in (data.get("data") or {}).get("children", []):
                        if item.get("name") == name and item.get("isDirectory"):
                            return item.get("id")
            raise RuntimeError(f"Create dir failed: {resp.text}")

        data = resp.json()
        return (data.get("data") or {}).get("id")

    async def _upload_file(self, file_path, parent_id):
        file_name = ospath.basename(file_path)
        file_size = await aiopath.getsize(file_path)
        chunk_size = self._get_chunk_size(file_size)
        if not parent_id:
            parent_id = await self._get_root_id()

        url = f"{_UPLOAD_BASE}/{parent_id}/{file_name}"

        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(file_size),
        }

        LOGGER.info(f"Uploading file: {file_path}")

        resp = await self._client.put(
            url,
            content=self._stream_file(file_path, chunk_size),
            headers=headers,
        )

        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Upload failed: {resp.text[:200]}")

        payload = resp.json()
        file_id = (payload.get("data") or {}).get("id")

        if not file_id:
            raise RuntimeError("Missing file id")

        self._files += 1

        return f"https://buzzheavier.com/{file_id}"

    async def _upload_dir(self, directory, parent_id):
        entries = await sync_to_async(lambda: list(walk(directory)))

        for root, _, files in entries:

            if self._listener.is_cancelled:
                return

            if root != directory:
                folder_name = ospath.basename(root)
                parent_id = await self._create_directory(folder_name, parent_id)
                self._folders += 1

            for file in sorted(files):
                path = ospath.join(root, file)

                if await aiopath.isfile(path):
                    try:
                        await self._upload_file(path, parent_id)
                    except Exception as e:
                        LOGGER.error(f"Upload error: {e}")
                        continue

    async def upload(self):
        try:
            self._client = AsyncClient(
                timeout=_HTTP_TIMEOUT,
                limits=Limits(max_connections=4, max_keepalive_connections=0),
                headers={"Authorization": f"Bearer {self._account_id}"},
            )
            if await aiopath.isfile(self._path):
                mime_type = await sync_to_async(get_mime_type, self._path)
                link = await self._upload_file(self._path, self._listener.up_dest)

            else:
                mime_type = "Folder"
                root_name = ospath.basename(ospath.abspath(self._path))

                root_id = await self._create_directory(
                    root_name, self._listener.up_dest
                )

                await self._upload_dir(self._path, root_id)

                link = f"https://buzzheavier.com/{root_id}"

            if self._listener.is_cancelled:
                return

            await self._listener.on_upload_complete(
                link,
                self._files,
                self._folders,
                mime_type,
            )
        except CancelledError:
            return
        except (Exception, HTTPError) as e:
            LOGGER.error(str(e))
            traceback.print_exc()
            await self._listener.on_upload_error(str(e))

        finally:
            if self._client:
                await self._client.aclose()
                self._client = None
