import os
import pickle
import urllib.parse as urlparse
from urllib.parse import parse_qs

import re
import json
import requests

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from tenacity import *

from bot import parent_id, DOWNLOAD_DIR, IS_TEAM_DRIVE, INDEX_URL, \
    USE_SERVICE_ACCOUNTS
from bot.helper.ext_utils.bot_utils import *
from bot.helper.ext_utils.fs_utils import get_mime_type

LOGGER = logging.getLogger(__name__)
logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)
SERVICE_ACCOUNT_INDEX = 0


class GoogleDriveHelper:
    def __init__(self, name=None, listener=None):
        self.__G_DRIVE_TOKEN_FILE = "token.pickle"
        # Check https://developers.google.com/drive/scopes for all available scopes
        self.__OAUTH_SCOPE = ['https://www.googleapis.com/auth/drive']
        # Redirect URI for installed apps, can be left as is
        self.__REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
        self.__G_DRIVE_DIR_MIME_TYPE = "application/vnd.google-apps.folder"
        self.__G_DRIVE_BASE_DOWNLOAD_URL = "https://drive.google.com/uc?id={}&export=download"
        self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL = "https://drive.google.com/drive/folders/{}"
        self.__listener = listener
        self.__service = self.authorize()
        self.__listener = listener
        self._file_uploaded_bytes = 0
        self.uploaded_bytes = 0
        self.UPDATE_INTERVAL = 5
        self.start_time = 0
        self.total_time = 0
        self._should_update = True
        self.is_uploading = True
        self.is_cancelled = False
        self.status = None
        self.updater = None
        self.name = name
        self.update_interval = 3

    def cancel(self):
        self.is_cancelled = True
        self.is_uploading = False

    def speed(self):
        """
        It calculates the average upload speed and returns it in bytes/seconds unit
        :return: Upload speed in bytes/second
        """
        try:
            return self.uploaded_bytes / self.total_time
        except ZeroDivisionError:
            return 0

    @staticmethod
    def getIdFromUrl(link: str):
        if "folders" in link or "file" in link:
            regex = r"https://drive\.google\.com/(drive)?/?u?/?\d?/?(mobile)?/?(file)?(folders)?/?d?/([-\w]+)[?+]?/?(w+)?"
            res = re.search(regex,link)
            if res is None:
                raise IndexError("GDrive ID not found.")
            return res.group(5)
        parsed = urlparse.urlparse(link)
        return parse_qs(parsed.query)['id'][0]

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def _on_upload_progress(self):
        if self.status is not None:
            chunk_size = self.status.total_size * self.status.progress() - self._file_uploaded_bytes
            self._file_uploaded_bytes = self.status.total_size * self.status.progress()
            LOGGER.debug(f'Uploading {self.name}, chunk size: {get_readable_file_size(chunk_size)}')
            self.uploaded_bytes += chunk_size
            self.total_time += self.update_interval

    def __upload_empty_file(self, path, file_name, mime_type, parent_id=None):
        media_body = MediaFileUpload(path,
                                     mimetype=mime_type,
                                     resumable=False)
        file_metadata = {
            'name': file_name,
            'description': 'mirror',
            'mimeType': mime_type,
        }
        if parent_id is not None:
            file_metadata['parents'] = [parent_id]
        return self.__service.files().create(supportsTeamDrives=True,
                                             body=file_metadata, media_body=media_body).execute()

    def switchServiceAccount(self):
        global SERVICE_ACCOUNT_INDEX
        service_account_count = len(os.listdir("accounts"))
        if SERVICE_ACCOUNT_INDEX == service_account_count - 1:
            SERVICE_ACCOUNT_INDEX = 0
        SERVICE_ACCOUNT_INDEX += 1
        LOGGER.info(f"Switching to {SERVICE_ACCOUNT_INDEX}.json service account")
        self.__service = self.authorize()

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def __set_permission(self, drive_id):
        permissions = {
            'role': 'reader',
            'type': 'anyone',
            'value': None,
            'withLink': True
        }
        return self.__service.permissions().create(supportsTeamDrives=True, fileId=drive_id,
                                                   body=permissions).execute()

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def upload_file(self, file_path, file_name, mime_type, parent_id):
        # File body description
        file_metadata = {
            'name': file_name,
            'description': 'mirror',
            'mimeType': mime_type,
        }
        if parent_id is not None:
            file_metadata['parents'] = [parent_id]

        if os.path.getsize(file_path) == 0:
            media_body = MediaFileUpload(file_path,
                                         mimetype=mime_type,
                                         resumable=False)
            response = self.__service.files().create(supportsTeamDrives=True,
                                                     body=file_metadata, media_body=media_body).execute()
            if not IS_TEAM_DRIVE:
                self.__set_permission(response['id'])

            drive_file = self.__service.files().get(supportsTeamDrives=True,
                                                    fileId=response['id']).execute()
            download_url = self.__G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get('id'))
            return download_url
        media_body = MediaFileUpload(file_path,
                                     mimetype=mime_type,
                                     resumable=True,
                                     chunksize=50 * 1024 * 1024)

        # Insert a file
        drive_file = self.__service.files().create(supportsTeamDrives=True,
                                                   body=file_metadata, media_body=media_body)
        response = None
        while response is None:
            if self.is_cancelled:
                return None
            try:
                self.status, response = drive_file.next_chunk()
            except HttpError as err:
                if err.resp.get('content-type', '').startswith('application/json'):
                    reason = json.loads(err.content).get('error').get('errors')[0].get('reason')
                    if reason == 'userRateLimitExceeded' or reason == 'dailyLimitExceeded':
                        if USE_SERVICE_ACCOUNTS:
                            self.switchServiceAccount()
                            LOGGER.info(f"Got: {reason}, Trying Again.")
                            self.upload_file(file_path, file_name, mime_type, parent_id)
                    else:
                        raise err
        self._file_uploaded_bytes = 0
        # Insert new permissions
        if not IS_TEAM_DRIVE:
            self.__set_permission(response['id'])
        # Define file instance and get url for download
        drive_file = self.__service.files().get(supportsTeamDrives=True, fileId=response['id']).execute()
        download_url = self.__G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get('id'))
        return download_url

    def upload(self, file_name: str):
        if USE_SERVICE_ACCOUNTS:
            self.service_account_count = len(os.listdir("accounts"))
        self.__listener.onUploadStarted()
        file_dir = f"{DOWNLOAD_DIR}{self.__listener.message.message_id}"
        file_path = f"{file_dir}/{file_name}"
        LOGGER.info("Uploading File: " + file_path)
        self.start_time = time.time()
        self.updater = setInterval(self.update_interval, self._on_upload_progress)
        if os.path.isfile(file_path):
            try:
                mime_type = get_mime_type(file_path)
                link = self.upload_file(file_path, file_name, mime_type, parent_id)
                if link is None:
                    raise Exception('Upload has been manually cancelled')
                LOGGER.info("Uploaded To G-Drive: " + file_path)
            except Exception as e:
                if isinstance(e, RetryError):
                    LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                    err = e.last_attempt.exception()
                else:
                    err = e
                LOGGER.error(err)
                self.__listener.onUploadError(str(err))
                return
            finally:
                self.updater.cancel()
        else:
            try:
                dir_id = self.create_directory(os.path.basename(os.path.abspath(file_name)), parent_id)
                result = self.upload_dir(file_path, dir_id)
                if result is None:
                    raise Exception('Upload has been manually cancelled!')
                LOGGER.info("Uploaded To G-Drive: " + file_name)
                link = f"https://drive.google.com/folderview?id={dir_id}"
            except Exception as e:
                if isinstance(e, RetryError):
                    LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                    err = e.last_attempt.exception()
                else:
                    err = e
                LOGGER.error(err)
                self.__listener.onUploadError(str(err))
                return
            finally:
                self.updater.cancel()
        LOGGER.info(download_dict)
        self.__listener.onUploadComplete(link)
        LOGGER.info("Deleting downloaded file/folder..")
        return link

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def copyFile(self, file_id, dest_id):
        body = {
            'parents': [dest_id]
        }

        try:
            res = self.__service.files().copy(supportsAllDrives=True,fileId=file_id,body=body).execute()
            return res
        except HttpError as err:
            if err.resp.get('content-type', '').startswith('application/json'):
                reason = json.loads(err.content).get('error').get('errors')[0].get('reason')
                if reason == 'userRateLimitExceeded' or reason == 'dailyLimitExceeded':
                    if USE_SERVICE_ACCOUNTS:
                        self.switchServiceAccount()
                        LOGGER.info(f"Got: {reason}, Trying Again.")
                        self.copyFile(file_id,dest_id)
                else:
                    raise err

    def clone(self, link):
        self.transferred_size = 0
        try:
            file_id = self.getIdFromUrl(link)
        except (KeyError,IndexError):
            msg = "Google drive ID could not be found in the provided link"
            return msg
        msg = ""
        LOGGER.info(f"File ID: {file_id}")
        try:
            meta = self.__service.files().get(supportsAllDrives=True, fileId=file_id,
                                              fields="name,id,mimeType,size").execute()
        except Exception as e:
            return f"{str(e).replace('>', '').replace('<', '')}"
        if meta.get("mimeType") == self.__G_DRIVE_DIR_MIME_TYPE:
            dir_id = self.create_directory(meta.get('name'), parent_id)
            try:
                result = self.cloneFolder(meta.get('name'), meta.get('name'), meta.get('id'), dir_id)
            except Exception as e:
                if isinstance(e, RetryError):
                    LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                    err = e.last_attempt.exception()
                else:
                    err = str(e).replace('>', '').replace('<', '')
                LOGGER.error(err)
                return err
            msg += f'<a href="{self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(dir_id)}">{meta.get("name")}</a>' \
                   f' ({get_readable_file_size(self.transferred_size)})'
            if INDEX_URL is not None:
                url = requests.utils.requote_uri(f'{INDEX_URL}/{meta.get("name")}/')
                msg += f' | <a href="{url}"> Index URL</a>'
        else:
            try:
                file = self.copyFile(meta.get('id'), parent_id)
            except Exception as e:
                if isinstance(e, RetryError):
                    LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                    err = e.last_attempt.exception()
                else:
                    err = str(e).replace('>', '').replace('<', '')
                LOGGER.error(err)
                return err
            msg += f'<a href="{self.__G_DRIVE_BASE_DOWNLOAD_URL.format(file.get("id"))}">{file.get("name")}</a>'
            try:
                msg += f' ({get_readable_file_size(int(meta.get("size")))}) '
                if INDEX_URL is not None:
                    url = requests.utils.requote_uri(f'{INDEX_URL}/{file.get("name")}')
                    msg += f' | <a href="{url}"> Index URL</a>'
            except TypeError:
                pass
        return msg

    def cloneFolder(self, name, local_path, folder_id, parent_id):
        page_token = None
        q = f"'{folder_id}' in parents"
        files = []
        LOGGER.info(f"Syncing: {local_path}")
        new_id = None
        while True:
            response = self.__service.files().list(supportsTeamDrives=True,
                                                   includeTeamDriveItems=True,
                                                   q=q,
                                                   spaces='drive',
                                                   fields='nextPageToken, files(id, name, mimeType,size)',
                                                   pageToken=page_token).execute()
            for file in response.get('files', []):
                files.append(file)
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        if len(files) == 0:
            return parent_id
        for file in files:
            if file.get('mimeType') == self.__G_DRIVE_DIR_MIME_TYPE:
                file_path = os.path.join(local_path, file.get('name'))
                current_dir_id = self.create_directory(file.get('name'), parent_id)
                new_id = self.cloneFolder(file.get('name'), file_path, file.get('id'), current_dir_id)
            else:
                try:
                    self.transferred_size += int(file.get('size'))
                except TypeError:
                    pass
                try:
                    self.copyFile(file.get('id'), parent_id)
                    new_id = parent_id
                except Exception as e:
                    if isinstance(e, RetryError):
                        LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                        err = e.last_attempt.exception()
                    else:
                        err = e
                    LOGGER.error(err)
        return new_id

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(5),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, logging.DEBUG))
    def create_directory(self, directory_name, parent_id):
        file_metadata = {
            "name": directory_name,
            "mimeType": self.__G_DRIVE_DIR_MIME_TYPE
        }
        if parent_id is not None:
            file_metadata["parents"] = [parent_id]
        file = self.__service.files().create(supportsTeamDrives=True, body=file_metadata).execute()
        file_id = file.get("id")
        if not IS_TEAM_DRIVE:
            self.__set_permission(file_id)
        LOGGER.info("Created Google-Drive Folder:\nName: {}\nID: {} ".format(file.get("name"), file_id))
        return file_id

    def upload_dir(self, input_directory, parent_id):
        list_dirs = os.listdir(input_directory)
        if len(list_dirs) == 0:
            return parent_id
        new_id = None
        for item in list_dirs:
            current_file_name = os.path.join(input_directory, item)
            if self.is_cancelled:
                return None
            if os.path.isdir(current_file_name):
                current_dir_id = self.create_directory(item, parent_id)
                new_id = self.upload_dir(current_file_name, current_dir_id)
            else:
                mime_type = get_mime_type(current_file_name)
                file_name = current_file_name.split("/")[-1]
                # current_file_name will have the full path
                self.upload_file(current_file_name, file_name, mime_type, parent_id)
                new_id = parent_id
        return new_id

    def authorize(self):
        # Get credentials
        credentials = None
        if not USE_SERVICE_ACCOUNTS:
            if os.path.exists(self.__G_DRIVE_TOKEN_FILE):
                with open(self.__G_DRIVE_TOKEN_FILE, 'rb') as f:
                    credentials = pickle.load(f)
            if credentials is None or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', self.__OAUTH_SCOPE)
                    LOGGER.info(flow)
                    credentials = flow.run_console(port=0)

                # Save the credentials for the next run
                with open(self.__G_DRIVE_TOKEN_FILE, 'wb') as token:
                    pickle.dump(credentials, token)
        else:
            LOGGER.info(f"Authorizing with {SERVICE_ACCOUNT_INDEX}.json service account")
            credentials = service_account.Credentials.from_service_account_file(
                f'accounts/{SERVICE_ACCOUNT_INDEX}.json',
                scopes=self.__OAUTH_SCOPE)
        return build('drive', 'v3', credentials=credentials, cache_discovery=False)

    def drive_list(self, fileName):
        msg = ""
        # Create Search Query for API request.
        query = f"'{parent_id}' in parents and (name contains '{fileName}')"
        response = self.__service.files().list(supportsTeamDrives=True,
                                               includeTeamDriveItems=True,
                                               q=query,
                                               spaces='drive',
                                               pageSize=20,
                                               fields='files(id, name, mimeType, size)',
                                               orderBy='modifiedTime desc').execute()
        for file in response.get('files', []):
            if file.get(
                    'mimeType') == "application/vnd.google-apps.folder":  # Detect Whether Current Entity is a Folder or File.
                msg += f"⁍ <a href='https://drive.google.com/drive/folders/{file.get('id')}'>{file.get('name')}" \
                       f"</a> (folder)"
                if INDEX_URL is not None:
                    url = requests.utils.requote_uri(f'{INDEX_URL}/{file.get("name")}/')
                    msg += f' | <a href="{url}"> Index URL</a>'
            else:
                msg += f"⁍ <a href='https://drive.google.com/uc?id={file.get('id')}" \
                       f"&export=download'>{file.get('name')}</a> ({get_readable_file_size(int(file.get('size')))})"
                if INDEX_URL is not None:
                    url = requests.utils.requote_uri(f'{INDEX_URL}/{file.get("name")}')
                    msg += f' | <a href="{url}"> Index URL</a>'
            msg += '\n'
        return msg
