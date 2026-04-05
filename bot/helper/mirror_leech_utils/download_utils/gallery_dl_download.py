from logging import ERROR, Handler, getLogger
from os import path as ospath, listdir, walk, rename
from secrets import token_urlsafe
from shutil import move as shmove, rmtree as shrmtree
from time import time

import gallery_dl.config as gdl_config
from gallery_dl.job import DownloadJob
from gallery_dl.output import NullOutput

from .... import task_dict_lock, task_dict
from ...ext_utils.bot_utils import sync_to_async, async_to_sync
from ...ext_utils.task_manager import check_running_tasks, stop_duplicate_check
from ...mirror_leech_utils.status_utils.queue_status import QueueStatus
from ...telegram_helper.message_utils import send_status_message
from ..status_utils.gallery_dl_status import GalleryDLStatus

LOGGER = getLogger(__name__)


class GalleryDLLogHandler(Handler):
    def __init__(self):
        super().__init__(level=ERROR)
        self.errors = []

    def emit(self, record):
        self.errors.append(record.getMessage())


class GalleryDLOutput(NullOutput):
    def __init__(self, obj):
        self._obj = obj

    def start(self, path):
        self._obj._current_file = path
        self._obj._current_file_start = time()

    def skip(self, path):
        self._obj._skipped_count += 1

    def success(self, path):
        if ospath.exists(path):
            fsize = ospath.getsize(path)
            self._obj._downloaded_bytes += fsize
        self._obj._completed_count += 1
        self._obj._current_file = ""


