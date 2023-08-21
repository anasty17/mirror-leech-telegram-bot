#!/usr/bin/env python3
from logging import getLogger
from os import makedirs, path as ospath
from io import FileIO
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, RetryError

from bot import GLOBAL_EXTENSION_FILTER
from bot.helper.ext_utils.bot_utils import setInterval
from bot.helper.ext_utils.bot_utils import async_to_sync
from bot.helper.mirror_utils.gdrive_utlis.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)


class gdDownload(GoogleDriveHelper):

    def __init__(self, name, path, listener):
        super().__init__(listener, name)
        self.__updater = None
        self.__path = path
        self.is_downloading = True

    def download(self, link):
        file_id = self.getIdFromUrl(link, self.listener.user_id)
        self.service = self.authorize()
        self.__updater = setInterval(self.update_interval, self.progress)
        try:
            meta = self.getFileMetadata(file_id)
            if meta.get("mimeType") == self.G_DRIVE_DIR_MIME_TYPE:
                self.__download_folder(file_id, self.__path, self.name)
            else:
                makedirs(self.__path, exist_ok=True)
                self.__download_file(file_id, self.__path,
                                     self.name, meta.get('mimeType'))
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(
                    f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace('>', '').replace('<', '')
            if "downloadQuotaExceeded" in err:
                err = "Download Quota Exceeded."
            elif "File not found" in err:
                if not self.alt_auth:
                    token_service = self.alt_authorize()
                    if token_service is not None:
                        LOGGER.error(
                            'File not found. Trying with token.pickle...')
                        self.service = token_service
                        self.__updater.cancel()
                        return self.download(link)
                err = 'File not found!'
            async_to_sync(self.listener.onDownloadError, err)
            self.is_cancelled = True
        finally:
            self.__updater.cancel()
            if self.is_cancelled:
                return
            async_to_sync(self.listener.onDownloadComplete)

    def __download_folder(self, folder_id, path, folder_name):
        folder_name = folder_name.replace('/', '')
        if not ospath.exists(f"{path}/{folder_name}"):
            makedirs(f"{path}/{folder_name}")
        path += f"/{folder_name}"
        result = self.getFilesByFolderId(folder_id)
        if len(result) == 0:
            return
        if self.listener.user_dict.get('excluded_extensions', False):
            extension_filter = self.listener.user_dict['excluded_extensions']
        elif 'excluded_extensions' not in self.listener.user_dict:
            extension_filter = GLOBAL_EXTENSION_FILTER
        else:
            extension_filter = ['aria2', '!qB']
        result = sorted(result, key=lambda k: k['name'])
        for item in result:
            file_id = item['id']
            filename = item['name']
            shortcut_details = item.get('shortcutDetails')
            if shortcut_details is not None:
                file_id = shortcut_details['targetId']
                mime_type = shortcut_details['targetMimeType']
            else:
                mime_type = item.get('mimeType')
            if mime_type == self.G_DRIVE_DIR_MIME_TYPE:
                self.__download_folder(file_id, path, filename)
            elif not ospath.isfile(f"{path}{filename}") and not filename.lower().endswith(tuple(extension_filter)):
                self.__download_file(file_id, path, filename, mime_type)
            if self.is_cancelled:
                break

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=(retry_if_exception_type(Exception)))
    def __download_file(self, file_id, path, filename, mime_type):
        request = self.service.files().get_media(
            fileId=file_id, supportsAllDrives=True)
        filename = filename.replace('/', '')
        if len(filename.encode()) > 255:
            ext = ospath.splitext(filename)[1]
            filename = f"{filename[:245]}{ext}"
            if self.name.endswith(ext):
                self.name = filename
        if self.is_cancelled:
            return
        fh = FileIO(f"{path}/{filename}", 'wb')
        downloader = MediaIoBaseDownload(
            fh, request, chunksize=100 * 1024 * 1024)
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
                if err.resp.get('content-type', '').startswith('application/json'):
                    reason = eval(err.content).get(
                        'error').get('errors')[0].get('reason')
                    if reason not in [
                        'downloadQuotaExceeded',
                        'dailyLimitExceeded',
                    ]:
                        raise err
                    if self.use_sa:
                        if self.sa_count >= self.sa_number:
                            LOGGER.info(
                                f"Reached maximum number of service accounts switching, which is {self.sa_count}")
                            raise err
                        else:
                            if self.is_cancelled:
                                return
                            self.switchServiceAccount()
                            LOGGER.info(f"Got: {reason}, Trying Again...")
                            return self.__download_file(file_id, path, filename, mime_type)
                    else:
                        LOGGER.error(f"Got: {reason}")
                        raise err
        self.file_processed_bytes = 0
