import os
import re
import time
import asyncio
import aiofiles
from aiofiles.os import makedirs, remove as aioremove
from aioshutil import rmtree
from secrets import token_urlsafe
from httpx import AsyncClient

from .... import LOGGER, task_dict, task_dict_lock
from ....core.config_manager import Config
from ...ext_utils.bot_utils import cmd_exec
from ...ext_utils.task_manager import check_running_tasks, stop_duplicate_check
from ...ext_utils.status_utils import MirrorStatus
from ...mirror_leech_utils.status_utils.queue_status import QueueStatus
from ...mirror_leech_utils.status_utils.tldv_status import TldvStatus
from ...telegram_helper.message_utils import send_status_message


def caesar_decipher(text: str, offset: int) -> str:
    shift = ((offset % 26) + 26) % 26
    result = []
    for char in text:
        code = ord(char)
        if 65 <= code <= 90:  # A-Z
            result.append(chr(((code - 65 + shift) % 26) + 65))
        elif 97 <= code <= 122:  # a-z
            result.append(chr(((code - 97 + shift) % 26) + 97))
        else:
            result.append(char)
    return "".join(result)


def parse_tldv_conf(line: str):
    prefix = "#TLDVCONF:"
    if not line.startswith(prefix):
        raise ValueError(f"Invalid TLDVCONF line: {line}")
    rest = line[len(prefix):]
    first_comma = rest.find(",")
    second_comma = rest.find(",", first_comma + 1)
    if first_comma == -1 or second_comma == -1:
        raise ValueError(f"Malformed TLDVCONF: {line}")
    expiry = rest[:first_comma]
    offset = int(rest[first_comma + 1:second_comma])
    base_url = rest[second_comma + 1:]
    return expiry, offset, base_url


def get_tldv_token(listener, headers=None):
    if headers:
        for h in headers:
            h_lower = h.lower()
            if "authorization" in h_lower and "bearer" in h_lower:
                idx = h_lower.find("bearer")
                return h[idx + 6:].strip()
            if "tldvtoken=" in h_lower:
                match = re.search(r"tldvtoken=([^;]+)", h, re.IGNORECASE)
                if match:
                    return match.group(1).strip()

    return Config.TLDV_TOKEN


