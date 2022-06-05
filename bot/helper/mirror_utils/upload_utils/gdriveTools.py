from logging import getLogger, ERROR, DEBUG
from time import time
from pickle import load as pload
from json import loads as jsnloads
from os import makedirs, path as ospath, listdir
from requests.utils import quote as rquote
from io import FileIO
from re import search as re_search
from urllib.parse import parse_qs, urlparse
from random import randrange
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from telegram import InlineKeyboardMarkup
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_log, RetryError

from bot.helper.telegram_helper.button_build import ButtonMaker
from bot import parent_id, DOWNLOAD_DIR, IS_TEAM_DRIVE, INDEX_URL, USE_SERVICE_ACCOUNTS, BUTTON_FOUR_NAME, \
                BUTTON_FOUR_URL, BUTTON_FIVE_NAME, BUTTON_FIVE_URL, BUTTON_SIX_NAME, BUTTON_SIX_URL, VIEW_LINK, \
                DRIVES_NAMES, DRIVES_IDS, INDEX_URLS, EXTENTION_FILTER
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.ext_utils.bot_utils import get_readable_file_size, setInterval
from bot.helper.ext_utils.fs_utils import get_mime_type, get_path_size
from bot.helper.ext_utils.shortenurl import short_url

LOGGER = getLogger(__name__)
getLogger('googleapiclient.discovery').setLevel(ERROR)

