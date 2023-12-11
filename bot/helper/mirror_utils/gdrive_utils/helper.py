from logging import getLogger, ERROR
from pickle import load as pload
from os import path as ospath, listdir
from re import search as re_search
from urllib.parse import parse_qs, urlparse
from random import randrange
from google.oauth2 import service_account
from googleapiclient.discovery import build
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from bot import config_dict
from bot.helper.ext_utils.links_utils import is_gdrive_id

LOGGER = getLogger(__name__)
getLogger("googleapiclient.discovery").setLevel(ERROR)


class GoogleDriveHelper:
    def __init__(self):
        self._OAUTH_SCOPE = ["https://www.googleapis.com/auth/drive"]
        self.token_path = "token.pickle"
        self.G_DRIVE_DIR_MIME_TYPE = "application/vnd.google-apps.folder"
        self.G_DRIVE_BASE_DOWNLOAD_URL = (
            "https://drive.google.com/uc?id={}&export=download"
        )
        self.G_DRIVE_DIR_BASE_DOWNLOAD_URL = "https://drive.google.com/drive/folders/{}"
        self.is_uploading = False
        self.is_downloading = False
        self.is_cloning = False
        self.is_cancelled = False
        self.sa_index = 0
        self.sa_count = 1
        self.sa_number = 100
        self.alt_auth = False
        self.service = None
        self.total_files = 0
        self.total_folders = 0
        self.file_processed_bytes = 0
        self.proc_bytes = 0
        self.total_time = 0
        self.status = None
        self.update_interval = 3
        self.use_sa = config_dict["USE_SERVICE_ACCOUNTS"]

    @property
    def speed(self):
        try:
            return self.proc_bytes / self.total_time
        except:
            return 0

    @property
    def processed_bytes(self):
        return self.proc_bytes

    async def progress(self):
        if self.status is not None:
            chunk_size = (
                self.status.total_size * self.status.progress()
                - self.file_processed_bytes
            )
            self.file_processed_bytes = self.status.total_size * self.status.progress()
            self.proc_bytes += chunk_size
            self.total_time += self.update_interval

    def authorize(self):
        credentials = None
        if self.use_sa:
            json_files = listdir("accounts")
            self.sa_number = len(json_files)
            self.sa_index = randrange(self.sa_number)
            LOGGER.info(f"Authorizing with {json_files[self.sa_index]} service account")
            credentials = service_account.Credentials.from_service_account_file(
                f"accounts/{json_files[self.sa_index]}", scopes=self._OAUTH_SCOPE
            )
        elif ospath.exists(self.token_path):
            LOGGER.info(f"Authorize with {self.token_path}")
            with open(self.token_path, "rb") as f:
                credentials = pload(f)
        else:
            LOGGER.error("token.pickle not found!")
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    def switchServiceAccount(self):
        if self.sa_index == self.sa_number - 1:
            self.sa_index = 0
        else:
            self.sa_index += 1
        self.sa_count += 1
        LOGGER.info(f"Switching to {self.sa_index} index")
        self.service = self.authorize()

    def getIdFromUrl(self, link, user_id=""):
        if user_id and link.startswith("mtp:"):
            self.use_sa = False
            self.token_path = f"tokens/{user_id}.pickle"
        elif link.startswith("sa:"):
            self.use_sa = True
        elif link.startswith("tp:"):
            self.use_sa = False
        link = link.lstrip("mtp:").lstrip("sa:").lstrip("tp:")
        if is_gdrive_id(link):
            return link
        if "folders" in link or "file" in link:
            regex = r"https:\/\/drive\.google\.com\/(?:drive(.*?)\/folders\/|file(.*?)?\/d\/)([-\w]+)"
            res = re_search(regex, link)
            if res is None:
                raise IndexError("G-Drive ID not found.")
            return res.group(3)
        parsed = urlparse(link)
        return parse_qs(parsed.query)["id"][0]

    @retry(
        wait=wait_exponential(multiplier=2, min=3, max=6),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
    )
    def set_permission(self, file_id):
        permissions = {
            "role": "reader",
            "type": "anyone",
            "value": None,
            "withLink": True,
        }
        return (
            self.service.permissions()
            .create(fileId=file_id, body=permissions, supportsAllDrives=True)
            .execute()
        )

    @retry(
        wait=wait_exponential(multiplier=2, min=3, max=6),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
    )
    def getFileMetadata(self, file_id):
        return (
            self.service.files()
            .get(
                fileId=file_id,
                supportsAllDrives=True,
                fields="name, id, mimeType, size",
            )
            .execute()
        )

    @retry(
        wait=wait_exponential(multiplier=2, min=3, max=6),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
    )
    def getFilesByFolderId(self, folder_id, item_type=""):
        page_token = None
        files = []
        if not item_type:
            q = f"'{folder_id}' in parents and trashed = false"
        elif item_type == "folders":
            q = f"'{folder_id}' in parents and mimeType = '{self.G_DRIVE_DIR_MIME_TYPE}' and trashed = false"
        else:
            q = f"'{folder_id}' in parents and mimeType != '{self.G_DRIVE_DIR_MIME_TYPE}' and trashed = false"
        while True:
            response = (
                self.service.files()
                .list(
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    q=q,
                    spaces="drive",
                    pageSize=200,
                    fields="nextPageToken, files(id, name, mimeType, size, shortcutDetails)",
                    orderBy="folder, name",
                    pageToken=page_token,
                )
                .execute()
            )
            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if page_token is None:
                break
        return files

    @retry(
        wait=wait_exponential(multiplier=2, min=3, max=6),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
    )
    def create_directory(self, directory_name, dest_id):
        file_metadata = {
            "name": directory_name,
            "description": "Uploaded by Mirror-leech-telegram-bot",
            "mimeType": self.G_DRIVE_DIR_MIME_TYPE,
        }
        if dest_id is not None:
            file_metadata["parents"] = [dest_id]
        file = (
            self.service.files()
            .create(body=file_metadata, supportsAllDrives=True)
            .execute()
        )
        file_id = file.get("id")
        if not config_dict["IS_TEAM_DRIVE"]:
            self.set_permission(file_id)
        LOGGER.info(f'Created G-Drive Folder:\nName: {file.get("name")}\nID: {file_id}')
        return file_id

    def escapes(self, estr):
        chars = ["\\", "'", '"', r"\a", r"\b", r"\f", r"\n", r"\r", r"\t"]
        for char in chars:
            estr = estr.replace(char, f"\\{char}")
        return estr.strip()

    """
    def get_recursive_list(self, file, rootId):
        rtnlist = []
        if not rootId:
            rootId = file.get('teamDriveId')
        if rootId == "root":
            rootId = self.service.files().get(
                fileId='root', fields='id').execute().get('id')
        x = file.get("name")
        y = file.get("id")
        while (y != rootId):
            rtnlist.append(x)
            file = self.service.files().get(fileId=file.get("parents")[0], supportsAllDrives=True,
                                            fields='id, name, parents').execute()
            x = file.get("name")
            y = file.get("id")
        rtnlist.reverse()
        return rtnlist
    """

    async def cancel_task(self):
        self.is_cancelled = True
        if self.is_downloading:
            LOGGER.info(f"Cancelling Download: {self.listener.name}")
            await self.listener.onDownloadError("Download stopped by user!")
        elif self.is_cloning:
            LOGGER.info(f"Cancelling Clone: {self.listener.name}")
            await self.listener.onUploadError(
                "your clone has been stopped and cloned data has been deleted!"
            )
        elif self.is_uploading:
            LOGGER.info(f"Cancelling Upload: {self.listener.name}")
            await self.listener.onUploadError(
                "your upload has been stopped and uploaded data has been deleted!"
            )
