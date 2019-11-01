from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
import pickle
import os
import time
from bot import LOGGER, parent_id, DOWNLOAD_DIR, DOWNLOAD_STATUS_UPDATE_INTERVAL
from bot.helper.ext_utils.fs_utils import get_mime_type
from bot.helper.ext_utils.bot_utils import *
from bot.helper.ext_utils.exceptions import KillThreadException
import threading

logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)


class GoogleDriveHelper:

    def __init__(self, listener=None):
        self.__G_DRIVE_TOKEN_FILE = "token.pickle"
        # Check https://developers.google.com/drive/scopes for all available scopes
        self.__OAUTH_SCOPE = "https://www.googleapis.com/auth/drive.file"
        # Redirect URI for installed apps, can be left as is
        self.__REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
        self.__G_DRIVE_DIR_MIME_TYPE = "application/vnd.google-apps.folder"
        self.__G_DRIVE_BASE_DOWNLOAD_URL = "https://drive.google.com/uc?id={}&export=download"
        self.__listener = listener
        self.__service = self.authorize()
        self._file_uploaded_bytes = 0
        self.uploaded_bytes = 0
        self.start_time = 0
        self.total_time = 0
        self._should_update = True
        self.is_uploading = True
        self.is_cancelled = False
        self.status = None

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

    def _on_upload_progress(self):
        while self.is_uploading:
            if self.status is not None:
                chunk_size = self.status.total_size * self.status.progress() - self._file_uploaded_bytes
                self._file_uploaded_bytes = self.status.total_size * self.status.progress()
                LOGGER.info(f'Chunk size: {get_readable_file_size(chunk_size)}')
                self.uploaded_bytes += chunk_size
                self.total_time += DOWNLOAD_STATUS_UPDATE_INTERVAL

                if self._should_update:
                    try:
                        LOGGER.info('Updating messages')
                        _list = get_download_status_list()
                        index = get_download_index(_list, get_download(self.__listener.message.message_id).gid)
                        self.__listener.onUploadProgress(_list, index)
                    except KillThreadException as e:
                        LOGGER.info(f'Stopped calling onDownloadProgress(): {str(e)}')
                        # TODO: Find a way to know if the Error is actually about message not found and not found
                        # self._should_update = False
                        pass
            else:
                LOGGER.info('status: None')
            time.sleep(DOWNLOAD_STATUS_UPDATE_INTERVAL)

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
        return self.__service.files().create(body=file_metadata, media_body=media_body).execute()

    def __set_permission(self, drive_id):
        permissions = {
            'role': 'reader',
            'type': 'anyone',
            'value': None,
            'withLink': True
        }
        return self.__service.permissions().create(fileId=drive_id, body=permissions).execute()

    def upload_file(self, file_path, file_name, mime_type, parent_id):
        # File body description
        file_metadata = {
            'name': file_name,
            'description': 'mirror',
            'mimeType': mime_type,
        }
        if parent_id is not None:
            file_metadata['parents'] = [parent_id]

        if os.path.getsize(file_path):
            media_body = MediaFileUpload(file_path,
                                         mimetype=mime_type,
                                         resumable=False)
            response = self.__service.files().create(body=file_metadata, media_body=media_body).execute()
            self.__set_permission(response['id'])
            drive_file = self.__service.files().get(fileId=response['id']).execute()
            download_url = self.__G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get('id'))
            return download_url
        media_body = MediaFileUpload(file_path,
                                     mimetype=mime_type,
                                     resumable=True,
                                     chunksize=50*1024*1024)

        # Insert a file
        drive_file = self.__service.files().create(body=file_metadata, media_body=media_body)
        response = None
        while response is None:
            if self.is_cancelled:
                return None
            self.status, response = drive_file.next_chunk()
        self._file_uploaded_bytes = 0
        # Insert new permissions
        self.__set_permission(response['id'])
        # Define file instance and get url for download
        drive_file = self.__service.files().get(fileId=response['id']).execute()
        download_url = self.__G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get('id'))
        return download_url

    def upload(self, file_name: str):
        _list = get_download_status_list()
        index = get_download_index(_list, get_download(self.__listener.message.message_id).gid)
        self.__listener.onUploadStarted(_list, index)
        file_dir = f"{DOWNLOAD_DIR}{self.__listener.message.message_id}"
        file_path = f"{file_dir}/{file_name}"
        LOGGER.info("Uploading File: " + file_name)
        self.start_time = time.time()
        threading.Thread(target=self._on_upload_progress).start()
        if os.path.isfile(file_path):
            try:
                mime_type = get_mime_type(file_path)
                link = self.upload_file(file_path, file_name, mime_type, parent_id)
                if link is None:
                    raise Exception('Upload has been manually cancelled')
                LOGGER.info("Uploaded To G-Drive: " + file_path)
            except Exception as e:
                LOGGER.error(str(e))
                e_str = str(e).replace('<', '')
                e_str = e_str.replace('>', '')
                self.__listener.onUploadError(e_str, _list, index)
                return
            finally:
                self.is_uploading = False
        else:
            try:
                dir_id = self.create_directory(os.path.basename(os.path.abspath(file_name)), parent_id)
                result = self.upload_dir(file_path, dir_id)
                if result is None:
                    raise Exception('Upload has been manually cancelled!')
                LOGGER.info("Uploaded To G-Drive: " + file_name)
                link = f"https://drive.google.com/folderview?id={dir_id}"
            except Exception as e:
                LOGGER.error(str(e))
                e_str = str(e).replace('<', '')
                e_str = e_str.replace('>', '')
                self.__listener.onUploadError(e_str, _list, index)
                return
            finally:
                self.is_uploading = False
        LOGGER.info(download_dict)
        self.__listener.onUploadComplete(link, _list, index)
        LOGGER.info("Deleting downloaded file/folder..")
        return link

    def create_directory(self, directory_name, parent_id):
        file_metadata = {
            "name": directory_name,
            "mimeType": self.__G_DRIVE_DIR_MIME_TYPE
        }
        if parent_id is not None:
            file_metadata["parents"] = [parent_id]
        file = self.__service.files().create(body=file_metadata).execute()
        file_id = file.get("id")
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
        return build('drive', 'v3', credentials=credentials, cache_discovery=False)

    def drive_list(self, fileName):
        msg = ""
        # Create Search Query for API request.
        query = f"'{parent_id}' in parents and (name contains '{fileName}')"
        page_token = None
        results = []
        while True:
            response = self.__service.files().list(q=query,
                                                   spaces='drive',
                                                   fields='nextPageToken, files(id, name, mimeType, size)',
                                                   pageToken=page_token,
                                                   orderBy='modifiedTime desc').execute()
            for file in response.get('files', []):
                if file.get(
                        'mimeType') == "application/vnd.google-apps.folder":  # Detect Whether Current Entity is a Folder or File.
                    if len(results) >= 20:
                        break
                    msg += f"⁍ <a href='https://drive.google.com/drive/folders/{file.get('id')}'>{file.get('name')}" \
                           f"</a> (folder)" + "\n"
                    results.append(file)
                else:
                    if len(results) >= 20:
                        break
                    msg += f"⁍ <a href='https://drive.google.com/uc?id={file.get('id')}" \
                           f"&export=download'>{file.get('name')}</a> ({get_readable_file_size(int(file.get('size')))})" + "\n"
                    results.append(file)
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        del results
        return msg