if USE_SERVICE_ACCOUNTS:
    SERVICE_ACCOUNT_INDEX = randrange(len(listdir("accounts")))


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
        self.__service = self.__authorize()
        self._file_uploaded_bytes = 0
        self._file_downloaded_bytes = 0
        self.uploaded_bytes = 0
        self.downloaded_bytes = 0
        self.start_time = 0
        self.total_time = 0
        self.dtotal_time = 0
        self.is_uploading = False
        self.is_downloading = False
        self.is_cloning = False
        self.is_cancelled = False
        self.is_errored = False
        self.status = None
        self.dstatus = None
        self.updater = None
        self.name = name
        self.update_interval = 3
        self.__total_bytes = 0
        self.__total_files = 0
        self.__total_folders = 0
        self.transferred_size = 0
        self.__sa_count = 0
        self.alt_auth = False

    def speed(self):
        """
        It calculates the average upload speed and returns it in bytes/seconds unit
        :return: Upload speed in bytes/second
        """
        try:
            return self.uploaded_bytes / self.total_time
        except ZeroDivisionError:
            return 0

    def dspeed(self):
        try:
            return self.downloaded_bytes / self.dtotal_time
        except ZeroDivisionError:
            return 0

    def cspeed(self):
        try:
            return self.transferred_size / int(time() - self.start_time)
        except ZeroDivisionError:
            return 0

    @staticmethod
    def __getIdFromUrl(link: str):
        if "folders" in link or "file" in link:
            regex = r"https:\/\/drive\.google\.com\/(?:drive(.*?)\/folders\/|file(.*?)?\/d\/)([-\w]+)"
            res = re_search(regex,link)
            if res is None:
                raise IndexError("G-Drive ID not found.")
            return res.group(3)
        parsed = urlparse(link)
        return parse_qs(parsed.query)['id'][0]

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, DEBUG))
    def _on_upload_progress(self):
        if self.status is not None:
            chunk_size = self.status.total_size * self.status.progress() - self._file_uploaded_bytes
            self._file_uploaded_bytes = self.status.total_size * self.status.progress()
            self.uploaded_bytes += chunk_size
            self.total_time += self.update_interval

    def deletefile(self, link: str):
        try:
            file_id = self.__getIdFromUrl(link)
        except (KeyError, IndexError):
            msg = "Google Drive ID could not be found in the provided link"
            return msg
        msg = ''
        try:
            self.__service.files().delete(fileId=file_id, supportsTeamDrives=IS_TEAM_DRIVE).execute()
            msg = "Successfully deleted"
            LOGGER.info(f"Delete Result: {msg}")
        except HttpError as err:
            if "File not found" in str(err):
                msg = "No such file exist"
            elif "insufficientFilePermissions" in str(err):
                msg = "Insufficient File Permissions"
                token_service = self.__alt_authorize()
                if token_service is not None:
                    self.__service = token_service
                    return self.deletefile(link)
            else:
                msg = str(err)
            LOGGER.error(f"Delete Result: {msg}")
        finally:
            return msg

    def __switchServiceAccount(self):
        global SERVICE_ACCOUNT_INDEX
        service_account_count = len(listdir("accounts"))
        if SERVICE_ACCOUNT_INDEX == service_account_count - 1:
            SERVICE_ACCOUNT_INDEX = 0
        self.__sa_count += 1
        SERVICE_ACCOUNT_INDEX += 1
        LOGGER.info(f"Switching to {SERVICE_ACCOUNT_INDEX}.json service account")
        self.__service = self.__authorize()

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, DEBUG))
    def __set_permission(self, drive_id):
        permissions = {
            'role': 'reader',
            'type': 'anyone',
            'value': None,
            'withLink': True
        }
        return self.__service.permissions().create(supportsTeamDrives=True, fileId=drive_id,
                                                   body=permissions).execute()

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=(retry_if_exception_type(HttpError) | retry_if_exception_type(IOError)), before=before_log(LOGGER, DEBUG))
    def __upload_file(self, file_path, file_name, mime_type, parent_id):
        # File body description
        file_metadata = {
            'name': file_name,
            'description': 'Uploaded by Mirror-leech-telegram-bot',
            'mimeType': mime_type,
        }
        if parent_id is not None:
            file_metadata['parents'] = [parent_id]

        if ospath.getsize(file_path) == 0:
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
                break
            try:
                self.status, response = drive_file.next_chunk()
            except HttpError as err:
                if err.resp.get('content-type', '').startswith('application/json'):
                    reason = jsnloads(err.content).get('error').get('errors')[0].get('reason')
                    if reason not in [
                        'userRateLimitExceeded',
                        'dailyLimitExceeded',
                    ]:
                        raise err
                    if USE_SERVICE_ACCOUNTS:
                        self.__switchServiceAccount()
                        LOGGER.info(f"Got: {reason}, Trying Again.")
                        return self.__upload_file(file_path, file_name, mime_type, parent_id)
                    else:
                        LOGGER.error(f"Got: {reason}")
                        raise err
        if self.is_cancelled:
            return
        self._file_uploaded_bytes = 0
        # Insert new permissions
        if not IS_TEAM_DRIVE:
            self.__set_permission(response['id'])
        # Define file instance and get url for download
        drive_file = self.__service.files().get(supportsTeamDrives=True, fileId=response['id']).execute()
        download_url = self.__G_DRIVE_BASE_DOWNLOAD_URL.format(drive_file.get('id'))
        return download_url

    def upload(self, file_name: str):
        self.is_downloading = False
        self.is_uploading = True
        file_dir = f"{DOWNLOAD_DIR}{self.__listener.message.message_id}"
        file_path = f"{file_dir}/{file_name}"
        size = get_readable_file_size(get_path_size(file_path))
        LOGGER.info("Uploading File: " + file_path)
        self.updater = setInterval(self.update_interval, self._on_upload_progress)
        try:
            if ospath.isfile(file_path):
                mime_type = get_mime_type(file_path)
                link = self.__upload_file(file_path, file_name, mime_type, parent_id)
                if self.is_cancelled:
                    return
                if link is None:
                    raise Exception('Upload has been manually cancelled')
                LOGGER.info("Uploaded To G-Drive: " + file_path)
            else:
                mime_type = 'Folder'
                dir_id = self.__create_directory(ospath.basename(ospath.abspath(file_name)), parent_id)
                result = self.__upload_dir(file_path, dir_id)
                if result is None:
                    raise Exception('Upload has been manually cancelled!')
                link = f"https://drive.google.com/folderview?id={dir_id}"
                if self.is_cancelled:
                    return
                LOGGER.info("Uploaded To G-Drive: " + file_name)
        except Exception as e:
            if isinstance(e, RetryError):
                LOGGER.info(f"Total Attempts: {e.last_attempt.attempt_number}")
                err = e.last_attempt.exception()
            else:
                err = e
            LOGGER.error(err)
            self.__listener.onUploadError(str(err))
            self.is_errored = True
        finally:
            self.updater.cancel()
            if self.is_cancelled and not self.is_errored:
                if mime_type == 'Folder':
                    LOGGER.info("Deleting uploaded data from Drive...")
                    link = f"https://drive.google.com/folderview?id={dir_id}"
                    self.deletefile(link)
                return
            elif self.is_errored:
                return
        self.__listener.onUploadComplete(link, size, self.__total_files, self.__total_folders, mime_type, self.name)

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, DEBUG))
    def __copyFile(self, file_id, dest_id):
        body = {
            'parents': [dest_id]
        }

        try:
            return (
                self.__service.files()
                .copy(supportsAllDrives=True, fileId=file_id, body=body)
                .execute()
            )

        except HttpError as err:
            if err.resp.get('content-type', '').startswith('application/json'):
                reason = jsnloads(err.content).get('error').get('errors')[0].get('reason')
                if reason in ['userRateLimitExceeded', 'dailyLimitExceeded']:
                    if USE_SERVICE_ACCOUNTS:
                        if self.__sa_count == len(listdir("accounts")) or self.__sa_count > 50:
                            self.is_cancelled = True
                            raise err
                        else:
                            self.__switchServiceAccount()
                            return self.__copyFile(file_id, dest_id)
                    else:
                        self.is_cancelled = True
                        LOGGER.error(f"Got: {reason}")
                        raise err
                else:
                    raise err


    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, DEBUG))
    def __getFileMetadata(self, file_id):
        return self.__service.files().get(supportsAllDrives=True, fileId=file_id,
                                              fields="name,id,mimeType,size").execute()

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, DEBUG))
    def __getFilesByFolderId(self, folder_id):
        page_token = None
        files = []
        while True:
            response = self.__service.files().list(supportsTeamDrives=True,
                                                   includeTeamDriveItems=True,
                                                   q=f"'{folder_id}' in parents and trashed = false",
                                                   spaces='drive',
                                                   pageSize=200,
                                                   fields='nextPageToken, files(id, name, mimeType, size, shortcutDetails)',
                                                   orderBy='folder, name',
                                                   pageToken=page_token).execute()
            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken')
            if page_token is None:
                break
        return files

    def clone(self, link):
        self.is_cloning = True
        self.start_time = time()
        self.__total_files = 0
        self.__total_folders = 0
        try:
            file_id = self.__getIdFromUrl(link)
        except (KeyError, IndexError):
            msg = "Google Drive ID could not be found in the provided link"
            return msg
        msg = ""
        LOGGER.info(f"File ID: {file_id}")
        try:
            meta = self.__getFileMetadata(file_id)
            mime_type = meta.get("mimeType")
            if mime_type == self.__G_DRIVE_DIR_MIME_TYPE:
                dir_id = self.__create_directory(meta.get('name'), parent_id)
                self.__cloneFolder(meta.get('name'), meta.get('name'), meta.get('id'), dir_id)
                durl = self.__G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(dir_id)
                if self.is_cancelled:
                    LOGGER.info("Deleting cloned data from Drive...")
                    self.deletefile(durl)
                    return "your clone has been stopped and cloned data has been deleted!", "cancelled"
                msg += f'<b>Name: </b><code>{meta.get("name")}</code>'
                msg += f'\n\n<b>Size: </b>{get_readable_file_size(self.transferred_size)}'
                msg += '\n\n<b>Type: </b>Folder'
                msg += f'\n<b>SubFolders: </b>{self.__total_folders}'
                msg += f'\n<b>Files: </b>{self.__total_files}'
                buttons = ButtonMaker()
                durl = short_url(durl)
                buttons.buildbutton("☁️ Drive Link", durl)
                if INDEX_URL is not None:
                    url_path = rquote(f'{meta.get("name")}', safe='')
                    url = f'{INDEX_URL}/{url_path}/'
                    url = short_url(url)
                    buttons.buildbutton("⚡ Index Link", url)
            else:
                file = self.__copyFile(meta.get('id'), parent_id)
                msg += f'<b>Name: </b><code>{file.get("name")}</code>'
                durl = self.__G_DRIVE_BASE_DOWNLOAD_URL.format(file.get("id"))
                buttons = ButtonMaker()
                durl = short_url(durl)
                buttons.buildbutton("☁️ Drive Link", durl)
                if mime_type is None:
                    mime_type = 'File'
                msg += f'\n\n<b>Size: </b>{get_readable_file_size(int(meta.get("size", 0)))}'
                msg += f'\n\n<b>Type: </b>{mime_type}'
                if INDEX_URL is not None:
                    url_path = rquote(f'{file.get("name")}', safe='')
                    url = f'{INDEX_URL}/{url_path}'
                    url = short_url(url)
                    buttons.buildbutton("⚡ Index Link", url)
                    if VIEW_LINK:
                        urls = f'{INDEX_URL}/{url_path}?a=view'
                        urls = short_url(urls)
                        buttons.buildbutton("🌐 View Link", urls)
            if BUTTON_FOUR_NAME is not None and BUTTON_FOUR_URL is not None:
                buttons.buildbutton(f"{BUTTON_FOUR_NAME}", f"{BUTTON_FOUR_URL}")
            if BUTTON_FIVE_NAME is not None and BUTTON_FIVE_URL is not None:
                buttons.buildbutton(f"{BUTTON_FIVE_NAME}", f"{BUTTON_FIVE_URL}")
            if BUTTON_SIX_NAME is not None and BUTTON_SIX_URL is not None:
                buttons.buildbutton(f"{BUTTON_SIX_NAME}", f"{BUTTON_SIX_URL}")
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace('>', '').replace('<', '')
            LOGGER.error(err)
            if "User rate limit exceeded" in str(err):
                msg = "User rate limit exceeded."
            elif "File not found" in str(err):
                token_service = self.__alt_authorize()
                if token_service is not None:
                    self.__service = token_service
                    return self.clone(link)
                msg = "File not found."
            else:
                msg = f"Error.\n{err}"
            return msg, ""
        return msg, InlineKeyboardMarkup(buttons.build_menu(2))

    def __cloneFolder(self, name, local_path, folder_id, parent_id):
        LOGGER.info(f"Syncing: {local_path}")
        files = self.__getFilesByFolderId(folder_id)
        if len(files) == 0:
            return parent_id
        for file in files:
            if file.get('mimeType') == self.__G_DRIVE_DIR_MIME_TYPE:
                self.__total_folders += 1
                file_path = ospath.join(local_path, file.get('name'))
                current_dir_id = self.__create_directory(file.get('name'), parent_id)
                self.__cloneFolder(file.get('name'), file_path, file.get('id'), current_dir_id)
            elif not file.get('name').lower().endswith(tuple(EXTENTION_FILTER)):
                self.__total_files += 1
                self.transferred_size += int(file.get('size', 0))
                self.__copyFile(file.get('id'), parent_id)
            if self.is_cancelled:
                break

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, DEBUG))
    def __create_directory(self, directory_name, parent_id):
        file_metadata = {
            "name": directory_name,
            "description": "Uploaded by Mirror-leech-telegram-bot",
            "mimeType": self.__G_DRIVE_DIR_MIME_TYPE
        }
        if parent_id is not None:
            file_metadata["parents"] = [parent_id]
        file = self.__service.files().create(supportsTeamDrives=True, body=file_metadata).execute()
        file_id = file.get("id")
        if not IS_TEAM_DRIVE:
            self.__set_permission(file_id)
        LOGGER.info("Created G-Drive Folder:\nName: {}\nID: {} ".format(file.get("name"), file_id))
        return file_id

    def __upload_dir(self, input_directory, parent_id):
        list_dirs = listdir(input_directory)
        if len(list_dirs) == 0:
            return parent_id
        new_id = None
        for item in list_dirs:
            current_file_name = ospath.join(input_directory, item)
            if ospath.isdir(current_file_name):
                current_dir_id = self.__create_directory(item, parent_id)
                new_id = self.__upload_dir(current_file_name, current_dir_id)
                self.__total_folders += 1
            elif not item.lower().endswith(tuple(EXTENTION_FILTER)):
                mime_type = get_mime_type(current_file_name)
                file_name = current_file_name.split("/")[-1]
                # current_file_name will have the full path
                self.__upload_file(current_file_name, file_name, mime_type, parent_id)
                self.__total_files += 1
                new_id = parent_id
            if self.is_cancelled:
                break
        return new_id

    def __authorize(self):
        # Get credentials
        credentials = None
        if not USE_SERVICE_ACCOUNTS:
            if ospath.exists(self.__G_DRIVE_TOKEN_FILE):
                with open(self.__G_DRIVE_TOKEN_FILE, 'rb') as f:
                    credentials = pload(f)
            else:
                LOGGER.error('token.pickle not found!')
        else:
            LOGGER.info(f"Authorizing with {SERVICE_ACCOUNT_INDEX}.json service account")
            credentials = service_account.Credentials.from_service_account_file(
                f'accounts/{SERVICE_ACCOUNT_INDEX}.json',
                scopes=self.__OAUTH_SCOPE)
        return build('drive', 'v3', credentials=credentials, cache_discovery=False)

    def __alt_authorize(self):
        credentials = None
        if USE_SERVICE_ACCOUNTS and not self.alt_auth:
            self.alt_auth = True
            if ospath.exists(self.__G_DRIVE_TOKEN_FILE):
                LOGGER.info("Authorize with token.pickle")
                with open(self.__G_DRIVE_TOKEN_FILE, 'rb') as f:
                    credentials = pload(f)
                return build('drive', 'v3', credentials=credentials, cache_discovery=False)
        return None

    def __escapes(self, str):
        chars = ['\\', "'", '"', r'\a', r'\b', r'\f', r'\n', r'\r', r'\t']
        for char in chars:
            str = str.replace(char, '\\' + char)
        return str.strip()

    def __get_recursive_list(self, file, rootid = "root"):
        rtnlist = []
        if not rootid:
            rootid = file.get('teamDriveId')
        if rootid == "root":
            rootid = self.__service.files().get(fileId = 'root', fields="id").execute().get('id')
        x = file.get("name")
        y = file.get("id")
        while(y != rootid):
            rtnlist.append(x)
            file = self.__service.files().get(
                                            fileId=file.get("parents")[0],
                                            supportsAllDrives=True,
                                            fields='id, name, parents'
                                            ).execute()
            x = file.get("name")
            y = file.get("id")
        rtnlist.reverse()
        return rtnlist

    def __drive_query(self, parent_id, fileName, stopDup, isRecursive, itemType):
        try:
            if isRecursive:
                if stopDup:
                    query = f"name = '{fileName}' and "
                else:
                    fileName = fileName.split(' ')
                    query = "".join(
                        f"name contains '{name}' and "
                        for name in fileName
                        if name != ''
                    )
                    if itemType == "files":
                        query += "mimeType != 'application/vnd.google-apps.folder' and "
                    elif itemType == "folders":
                        query += "mimeType = 'application/vnd.google-apps.folder' and "
                query += "trashed = false"
                if parent_id == "root":
                    return (
                        self.__service.files()
                        .list(q=query + " and 'me' in owners",
                            pageSize=200,
                            spaces='drive',
                            fields='files(id, name, mimeType, size, parents)',
                            orderBy='folder, name asc'
                        )
                        .execute()
                    )
                else:
                    return (
                        self.__service.files()
                        .list(supportsTeamDrives=True,
                            includeTeamDriveItems=True,
                            teamDriveId=parent_id,
                            q=query,
                            corpora='drive',
                            spaces='drive',
                            pageSize=200,
                            fields='files(id, name, mimeType, size, teamDriveId, parents)',
                            orderBy='folder, name asc'
                        )
                        .execute()
                    )
            else:
                if stopDup:
                    query = f"'{parent_id}' in parents and name = '{fileName}' and "
                else:
                    query = f"'{parent_id}' in parents and "
                    fileName = fileName.split(' ')
                    for name in fileName:
                        if name != '':
                            query += f"name contains '{name}' and "
                    if itemType == "files":
                        query += "mimeType != 'application/vnd.google-apps.folder' and "
                    elif itemType == "folders":
                        query += "mimeType = 'application/vnd.google-apps.folder' and "
                query += "trashed = false"
                return (
                    self.__service.files()
                    .list(
                        supportsTeamDrives=True,
                        includeTeamDriveItems=True,
                        q=query,
                        spaces='drive',
                        pageSize=200,
                        fields='files(id, name, mimeType, size)',
                        orderBy='folder, name asc',
                    )
                    .execute()
                )
        except Exception as err:
            err = str(err).replace('>', '').replace('<', '')
            LOGGER.error(err)
            return {'files': []}

    def drive_list(self, fileName, stopDup=False, noMulti=False, isRecursive=True, itemType=""):
        msg = ""
        fileName = self.__escapes(str(fileName))
        contents_count = 0
        telegraph_content = []
        path = []
        Title = False
        if len(DRIVES_IDS) > 1:
            token_service = self.__alt_authorize()
            if token_service is not None:
                self.__service = token_service
        for index, parent_id in enumerate(DRIVES_IDS):
            if isRecursive and len(parent_id) > 23:
                isRecur = False
            else:
                isRecur = isRecursive
            response = self.__drive_query(parent_id, fileName, stopDup, isRecur, itemType)
            if not response["files"] and noMulti:
                break
            elif not response["files"]:
                continue
            if not Title:
                msg += f'<h4>Search Result For {fileName}</h4>'
                Title = True
            if len(DRIVES_NAMES) > 1 and DRIVES_NAMES[index] is not None:
                msg += f"╾────────────╼<br><b>{DRIVES_NAMES[index]}</b><br>╾────────────╼<br>"
            for file in response.get('files', []):
                mime_type = file.get('mimeType')
                if mime_type == "application/vnd.google-apps.folder":
                    furl = f"https://drive.google.com/drive/folders/{file.get('id')}"
                    msg += f"📁 <code>{file.get('name')}<br>(folder)</code><br>"
                    furl = short_url(furl)
                    msg += f"<b><a href={furl}>Drive Link</a></b>"
                    if INDEX_URLS[index] is not None:
                        if isRecur:
                            url_path = "/".join([rquote(n, safe='') for n in self.__get_recursive_list(file, parent_id)])
                        else:
                            url_path = rquote(f'{file.get("name")}', safe='')
                        url = f'{INDEX_URLS[index]}/{url_path}/'
                        url = short_url(url)
                        msg += f' <b>| <a href="{url}">Index Link</a></b>'
                elif mime_type == 'application/vnd.google-apps.shortcut':
                    msg += f"⁍<a href='https://drive.google.com/drive/folders/{file.get('id')}'>{file.get('name')}" \
                        f"</a> (shortcut)"
                    # Excluded index link as indexes cant download or open these shortcuts
                else:
                    furl = f"https://drive.google.com/uc?id={file.get('id')}&export=download"
                    msg += f"📄 <code>{file.get('name')}<br>({get_readable_file_size(int(file.get('size', 0)))})</code><br>"
                    furl = short_url(furl)
                    msg += f"<b><a href={furl}>Drive Link</a></b>"
                    if INDEX_URLS[index] is not None:
                        if isRecur:
                            url_path = "/".join(
                                rquote(n, safe='')
                                for n in self.__get_recursive_list(file, parent_id)
                            )

                        else:
                            url_path = rquote(f'{file.get("name")}')
                        url = f'{INDEX_URLS[index]}/{url_path}'
                        url = short_url(url)
                        msg += f' <b>| <a href="{url}">Index Link</a></b>'
                        if VIEW_LINK:
                            urls = f'{INDEX_URLS[index]}/{url_path}?a=view'
                            urls = short_url(urls)
                            msg += f' <b>| <a href="{urls}">View Link</a></b>'
                msg += '<br><br>'
                contents_count += 1
                if len(msg.encode('utf-8')) > 39000:
                    telegraph_content.append(msg)
                    msg = ""
            if noMulti:
                break

        if msg != '':
            telegraph_content.append(msg)

        if len(telegraph_content) == 0:
            return "", None

        for content in telegraph_content:
            path.append(
                telegraph.create_page(
                    title='Mirror-Leech-Bot Drive Search',
                    content=content
                )["path"]
            )
        if len(path) > 1:
            telegraph.edit_telegraph(path, telegraph_content)

        msg = f"<b>Found {contents_count} result for <i>{fileName}</i></b>"
        buttons = ButtonMaker()
        buttons.buildbutton("🔎 VIEW", f"https://telegra.ph/{path[0]}")

        return msg, InlineKeyboardMarkup(buttons.build_menu(1))

    def count(self, link):
        try:
            file_id = self.__getIdFromUrl(link)
        except (KeyError, IndexError):
            msg = "Google Drive ID could not be found in the provided link"
            return msg
        msg = ""
        LOGGER.info(f"File ID: {file_id}")
        try:
            meta = self.__getFileMetadata(file_id)
            name = meta['name']
            LOGGER.info(f"Counting: {name}")
            mime_type = meta.get('mimeType')
            if mime_type == self.__G_DRIVE_DIR_MIME_TYPE:
                self.__gDrive_directory(meta)
                msg += f'<b>Name: </b><code>{name}</code>'
                msg += f'\n\n<b>Size: </b>{get_readable_file_size(self.__total_bytes)}'
                msg += '\n\n<b>Type: </b>Folder'
                msg += f'\n<b>SubFolders: </b>{self.__total_folders}'
            else:
                msg += f'<b>Name: </b><code>{name}</code>'
                if mime_type is None:
                    mime_type = 'File'
                self.__total_files += 1
                self.__gDrive_file(meta)
                msg += f'\n\n<b>Size: </b>{get_readable_file_size(self.__total_bytes)}'
                msg += f'\n\n<b>Type: </b>{mime_type}'
            msg += f'\n<b>Files: </b>{self.__total_files}'
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace('>', '').replace('<', '')
            LOGGER.error(err)
            if "File not found" in str(err):
                token_service = self.__alt_authorize()
                if token_service is not None:
                    self.__service = token_service
                    return self.count(link)
                msg = "File not found."
            else:
                msg = f"Error.\n{err}"
        return msg

    def __gDrive_file(self, filee):
        size = int(filee.get('size', 0))
        self.__total_bytes += size

    def __gDrive_directory(self, drive_folder):
        files = self.__getFilesByFolderId(drive_folder['id'])
        if len(files) == 0:
            return
        for filee in files:
            shortcut_details = filee.get('shortcutDetails')
            if shortcut_details is not None:
                mime_type = shortcut_details['targetMimeType']
                file_id = shortcut_details['targetId']
                filee = self.__getFileMetadata(file_id)
            else:
                mime_type = filee.get('mimeType')
            if mime_type == self.__G_DRIVE_DIR_MIME_TYPE:
                self.__total_folders += 1
                self.__gDrive_directory(filee)
            else:
                self.__total_files += 1
                self.__gDrive_file(filee)

    def helper(self, link):
        try:
            file_id = self.__getIdFromUrl(link)
        except (KeyError, IndexError):
            msg = "Google Drive ID could not be found in the provided link"
            return msg, "", "", ""
        LOGGER.info(f"File ID: {file_id}")
        try:
            meta = self.__getFileMetadata(file_id)
            name = meta['name']
            LOGGER.info(f"Checking size, this might take a minute: {name}")
            if meta.get('mimeType') == self.__G_DRIVE_DIR_MIME_TYPE:
                self.__gDrive_directory(meta)
            else:
                self.__total_files += 1
                self.__gDrive_file(meta)
            size = self.__total_bytes
            files = self.__total_files
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace('>', '').replace('<', '')
            LOGGER.error(err)
            if "File not found" in str(err):
                token_service = self.__alt_authorize()
                if token_service is not None:
                    self.__service = token_service
                    return self.helper(link)
                msg = "File not found."
            else:
                msg = f"Error.\n{err}"
            return msg, "", "", ""
        return "", size, name, files

    def download(self, link):
        self.is_downloading = True
        file_id = self.__getIdFromUrl(link)
        self.updater = setInterval(self.update_interval, self._on_download_progress)
        try:
            meta = self.__getFileMetadata(file_id)
            path = f"{DOWNLOAD_DIR}{self.__listener.uid}/"
            if meta.get("mimeType") == self.__G_DRIVE_DIR_MIME_TYPE:
                self.__download_folder(file_id, path, meta.get('name'))
            else:
                makedirs(path)
                self.__download_file(file_id, path, meta.get('name'), meta.get('mimeType'))
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace('>', '').replace('<', '')
            LOGGER.error(err)
            if "downloadQuotaExceeded" in str(err):
                err = "Download Quota Exceeded."
            elif "File not found" in str(err):
                token_service = self.__alt_authorize()
                if token_service is not None:
                    self.__service = token_service
                    self.updater.cancel()
                    return self.download(link)
            self.__listener.onDownloadError(err)
            self.is_cancelled = True
        finally:
            self.updater.cancel()
            if self.is_cancelled:
                return
        self.__listener.onDownloadComplete()

    def __download_folder(self, folder_id, path, folder_name):
        folder_name = folder_name.replace('/', '')
        if not ospath.exists(path + folder_name):
            makedirs(path + folder_name)
        path += folder_name + '/'
        result = self.__getFilesByFolderId(folder_id)
        if len(result) == 0:
            return
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
            if mime_type == self.__G_DRIVE_DIR_MIME_TYPE:
                self.__download_folder(file_id, path, filename)
            elif not ospath.isfile(path + filename) and not filename.lower().endswith(tuple(EXTENTION_FILTER)):
                self.__download_file(file_id, path, filename, mime_type)
            if self.is_cancelled:
                break

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=(retry_if_exception_type(HttpError) | retry_if_exception_type(IOError)), before=before_log(LOGGER, DEBUG))
    def __download_file(self, file_id, path, filename, mime_type):
        request = self.__service.files().get_media(fileId=file_id)
        filename = filename.replace('/', '')
        fh = FileIO('{}{}'.format(path, filename), 'wb')
        downloader = MediaIoBaseDownload(fh, request, chunksize=50 * 1024 * 1024)
        done = False
        while not done:
            if self.is_cancelled:
                fh.close()
                break
            try:
                self.dstatus, done = downloader.next_chunk()
            except HttpError as err:
                if err.resp.get('content-type', '').startswith('application/json'):
                    reason = jsnloads(err.content).get('error').get('errors')[0].get('reason')
                    if reason not in [
                        'downloadQuotaExceeded',
                        'dailyLimitExceeded',
                    ]:
                        raise err
                    if USE_SERVICE_ACCOUNTS:
                        if self.__sa_count == len(listdir("accounts")) or self.__sa_count > 50:
                            self.is_cancelled = True
                            raise err
                        else:
                            self.__switchServiceAccount()
                            LOGGER.info(f"Got: {reason}, Trying Again...")
                            return self.__download_file(file_id, path, filename, mime_type)
                    else:
                        LOGGER.error(f"Got: {reason}")
                        raise err
        self._file_downloaded_bytes = 0

    @retry(wait=wait_exponential(multiplier=2, min=3, max=6), stop=stop_after_attempt(3),
           retry=retry_if_exception_type(HttpError), before=before_log(LOGGER, DEBUG))
    def _on_download_progress(self):
        if self.dstatus is not None:
            chunk_size = self.dstatus.total_size * self.dstatus.progress() - self._file_downloaded_bytes
            self._file_downloaded_bytes = self.dstatus.total_size * self.dstatus.progress()
            self.downloaded_bytes += chunk_size
            self.dtotal_time += self.update_interval

    def cancel_download(self):
        self.is_cancelled = True
        if self.is_downloading:
            LOGGER.info(f"Cancelling Download: {self.name}")
            self.__listener.onDownloadError('Download stopped by user!')
        elif self.is_cloning:
            LOGGER.info(f"Cancelling Clone: {self.name}")
        elif self.is_uploading:
            LOGGER.info(f"Cancelling Upload: {self.name}")
            self.__listener.onUploadError('your upload has been stopped and uploaded data has been deleted!')
