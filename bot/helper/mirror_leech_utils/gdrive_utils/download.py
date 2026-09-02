from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from io import FileIO
from json import loads as json_loads
from time import time
from logging import getLogger
from os import makedirs, path as ospath
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
    RetryError,
)

from ...ext_utils.bot_utils import async_to_sync
from ...ext_utils.bot_utils import SetInterval
from ...mirror_leech_utils.gdrive_utils.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)

EXPORT_MAP = {
    "application/vnd.google-apps.document": {
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "ext": ".docx",
    },
    "application/vnd.google-apps.spreadsheet": {
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "ext": ".xlsx",
    },
    "application/vnd.google-apps.presentation": {
        "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ext": ".pptx",
    },
    "application/vnd.google-apps.drawing": {
        "mime": "image/png",
        "ext": ".png",
    },
}


def _error_reason(err):
    try:
        payload = json_loads(err.content)
        return payload.get("error", {}).get("errors", [{}])[0].get("reason") or ""
    except (TypeError, ValueError, IndexError, AttributeError):
        return ""


class GoogleDriveDownload(GoogleDriveHelper):
    def __init__(self, listener, path):
        self.listener = listener
        self._path = path
        self._start_time = time()
        super().__init__()
        self.is_downloading = True

    def download(self):
        file_id = self.get_id_from_url(self.listener.link, self.listener.user_id)
        self.service = self.authorize()
        try:
            meta = self.get_file_metadata(file_id)
            if meta.get("mimeType") == self.G_DRIVE_DIR_MIME_TYPE:
                self._download_folder(file_id, self._path, self.listener.name)
            else:
                makedirs(self._path, exist_ok=True)
                self._download_file(
                    file_id,
                    self._path,
                    self.listener.name,
                    meta.get("mimeType"),
                    meta.get("size", 0),
                )
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace(">", "").replace("<", "")
            if "downloadQuotaExceeded" in err:
                err = "Download Quota Exceeded."
            elif "File not found" in err:
                if not self.alt_auth and self.use_sa:
                    self.alt_auth = True
                    self.use_sa = False
                    LOGGER.error("File not found. Trying with token.pickle...")
                    return self.download()
                err = "File not found!"
            async_to_sync(self.listener.on_download_error, err)
            self.listener.is_cancelled = True
        finally:
            if not self.listener.is_cancelled:
                async_to_sync(self.listener.on_download_complete)

    def _download_folder(self, folder_id, path, folder_name):
        folder_name = folder_name.replace("/", "")
        if not ospath.exists(f"{path}/{folder_name}"):
            makedirs(f"{path}/{folder_name}")
        path += f"/{folder_name}"
        result = self.get_files_by_folder_id(folder_id)
        if len(result) == 0:
            return
        result = sorted(result, key=lambda k: k["name"])
        for item in result:
            file_id = item["id"]
            filename = item["name"]
            shortcut_details = item.get("shortcutDetails")
            if shortcut_details is not None:
                file_id = shortcut_details["targetId"]
                mime_type = shortcut_details["targetMimeType"]
            else:
                mime_type = item.get("mimeType")
            if mime_type == self.G_DRIVE_DIR_MIME_TYPE:
                self._download_folder(file_id, path, filename)
            elif ospath.isfile(f"{path}/{filename}"):
                continue
            elif (
                self.listener.included_extensions
                and not filename.strip()
                .lower()
                .endswith(tuple(self.listener.included_extensions))
            ):
                continue
            elif (
                not self.listener.included_extensions
                and filename.strip()
                .lower()
                .endswith(tuple(self.listener.excluded_extensions))
            ):
                continue
            else:
                self._download_file(
                    file_id, path, filename, mime_type, item.get("size", 0)
                )
            if self.listener.is_cancelled:
                break

    @retry(
        wait=wait_exponential(multiplier=2, min=3, max=6),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
    )
    def _download_file(
        self,
        file_id,
        path,
        filename,
        mime_type,
        file_size,
    ):
        if mime_type.startswith("application/vnd.google-apps"):
            export = EXPORT_MAP.get(
                mime_type,
                {
                    "mime": "application/pdf",
                    "ext": ".pdf",
                },
            )
            request = self.service.files().export_media(
                fileId=file_id, mimeType=export["mime"]
            )
            filename = f"{filename}{export['ext']}"
        else:
            request = self.service.files().get_media(
                fileId=file_id, supportsAllDrives=True, acknowledgeAbuse=True
            )
        filename = filename.replace("/", "")
        if len(filename.encode()) > 255:
            ext = ospath.splitext(filename)[1]
            filename = f"{filename[:245]}{ext}"
            if self.listener.name.strip().endswith(ext):
                self.listener.name = filename
        if self.listener.is_cancelled:
            return
        fh = FileIO(f"{path}/{filename}", "wb")
        downloader = MediaIoBaseDownload(fh, request, chunksize=100 * 1024 * 1024)
        done = False
        retries = 0
        try:
            while not done:
                if self.listener.is_cancelled:
                    break
                try:
                    self.status, done = downloader.next_chunk()
                    self.progress()
                    if self.status is None:
                        if self.file_processed_bytes and done:
                            self.proc_bytes += file_size - self.file_processed_bytes
                        else:
                            self.proc_bytes += file_size
                except HttpError as err:
                    LOGGER.error(err)
                    if err.resp.status in [500, 502, 503, 504, 429] and retries < 10:
                        retries += 1
                        continue
                    if err.resp.get("content-type", "").startswith("application/json"):
                        reason = _error_reason(err)
                        if reason == "fileNotDownloadable" and "document" in mime_type:
                            self.proc_bytes -= self.file_processed_bytes
                            return self._download_file(
                                file_id, path, filename, mime_type, True
                            )
                        if reason not in [
                            "downloadQuotaExceeded",
                            "dailyLimitExceeded",
                        ]:
                            raise err
                        if self.use_sa:
                            if self.sa_count >= self.sa_number:
                                LOGGER.info(
                                    f"Reached maximum number of service accounts switching, which is {self.sa_count}"
                                )
                                raise err
                            if self.listener.is_cancelled:
                                return
                            self.switch_service_account()
                            LOGGER.info(f"Got: {reason}, Trying Again...")
                            self.proc_bytes -= self.file_processed_bytes
                            return self._download_file(
                                file_id, path, filename, mime_type, file_size
                            )
                        LOGGER.error(f"Got: {reason}")
                        raise err
        finally:
            fh.close()
            self.file_processed_bytes = 0
