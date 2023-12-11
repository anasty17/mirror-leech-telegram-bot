from logging import getLogger
from os import makedirs, path as ospath
from io import FileIO
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
    RetryError,
)

from bot.helper.ext_utils.bot_utils import setInterval
from bot.helper.ext_utils.bot_utils import async_to_sync
from bot.helper.mirror_utils.gdrive_utils.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)


class gdDownload(GoogleDriveHelper):
    def __init__(self, listener, path):
        self.listener = listener
        self._updater = None
        self._path = path
        super().__init__()
        self.is_downloading = True

    def download(self):
        file_id = self.getIdFromUrl(self.listener.link, self.listener.user_id)
        self.service = self.authorize()
        self._updater = setInterval(self.update_interval, self.progress)
        try:
            meta = self.getFileMetadata(file_id)
            if meta.get("mimeType") == self.G_DRIVE_DIR_MIME_TYPE:
                self._download_folder(file_id, self._path, self.listener.name)
            else:
                makedirs(self._path, exist_ok=True)
                self._download_file(
                    file_id, self._path, self.listener.name, meta.get("mimeType")
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
                    self._updater.cancel()
                    return self.download()
                err = "File not found!"
            async_to_sync(self.listener.onDownloadError, err)
            self.is_cancelled = True
        finally:
            self._updater.cancel()
            if self.is_cancelled:
                return
            async_to_sync(self.listener.onDownloadComplete)

    def _download_folder(self, folder_id, path, folder_name):
        folder_name = folder_name.replace("/", "")
        if not ospath.exists(f"{path}/{folder_name}"):
            makedirs(f"{path}/{folder_name}")
        path += f"/{folder_name}"
        result = self.getFilesByFolderId(folder_id)
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
            elif not ospath.isfile(
                f"{path}{filename}"
            ) and not filename.lower().endswith(tuple(self.listener.extension_filter)):
                self._download_file(file_id, path, filename, mime_type)
            if self.is_cancelled:
                break

    @retry(
        wait=wait_exponential(multiplier=2, min=3, max=6),
        stop=stop_after_attempt(3),
        retry=(retry_if_exception_type(Exception)),
    )
    def _download_file(self, file_id, path, filename, mime_type):
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
        filename = filename.replace("/", "")
        if len(filename.encode()) > 255:
            ext = ospath.splitext(filename)[1]
            filename = f"{filename[:245]}{ext}"
            if self.listener.name.endswith(ext):
                self.listener.name = filename
        if self.is_cancelled:
            return
        fh = FileIO(f"{path}/{filename}", "wb")
        downloader = MediaIoBaseDownload(fh, request, chunksize=100 * 1024 * 1024)
        done = False
        retries = 0
        while not done:
            if self.is_cancelled:
                fh.close()
                break
            try:
                self.status, done = downloader.next_chunk()
            except HttpError as err:
                if err.resp.status in [500, 502, 503, 504] and retries < 10:
                    retries += 1
                    continue
                if err.resp.get("content-type", "").startswith("application/json"):
                    reason = (
                        eval(err.content).get("error").get("errors")[0].get("reason")
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
                        else:
                            if self.is_cancelled:
                                return
                            self.switchServiceAccount()
                            LOGGER.info(f"Got: {reason}, Trying Again...")
                            return self._download_file(
                                file_id, path, filename, mime_type
                            )
                    else:
                        LOGGER.error(f"Got: {reason}")
                        raise err
        self.file_processed_bytes = 0
