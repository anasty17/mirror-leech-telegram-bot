from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
import pickle
import os
import time
from bot import LOGGER, parent_id, DOWNLOAD_DIR
from bot.helper.ext_utils.fs_utils import get_mime_type
from bot.helper.ext_utils.bot_utils import *
from bot.helper.ext_utils.exceptions import KillThreadException

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
        self.uploadedBytes = 0
        self.start_time = 0

    def upload_file(self, file_path, file_name, mime_type, parent_id):
        # File body description
        media_body = MediaFileUpload(file_path,
                                     mimetype=mime_type,
                                     resumable=True,
                                     chunksize=1024*1024)
        file_metadata = {
            'name': file_name,
            'description': 'mirror',
            'mimeType': mime_type,
        }
        if parent_id is not None:
            file_metadata['parents'] = [parent_id]
        # Permissions body description: anyone who has link can upload
        # Other permissions can be found at https://developers.google.com/drive/v2/reference/permissions
        permissions = {
            'role': 'reader',
            'type': 'anyone',
            'value': None,
            'withLink': True
        }
        # Insert a file
        drive_file = self.__service.files().create(body=file_metadata, media_body=media_body)
        response = None
        _list = get_download_status_list()
        index = get_download_index(_list, get_download(self.__listener.message.message_id).gid)
        uploaded_bytes = 0
        loop_count = 0
        should_update = True
        while response is None:
            status, response = drive_file.next_chunk()
            time_lapsed = time.time() - self.start_time
            # Update the message only if status is not null and loop_count is multiple of 50
            if status and loop_count % 50 == 0:
                chunk_size = status.total_size * status.progress() - uploaded_bytes
                uploaded_bytes = status.total_size * status.progress()

                # LOGGER.info(f'{file_name}: {status.progress() * 100}')

                with download_dict_lock:
                    download_dict[self.__listener.uid].uploaded_bytes += chunk_size
                    download_dict[self.__listener.uid].upload_time = time_lapsed
                if should_update:
                    try:
                        self.__listener.onUploadProgress(_list, index)
                    except KillThreadException:
                        should_update = False
            loop_count += 1

        # Insert new permissions
        self.__service.permissions().create(fileId=response['id'], body=permissions).execute()
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
        if os.path.isfile(file_path):
            try:
                mime_type = get_mime_type(file_path)
                g_drive_link = self.upload_file(file_path, file_name, mime_type, parent_id)
                LOGGER.info("Uploaded To G-Drive: " + file_path)
                link = g_drive_link
            except Exception as e:
                LOGGER.error(str(e))
                e_str = str(e).replace('<', '')
                e_str = e_str.replace('>', '')
                self.__listener.onUploadError(e_str, _list, index)
                return
        else:
            try:
                dir_id = self.create_directory(os.path.basename(os.path.abspath(file_name)), parent_id)
                self.upload_dir(file_path, dir_id)
                LOGGER.info("Uploaded To G-Drive: " + file_name)
                link = f"https://drive.google.com/folderview?id={dir_id}"
            except Exception as e:
                LOGGER.error(str(e))
                e_str = str(e).replace('<', '')
                e_str = e_str.replace('>', '')
                self.__listener.onUploadError(e_str, _list, index)
                return
        LOGGER.info(download_dict)
        self.__listener.onUploadComplete(link, _list, index)
        LOGGER.info("Deleting downloaded file/folder..")
        return link

    def create_directory(self, directory_name, parent_id):
        permissions = {
            "role": "reader",
            "type": "anyone",
            "value": None,
            "withLink": True
        }
        file_metadata = {
            "name": directory_name,
            "mimeType": self.__G_DRIVE_DIR_MIME_TYPE
        }
        if parent_id is not None:
            file_metadata["parents"] = [parent_id]
        file = self.__service.files().create(body=file_metadata).execute()
        file_id = file.get("id")
        self.__service.permissions().create(fileId=file_id, body=permissions).execute()
        LOGGER.info("Created Google-Drive Folder:\nName: {}\nID: {} ".format(file.get("name"), file_id))
        return file_id

    def upload_dir(self, input_directory, parent_id):
        list_dirs = os.listdir(input_directory)
        if len(list_dirs) == 0:
            return parent_id
        new_id = None
        for item in list_dirs:
            current_file_name = os.path.join(input_directory, item)
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
        while True:
            response = self.__service.files().list(q=query,
                                                   spaces='drive',
                                                   fields='nextPageToken, files(id, name, mimeType)',
                                                   pageToken=page_token).execute()
            for file in response.get('files', []):
                if file.get('mimeType') == "application/vnd.google-apps.folder":
                    msg += f"⁍ <a href='https://drive.google.com/drive/folders/{file.get('id')}'>{file.get('name')}" \
                           f"</a> (folder)" + "\n"
                # Detect Whether Current Entity is a Folder or File.
                else:
                    msg += f"⁍ <a href='https://drive.google.com/uc?id={file.get('id')}" \
                           f"&export=download'>{file.get('name')}</a>" + "\n"
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        return msg