class TldvDownloader:
    def __init__(self, listener, path, token=None):
        self.listener = listener
        self._path = path
        self.token = token
        self.meeting_id = None
        self.completed_segments = 0
        self.total_segments = 0
        self.processed_bytes = 0
        self.speed = 0
        self.start_time = None
        self.is_downloading = False
        self.gid = token_urlsafe(10)
        self.name = ""

    @property
    def estimated_total_size(self):
        if self.completed_segments > 0 and self.total_segments > 0:
            return int(
                (self.processed_bytes / self.completed_segments)
                * self.total_segments
            )
        return 0

    async def _download_segment(self, client, url, index, temp_dir):
        if self.listener.is_cancelled:
            return
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        # Retry up to 3 times
        for attempt in range(3):
            try:
                async with client.stream(
                    "GET", url, headers=headers, timeout=30.0
                ) as response:
                    if response.status_code != 200:
                        raise Exception(f"HTTP status {response.status_code}")

                    file_path = os.path.join(temp_dir, f"seg_{index:05d}.ts")
                    async with aiofiles.open(file_path, "wb") as f:
                        async for chunk in response.aiter_bytes(
                            chunk_size=32768
                        ):
                            if self.listener.is_cancelled:
                                return
                            await f.write(chunk)
                            self.processed_bytes += len(chunk)

                    elapsed = time.time() - self.start_time
                    if elapsed > 0:
                        self.speed = self.processed_bytes / elapsed

                    self.completed_segments += 1
                    self.listener.size = self.estimated_total_size
                    return
            except Exception as e:
                if attempt == 2:
                    raise Exception(
                        f"Failed to download segment {index} after 3 attempts: {e}"
                    )
                await asyncio.sleep(1)

    async def download(self):
        self.is_downloading = True
        self.start_time = time.time()

        match = re.search(
            r"https?://(?:app\.)?tldv\.io/(?:app/meetings|watch)/([a-zA-Z0-9]+)",
            self.listener.link,
        )
        if not match:
            await self.listener.on_download_error("Invalid tldv.io URL format")
            return
        self.meeting_id = match.group(1)

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with AsyncClient(verify=False, follow_redirects=True) as client:
            # 1. Fetch metadata
            meta_url = f"https://gw.tldv.io/v1/meetings/{self.meeting_id}/watch-page?noTranscript=true"
            try:
                resp = await client.get(meta_url, headers=headers, timeout=20.0)
                if resp.status_code in [401, 403]:
                    await self.listener.on_download_error(
                        "Authentication required. Set TLDV_TOKEN config or pass valid cookies."
                    )
                    return
                elif resp.status_code != 200:
                    await self.listener.on_download_error(
                        f"Failed to fetch metadata (HTTP {resp.status_code})"
                    )
                    return
                meta_data = resp.json()
            except Exception as e:
                await self.listener.on_download_error(
                    f"Failed to fetch watch-page: {e}"
                )
                return

            meeting_name = (
                meta_data.get("meeting", {}).get("name", "Untitled Meeting")
            )
            created_at = meta_data.get("meeting", {}).get("createdAt", "")

            date_str = ""
            if created_at:
                date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", created_at)
                if date_match:
                    date_str = date_match.group(1) + "_"

            safe_name = re.sub(r'[\\/*?:"<>|]', "", meeting_name).replace(
                " ", "_"
            )
            self.name = f"{date_str}{safe_name}.mp4"
            self.listener.name = self.name

            # 2. Fetch Playlist
            playlist_url = f"https://gaia.tldv.io/v1/meetings/{self.meeting_id}/playlist.m3u8"
            try:
                resp = await client.get(
                    playlist_url, headers=headers, timeout=20.0
                )
                if resp.status_code != 200:
                    await self.listener.on_download_error(
                        f"Failed to fetch playlist (HTTP {resp.status_code})"
                    )
                    return
                playlist_content = resp.text
            except Exception as e:
                await self.listener.on_download_error(
                    f"Failed to fetch playlist: {e}"
                )
                return

            # 3. Parse playlist and decrypt URLs
            try:
                lines = playlist_content.split("\n")
                offset = None
                base_url = None
                segment_urls = []
                for raw_line in lines:
                    line = raw_line.strip()
                    if not line:
                        continue
                    if line.startswith("#TLDVCONF:"):
                        _, offset, base_url = parse_tldv_conf(line)
                        continue
                    if line.startswith("#"):
                        continue
                    if offset is None or base_url is None:
                        raise ValueError(
                            "Segment line found before #TLDVCONF header"
                        )

                    deciphered = caesar_decipher(line, offset)
                    segment_urls.append(base_url + deciphered)
            except Exception as e:
                await self.listener.on_download_error(
                    f"Failed to parse playlist: {e}"
                )
                return

            self.total_segments = len(segment_urls)
            if self.total_segments == 0:
                await self.listener.on_download_error(
                    "No segments found in the playlist"
                )
                return

            # 4. Concurrently download segments
            temp_dir = os.path.join(self._path, "_tldv_temp")
            await makedirs(temp_dir, exist_ok=True)

            sem = asyncio.Semaphore(6)

            async def worker(url, idx):
                async with sem:
                    await self._download_segment(client, url, idx, temp_dir)

            tasks = [worker(url, i) for i, url in enumerate(segment_urls)]
            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                if not self.listener.is_cancelled:
                    await self.listener.on_download_error(
                        f"Error downloading segments: {e}"
                    )
                await rmtree(temp_dir, ignore_errors=True)
                return

            if self.listener.is_cancelled:
                await rmtree(temp_dir, ignore_errors=True)
                return

            # 5. Merge segments into output.ts
            output_ts = os.path.join(self._path, "output.ts")
            try:
                async with aiofiles.open(output_ts, "wb") as outfile:
                    for i in range(self.total_segments):
                        seg_file = os.path.join(temp_dir, f"seg_{i:05d}.ts")
                        if not os.path.exists(seg_file):
                            raise Exception(f"Missing segment {i}")
                        async with aiofiles.open(seg_file, "rb") as infile:
                            chunk = await infile.read()
                            await outfile.write(chunk)
            except Exception as e:
                await self.listener.on_download_error(
                    f"Failed to merge segments: {e}"
                )
                await rmtree(temp_dir, ignore_errors=True)
                if os.path.exists(output_ts):
                    await aioremove(output_ts)
                return

            await rmtree(temp_dir, ignore_errors=True)

            # 6. Remux output.ts into output.mp4
            final_mp4 = os.path.join(self._path, self.name)
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                output_ts,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                final_mp4,
            ]
            res_out, res_err, code = await cmd_exec(cmd)

            if os.path.exists(output_ts):
                await aioremove(output_ts)

            if code != 0:
                await self.listener.on_download_error(
                    f"Remuxing failed with code {code}. Stderr: {res_err}"
                )
                return

            self.listener.size = os.path.getsize(final_mp4)
            await self.listener.on_download_complete()

    async def cancel_task(self):
        self.listener.is_cancelled = True
        LOGGER.info(f"Cancelling TLDV Download: {self.listener.name}")
        await self.listener.on_download_error("Download Cancelled by User!")


async def add_tldv_download(listener, path, headers=None):
    token = get_tldv_token(listener, headers)

    downloader = TldvDownloader(listener, path, token)
    gid = downloader.gid

    listener.name = "tldv_meeting.mp4"

    add_to_queue, event = await check_running_tasks(listener)
    if add_to_queue:
        LOGGER.info(f"Added to Queue/Download: {listener.name}")
        async with task_dict_lock:
            task_dict[listener.mid] = QueueStatus(listener, gid, "dl")
        await listener.on_download_start()
        if listener.multi <= 1 and not listener.is_rss:
            await send_status_message(listener.message)
        await event.wait()
        if listener.is_cancelled:
            return

    async with task_dict_lock:
        task_dict[listener.mid] = TldvStatus(listener, downloader, gid)

    if add_to_queue:
        LOGGER.info(
            f"Start Queued Download with TldvDownloader: {listener.name}"
        )
    else:
        LOGGER.info(f"Download with TldvDownloader: {listener.name}")
        await listener.on_download_start()
        if listener.multi <= 1 and not listener.is_rss:
            await send_status_message(listener.message)

    await downloader.download()
