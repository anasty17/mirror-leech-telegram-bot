#!/usr/bin/env python3
from logging import getLogger
from os import path as ospath, listdir, remove as osremove
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, RetryError

from bot import config_dict, GLOBAL_EXTENSION_FILTER
from bot.helper.ext_utils.fs_utils import get_mime_type
from bot.helper.ext_utils.bot_utils import async_to_sync, setInterval
from bot.helper.mirror_utils.gdrive_utlis.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)


class gdUpload(GoogleDriveHelper):

    def __init__(self, name, path, listener):
        super().__init__(listener, name)
        self.__updater = None
        self.__path = path
        self.__is_errored = False
        self.is_uploading = True

    def user_setting(self):
        if self.listener.upDest.startswith('mtp:'):
            self.token_path = f'tokens/{self.listener.user_id}.pickle'
            self.listener.upDest = self.listener.upDest.lstrip('mtp:')
            self.use_sa = False

    def upload(self, size):
        self.user_setting()
        self.service = self.authorize()
        item_path = f"{self.__path}/{self.name}"
        LOGGER.info(f"Uploading: {item_path}")
        self.__updater = setInterval(self.update_interval, self.progress)
        try:
            if self.listener.user_dict.get('excluded_extensions', False):
                extension_filter = self.listener.user_dict['excluded_extensions']
            elif 'excluded_extensions' not in self.listener.user_dict:
                extension_filter = GLOBAL_EXTENSION_FILTER
            else:
                extension_filter = ['aria2', '!qB']
            if ospath.isfile(item_path):
                if item_path.lower().endswith(tuple(extension_filter)):
                    raise Exception(
                        'This file extension is excluded by extension filter!')
                mime_type = get_mime_type(item_path)
                link = self.__upload_file(
                    item_path, self.name, mime_type, self.listener.upDest, is_dir=False)
                if self.is_cancelled:
                    return
                if link is None:
                    raise Exception('Upload has been manually cancelled')
                LOGGER.info(f"Uploaded To G-Drive: {item_path}")
            else:
                mime_type = 'Folder'
                dir_id = self.create_directory(ospath.basename(
                    ospath.abspath(self.name)), self.listener.upDest)
                result = self.__upload_dir(item_path, dir_id, extension_filter)
                if result is None:
                    raise Exception('Upload has been manually cancelled!')
                link = self.G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(dir_id)
                if self.is_cancelled:
                    return
                LOGGER.info(f"Uploaded To G-Drive: {self.name}")
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(
                    f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace('>', '').replace('<', '')
            async_to_sync(self.listener.onUploadError, err)
            self.__is_errored = True
        finally:
            self.__updater.cancel()
            if self.is_cancelled and not self.__is_errored:
                if mime_type == 'Folder':
                    LOGGER.info("Deleting uploaded data from Drive...")
                    self.service.files().delete(fileId=dir_id, supportsAllDrives=True).execute()
                return
            elif self.__is_errored:
                return
            async_to_sync(self.listener.onUploadComplete, link, size, self.total_files,
                          self.total_folders, mime_type, self.name,
                          dir_id=self.getIdFromUrl(link, self.listener.user_id),
                          private=self.token_path.startswith('tokens/'))

    def __upload_dir(self, input_directory, dest_id, extension_filter):
        list_dirs = listdir(input_directory)
        if len(list_dirs) == 0:
            return dest_id
        new_id = None
        for item in list_dirs:
            current_file_name = ospath.join(input_directory, item)
            if ospath.isdir(current_file_name):
                current_dir_id = self.create_directory(item, dest_id)
                new_id = self.__upload_dir(current_file_name, current_dir_id, extension_filter)
                self.total_folders += 1
            elif not item.lower().endswith(tuple(extension_filter)):
                mime_type = get_mime_type(current_file_name)
                file_name = current_file_name.split("/")[-1]
                self.__upload_file(current_file_name,
                                   file_name, mime_type, dest_id)
                self.total_files += 1
                new_id = dest_id
            else:
                if not self.listener.seed or self.listener.newDir:
                    osremove(current_file_name)
                new_id = 'filter'
            if self.is_cancelled:
                break
        return new_id

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=(retry_if_exception_type(Exception)))
    def __upload_file(self, file_path, file_name, mime_type, dest_id, is_dir=True):
        # File body description
        file_metadata = {
            'name': file_name,
            'description': 'Uploaded by Mirror-leech-telegram-bot',
            'mimeType': mime_type,
        }
        if dest_id is not None:
            file_metadata['parents'] = [dest_id]

        if ospath.getsize(file_path) == 0:
            media_body = MediaFileUpload(file_path,
                                         mimetype=mime_type,
                                         resumable=False)
            response = self.service.files().create(body=file_metadata, media_body=media_body,
                                                   supportsAllDrives=True).execute()
            if not config_dict['IS_TEAM_DRIVE']:
                self.set_permission(response['id'])

            drive_file = self.service.files().get(
                fileId=response['id'], supportsAllDrives=True).execute()
            return self.G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get('id'))
        media_body = MediaFileUpload(file_path,
                                     mimetype=mime_type,
                                     resumable=True,
                                     chunksize=100 * 1024 * 1024)

        # Insert a file
        drive_file = self.service.files().create(
            body=file_metadata, media_body=media_body, supportsAllDrives=True)
        response = None
        retries = 0
        while response is None and not self.is_cancelled:
            try:
                self.status, response = drive_file.next_chunk()
            except HttpError as err:
                if err.resp.status in [500, 502, 503, 504] and retries < 10:
                    retries += 1
                    continue
                if err.resp.get('content-type', '').startswith('application/json'):
                    reason = eval(err.content).get(
                        'error').get('errors')[0].get('reason')
                    if reason not in [
                        'userRateLimitExceeded',
                        'dailyLimitExceeded',
                    ]:
                        raise err
                    if self.use_sa:
                        if self.sa_count >= self.sa_number:
                            LOGGER.info(
                                f"Reached maximum number of service accounts switching, which is {self.__sa_count}")
                            raise err
                        else:
                            if self.is_cancelled:
                                return
                            self.switchServiceAccount()
                            LOGGER.info(f"Got: {reason}, Trying Again.")
                            return self.__upload_file(file_path, file_name, mime_type, dest_id)
                    else:
                        LOGGER.error(f"Got: {reason}")
                        raise err
        if self.is_cancelled:
            return
        if not self.listener.seed or self.listener.newDir:
            try:
                osremove(file_path)
            except:
                pass
        self.file_processed_bytes = 0
        # Insert new permissions
        if not config_dict['IS_TEAM_DRIVE']:
            self.set_permission(response['id'])
        # Define file instance and get url for download
        if not is_dir:
            drive_file = self.service.files().get(
                fileId=response['id'], supportsAllDrives=True).execute()
            return self.G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get('id'))
        return
