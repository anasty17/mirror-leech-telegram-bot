#!/usr/bin/env python3
from logging import getLogger
from time import time
from os import path as ospath
from googleapiclient.errors import HttpError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, RetryError

from bot import config_dict, GLOBAL_EXTENSION_FILTER
from bot.helper.ext_utils.bot_utils import async_to_sync
from bot.helper.mirror_utils.gdrive_utlis.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)


class gdClone(GoogleDriveHelper):

    def __init__(self, name, listener):
        super().__init__(listener, name)
        self.__start_time = time()
        self.is_cloning = True

    def user_setting(self, link):
        if self.listener.upDest.startswith('mtp:') or link.startswith('mtp:'):
            self.token_path = f'tokens/{self.listener.user_id}.pickle'
            self.listener.upDest = self.listener.upDest.lstrip('mtp:')
            self.use_sa = False

    def clone(self, link):
        self.user_setting(link)
        try:
            file_id = self.getIdFromUrl(link, self.listener.user_id)
        except (KeyError, IndexError):
            return "Google Drive ID could not be found in the provided link"
        self.service = self.authorize()
        msg = ""
        LOGGER.info(f"File ID: {file_id}")
        try:
            meta = self.getFileMetadata(file_id)
            mime_type = meta.get("mimeType")
            if mime_type == self.G_DRIVE_DIR_MIME_TYPE:
                dir_id = self.create_directory(
                    meta.get('name'), self.listener.upDest)
                self.__cloneFolder(meta.get('name'), meta.get('id'), dir_id)
                durl = self.G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(dir_id)
                if self.is_cancelled:
                    LOGGER.info("Deleting cloned data from Drive...")
                    self.service.files().delete(fileId=dir_id, supportsAllDrives=True).execute()
                    return None, None, None, None, None, None
                mime_type = 'Folder'
                size = self.proc_bytes
            else:
                file = self.__copyFile(
                    meta.get('id'), self.listener.upDest)
                msg += f'<b>Name: </b><code>{file.get("name")}</code>'
                durl = self.G_DRIVE_BASE_DOWNLOAD_URL.format(file.get("id"))
                if mime_type is None:
                    mime_type = 'File'
                size = int(meta.get('size', 0))
            return durl, size, mime_type, self.total_files, self.total_folders, self.getIdFromUrl(durl, self.listener.user_id)
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(
                    f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace('>', '').replace('<', '')
            if "User rate limit exceeded" in err:
                msg = "User rate limit exceeded."
            elif "File not found" in err:
                if not self.alt_auth:
                    token_service = self.alt_authorize()
                    if token_service is not None:
                        LOGGER.error(
                            'File not found. Trying with token.pickle...')
                        self.service = token_service
                        return self.clone(link)
                msg = "File not found."
            else:
                msg = f"Error.\n{err}"
            async_to_sync(self.listener.onUploadError, msg)
            return None, None, None, None, None, None

    def __cloneFolder(self, folder_name, folder_id, dest_id):
        LOGGER.info(f"Syncing: {folder_name}")
        files = self.getFilesByFolderId(folder_id)
        if len(files) == 0:
            return dest_id
        if self.listener.user_dict.get('excluded_extensions', False):
            extension_filter = self.listener.user_dict['excluded_extensions']
        elif 'excluded_extensions' not in self.listener.user_dict:
            extension_filter = GLOBAL_EXTENSION_FILTER
        else:
            extension_filter = ['aria2', '!qB']
        for file in files:
            if file.get('mimeType') == self.G_DRIVE_DIR_MIME_TYPE:
                self.total_folders += 1
                file_path = ospath.join(folder_name, file.get('name'))
                current_dir_id = self.create_directory(
                    file.get('name'), dest_id)
                self.__cloneFolder(file_path, file.get('id'), current_dir_id)
            elif not file.get('name').lower().endswith(tuple(extension_filter)):
                self.total_files += 1
                self.__copyFile(file.get('id'), dest_id)
                self.proc_bytes += int(file.get('size', 0))
                self.total_time = int(time() - self.__start_time)
            if self.is_cancelled:
                break

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=retry_if_exception_type(Exception))
    def __copyFile(self, file_id, dest_id):
        body = {'parents': [dest_id]}
        try:
            return self.service.files().copy(fileId=file_id, body=body, supportsAllDrives=True).execute()
        except HttpError as err:
            if err.resp.get('content-type', '').startswith('application/json'):
                reason = eval(err.content).get(
                    'error').get('errors')[0].get('reason')
                if reason not in ['userRateLimitExceeded', 'dailyLimitExceeded', 'cannotCopyFile']:
                    raise err
                if reason == 'cannotCopyFile':
                    LOGGER.error(err)
                elif self.use_sa:
                    if self.sa_count >= self.sa_number:
                        LOGGER.info(
                            f"Reached maximum number of service accounts switching, which is {self.sa_count}")
                        raise err
                    else:
                        if self.is_cancelled:
                            return
                        self.switchServiceAccount()
                        return self.__copyFile(file_id, dest_id)
                else:
                    LOGGER.error(f"Got: {reason}")
                    raise err
