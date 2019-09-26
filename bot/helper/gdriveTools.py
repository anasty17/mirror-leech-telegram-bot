from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
import pickle
import os
from bot import LOGGER, parent_id, DOWNLOAD_DIR, download_list
from .listeners import MirrorListeners
from .fs_utils import clean_download, get_mime_type
from .bot_utils import *


class GoogleDriveHelper:

    def __init__(self, listener: MirrorListeners):
        self.__G_DRIVE_TOKEN_FILE = "token.pickle"
        # Check https://developers.google.com/drive/scopes for all available scopes
        self.__OAUTH_SCOPE = "https://www.googleapis.com/auth/drive.file"
        # Redirect URI for installed apps, can be left as is
        self.__REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
        self.__G_DRIVE_DIR_MIME_TYPE = "application/vnd.google-apps.folder"
        self.__G_DRIVE_BASE_DOWNLOAD_URL = "https://drive.google.com/uc?id={}&export=download"
        self.__listener = listener
        self.__service = self.authorize()

    def upload_file(self, file_path, file_name, mime_type,parent_id):
        # File body description
        media_body = MediaFileUpload(file_path,
                                     mimetype=mime_type,
                                     resumable=True)
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
        drive_file = self.__service.files().create(body=file_metadata, media_body=media_body).execute()
        # Insert new permissions
        self.__service.permissions().create(fileId=drive_file['id'], body=permissions).execute()
        # Define file instance and get url for download
        drive_file = self.__service.files().get(fileId=drive_file['id']).execute()
        download_url = self.__G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get('id'))
        return download_url

    def upload(self, file_name: str):
        _list = get_download_status_list()
        index = get_download_index(_list, get_download(self.__listener.update.update_id).gid)
        self.__listener.onUploadStarted(_list, index)
        file_dir = "{}{}".format(DOWNLOAD_DIR, self.__listener.update.update_id)
        file_path = "{}/{}".format(file_dir, file_name)
        link = None
        LOGGER.info("Uploading File: " + file_name)
        if os.path.isfile(file_path):
            mime_type = get_mime_type(file_path)
            try:
                g_drive_link = self.upload_file(file_path, file_name, mime_type,parent_id)
                LOGGER.info("Uploaded To G-Drive: " + file_path)
                link = g_drive_link
            except Exception as e:
                LOGGER.error(str(e))
                pass
        else:
            try:
                dir_id = self.create_directory(os.path.basename(os.path.abspath(file_name)),parent_id)
                self.upload_dir(file_path,dir_id)
                LOGGER.info("Uploaded To G-Drive: " + file_name)
                link = "https://drive.google.com/folderview?id={}".format(dir_id)
            except Exception as e:
                LOGGER.error(str(e))
                self.__listener.onUploadError(str(e))
                clean_download(file_dir)
                raise Exception('Error: {}'.format(str(e)))
        del download_list[self.__listener.update.update_id]
        LOGGER.info(download_list)
        self.__listener.onUploadComplete(link, _list, index)
        LOGGER.info("Deleting downloaded file/folder..")
        clean_download(file_dir)
        return link

    def create_directory(self, directory_name,parent_id):
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
        r_p_id = None
        for a_c_f_name in list_dirs:
            current_file_name = os.path.join(input_directory, a_c_f_name)
            if os.path.isdir(current_file_name):
                current_dir_id = self.create_directory(a_c_f_name, parent_id)
                r_p_id = self.upload_dir(current_file_name, current_dir_id)
            else:
                mime_type = get_mime_type(current_file_name)
                file_name = current_file_name.split("/")[-1]
                # current_file_name will have the full path
                self.upload_file(current_file_name, file_name, mime_type, parent_id)
                r_p_id = parent_id
        return r_p_id

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

    def drive_list(self,fileName):
        msg = ""
        #Create Search Query for API request.
        query = "'{}' in parents and (name contains '{}')".format(parent_id,fileName)
        page_token = None
        while True:
            response = self.__service.files().list(q=query,
                                              spaces='drive',
                                              fields='nextPageToken, files(id, name, mimeType)',
                                              pageToken=page_token).execute()
            for file in response.get('files',[]):
                if file.get('mimeType') == "application/vnd.google-apps.folder":
                    msg +='⁍ <a href="https://drive.google.com/drive/folders/{}">{}</a> (folder)'.format(file.get('id'),file.get('name'))+"\n"
                # Detect Whether Current Entity is a Folder or File.
                else:
                    msg += '⁍ <a href="https://drive.google.com/uc?id={}&export=download">{}</a>'.format(file.get('id'),file.get('name'))+"\n"
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        return msg        