class GalleryDLHelper:
    def __init__(self, listener):
        self._downloaded_bytes = 0
        self._download_speed = 0
        self._listener = listener
        self._gid = ""
        self._completed_count = 0
        self._skipped_count = 0
        self._current_file = ""
        self._current_file_start = 0
        self._last_check_time = 0
        self._last_check_bytes = 0
        self._user_set_name = False

    @property
    def download_speed(self):
        now = time()
        elapsed = now - self._last_check_time
        if elapsed > 0.5:
            current = self.downloaded_bytes
            self._download_speed = (current - self._last_check_bytes) / elapsed
            self._last_check_time = now
            self._last_check_bytes = current
        return self._download_speed

    @property
    def downloaded_bytes(self):
        total = self._downloaded_bytes
        if self._current_file:
            try:
                temp = f"{self._current_file}.part"
                if ospath.exists(temp):
                    total += ospath.getsize(temp)
            except OSError:
                pass
        return total

    @property
    def size(self):
        return self._listener.size

    @property
    def progress(self):
        try:
            if self._listener.size > 0:
                return (self.downloaded_bytes / self._listener.size) * 100
        except (ZeroDivisionError, TypeError):
            pass
        return 0

    def _scan_size(self, path):
        total = 0
        if ospath.isdir(path):
            for dirpath, _, filenames in walk(path):
                for f in filenames:
                    fp = ospath.join(dirpath, f)
                    if ospath.exists(fp):
                        total += ospath.getsize(fp)
        return total

    def _on_download_error(self, error):
        self._listener.is_cancelled = True
        async_to_sync(self._listener.on_download_error, error)

    @staticmethod
    def _unwrap_logger(logger):
        while logger is not None and hasattr(logger, "logger"):
            parent_logger = logger.logger
            if parent_logger is logger:
                break
            logger = parent_logger
        if logger is not None and hasattr(logger, "addHandler"):
            return logger
        return None

    async def _on_download_start(self, from_queue=False):
        async with task_dict_lock:
            task_dict[self._listener.mid] = GalleryDLStatus(
                self._listener, self, self._gid
            )
        if not from_queue:
            await self._listener.on_download_start()
            if self._listener.multi <= 1 and not self._listener.is_rss:
                await send_status_message(self._listener.message)

    def _download(self, path):
        error_handler = GalleryDLLogHandler()
        gdl_logger = getLogger("gallery-dl")
        extractor_logger = None
        gdl_logger.addHandler(error_handler)
        try:
            gdl_config.clear()

            if self._user_set_name:
                gdl_config.set(
                    (),
                    "base-directory",
                    ospath.join(path, self._listener.name),
                )
                gdl_config.set((), "directory", [])
            else:
                gdl_config.set((), "base-directory", path)

            gdl_config.set(("output",), "mode", "null")
            gdl_config.set(("output",), "skip", False)

            gdl_config.set(("downloader",), "retries", 10)
            gdl_config.set(("downloader", "http"), "timeout", 30)
            gdl_config.set(("downloader",), "part", True)

            gdl_config.set(("extractor",), "retries", 10)
            gdl_config.set(("extractor",), "timeout", 30)

            if ospath.exists("cookies.txt"):
                gdl_config.set(("extractor",), "cookies", "cookies.txt")

            if self._user_opts:
                self._apply_options(self._user_opts)

            self._last_check_time = time()
            self._last_check_bytes = 0

            if self._listener.is_cancelled:
                return

            job = DownloadJob(self._listener.link)
            job.out = GalleryDLOutput(self)

            # Capture errors from extractor-specific loggers (e.g., "instagram")
            # gallery-dl extractors log via logging.getLogger(category)
            if hasattr(job, "extractor") and hasattr(job.extractor, "log"):
                extractor_logger = self._unwrap_logger(job.extractor.log)
                if extractor_logger is not None:
                    extractor_logger.addHandler(error_handler)

            original_handle_url = job.handle_url

            def patched_handle_url(url, kwdict):
                if self._listener.is_cancelled:
                    raise Exception("Cancelled by user")
                return original_handle_url(url, kwdict)

            job.handle_url = patched_handle_url

            status = job.run()

            if self._listener.is_cancelled:
                return

            actual_size = self._scan_size(path)
            if actual_size > 0:
                self._downloaded_bytes = actual_size
                self._listener.size = actual_size

            if status != 0 and self._completed_count == 0:
                if error_handler.errors:
                    error_msg = "\n".join(error_handler.errors)
                else:
                    error_msg = (
                        f"gallery-dl download failed with status code: {status}"
                    )
                self._on_download_error(error_msg)
                return

            if not ospath.exists(path) or (
                ospath.isdir(path) and len(listdir(path)) == 0
            ):
                self._on_download_error(
                    "No files downloaded. Check if the link is valid."
                )
                return

            if not self._user_set_name:
                self._set_name(path)

            async_to_sync(self._listener.on_download_complete)
        except Exception as e:
            if not self._listener.is_cancelled:
                self._on_download_error(str(e))
        finally:
            gdl_logger.removeHandler(error_handler)
            if extractor_logger is not None:
                extractor_logger.removeHandler(error_handler)

    def _set_name(self, path):
        """Flatten gallery-dl's nested directory structure and set proper name.

        gallery-dl creates: base-dir/category/subcategory/files...
        We flatten to: base-dir/subcategory/files... with name = subcategory
        """
        if not ospath.isdir(path):
            return

        entries = listdir(path)
        if not entries:
            return

        if len(entries) != 1:
            return

        top_entry = entries[0]
        top_path = ospath.join(path, top_entry)

        if not ospath.isdir(top_path):
            self._listener.name = top_entry
            return

        sub_entries = listdir(top_path)
        if not sub_entries:
            return

        if len(sub_entries) == 1:
            sub_entry = sub_entries[0]
            sub_path = ospath.join(top_path, sub_entry)
            temp_dst = ospath.join(path, f".gdl_restructure_{token_urlsafe(6)}")
            shmove(sub_path, temp_dst)
            shrmtree(top_path)
            rename(temp_dst, ospath.join(path, sub_entry))
            self._listener.name = sub_entry
        else:
            self._listener.name = top_entry

    def _apply_options(self, options):
        for key, value in options.items():
            if key == "postprocessors":
                if isinstance(value, list):
                    gdl_config.set((), "postprocessors", value)
                elif isinstance(value, dict):
                    gdl_config.set((), "postprocessors", [value])
            elif key == "cookies":
                if isinstance(value, str):
                    gdl_config.set(("extractor",), "cookies", value)
                elif isinstance(value, dict):
                    for site, cookie_data in value.items():
                        gdl_config.set(
                            ("extractor", site), "cookies", cookie_data
                        )
            elif key == "directory":
                gdl_config.set((), "directory", value)
            elif key == "filename":
                gdl_config.set((), "filename", value)
            elif key == "base-directory":
                gdl_config.set((), "base-directory", value)
            elif key == "archive":
                gdl_config.set(("extractor",), "archive", value)
            elif key == "proxy":
                gdl_config.set(("downloader",), "proxy", value)
            elif key == "username":
                if isinstance(value, dict):
                    for site, uname in value.items():
                        gdl_config.set(
                            ("extractor", site), "username", uname
                        )
                else:
                    gdl_config.set(("extractor",), "username", value)
            elif key == "password":
                if isinstance(value, dict):
                    for site, passwd in value.items():
                        gdl_config.set(
                            ("extractor", site), "password", passwd
                        )
                else:
                    gdl_config.set(("extractor",), "password", value)
            elif key == "api-key":
                if isinstance(value, dict):
                    for site, api_key in value.items():
                        gdl_config.set(
                            ("extractor", site), "api-key", api_key
                        )
            elif key == "oauth":
                if isinstance(value, dict):
                    for site, oauth_data in value.items():
                        if isinstance(oauth_data, dict):
                            for oauth_key, oauth_val in oauth_data.items():
                                gdl_config.set(
                                    ("extractor", site),
                                    oauth_key,
                                    oauth_val,
                                )
            elif key == "extractor":
                if isinstance(value, dict):
                    for site, site_opts in value.items():
                        if isinstance(site_opts, dict):
                            for opt_key, opt_val in site_opts.items():
                                gdl_config.set(
                                    ("extractor", site), opt_key, opt_val
                                )
            elif key == "downloader":
                if isinstance(value, dict):
                    for scheme, scheme_opts in value.items():
                        if isinstance(scheme_opts, dict):
                            for opt_key, opt_val in scheme_opts.items():
                                gdl_config.set(
                                    ("downloader", scheme), opt_key, opt_val
                                )
                        else:
                            gdl_config.set(
                                ("downloader",), scheme, scheme_opts
                            )
            elif key == "output":
                if isinstance(value, dict):
                    for opt_key, opt_val in value.items():
                        gdl_config.set(("output",), opt_key, opt_val)
            elif key == "image-range":
                gdl_config.set(("extractor",), "image-range", value)
            elif key == "chapter-range":
                gdl_config.set(("extractor",), "chapter-range", value)
            elif key == "image-filter":
                gdl_config.set(("extractor",), "image-filter", value)
            elif key == "chapter-filter":
                gdl_config.set(("extractor",), "chapter-filter", value)
            elif key == "sleep":
                gdl_config.set(("extractor",), "sleep", value)
            elif key == "sleep-extractor":
                gdl_config.set(("extractor",), "sleep-extractor", value)
            elif key == "sleep-request":
                gdl_config.set(("extractor",), "sleep-request", value)
            elif key == "config-files":
                if isinstance(value, list):
                    gdl_config.load(value)
                elif isinstance(value, str):
                    gdl_config.load([value])
            else:
                gdl_config.set((), key, value)

    async def add_download(self, path, options):
        self._gid = token_urlsafe(10)
        self._user_opts = options
        self._user_set_name = bool(self._listener.name)

        await self._on_download_start()

        if not self._listener.name:
            self._listener.name = self._listener.link.split("/")[-1] or "gallery-dl"

        msg, button = await stop_duplicate_check(self._listener)
        if msg:
            await self._listener.on_download_error(msg, button)
            return

        add_to_queue, event = await check_running_tasks(self._listener)
        if add_to_queue:
            LOGGER.info(f"Added to Queue/Download: {self._listener.name}")
            async with task_dict_lock:
                task_dict[self._listener.mid] = QueueStatus(
                    self._listener, self._gid, "dl"
                )
            await event.wait()
            if self._listener.is_cancelled:
                return
            LOGGER.info(
                f"Start Queued Download from gallery-dl: {self._listener.name}"
            )
            await self._on_download_start(True)

        if not add_to_queue:
            LOGGER.info(f"Download with gallery-dl: {self._listener.name}")

        await sync_to_async(self._download, path)

    async def cancel_task(self):
        self._listener.is_cancelled = True
        LOGGER.info(f"Cancelling Download: {self._listener.name}")
        await self._listener.on_download_error("Stopped by User!")
