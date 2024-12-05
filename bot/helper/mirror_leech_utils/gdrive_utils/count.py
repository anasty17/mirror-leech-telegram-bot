from logging import getLogger
from tenacity import RetryError

from ...mirror_leech_utils.gdrive_utils.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)


class GoogleDriveCount(GoogleDriveHelper):
    def __init__(self):
        super().__init__()

    def count(self, link, user_id):
        try:
            file_id = self.get_id_from_url(link, user_id)
        except (KeyError, IndexError):
            return (
                "Google Drive ID could not be found in the provided link",
                None,
                None,
                None,
                None,
            )
        self.service = self.authorize()
        LOGGER.info(f"File ID: {file_id}")
        try:
            return self._proceed_count(file_id)
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace(">", "").replace("<", "")
            if "File not found" in err:
                if not self.alt_auth and self.use_sa:
                    self.alt_auth = True
                    self.use_sa = False
                    LOGGER.error("File not found. Trying with token.pickle...")
                    return self.count(link, user_id)
                msg = "File not found."
            else:
                msg = f"Error.\n{err}"
        return msg, None, None, None, None

    def _proceed_count(self, file_id):
        meta = self.get_file_metadata(file_id)
        name = meta["name"]
        LOGGER.info(f"Counting: {name}")
        mime_type = meta.get("mimeType")
        if mime_type == self.G_DRIVE_DIR_MIME_TYPE:
            self._gdrive_directory(meta)
            mime_type = "Folder"
        else:
            if mime_type is None:
                mime_type = "File"
            self.total_files += 1
            self._gdrive_file(meta)
        return name, mime_type, self.proc_bytes, self.total_files, self.total_folders

    def _gdrive_file(self, filee):
        size = int(filee.get("size", 0))
        self.proc_bytes += size

    def _gdrive_directory(self, drive_folder):
        files = self.get_files_by_folder_id(drive_folder["id"])
        if len(files) == 0:
            return
        for filee in files:
            shortcut_details = filee.get("shortcutDetails")
            if shortcut_details is not None:
                mime_type = shortcut_details["targetMimeType"]
                file_id = shortcut_details["targetId"]
                filee = self.get_file_metadata(file_id)
            else:
                mime_type = filee.get("mimeType")
            if mime_type == self.G_DRIVE_DIR_MIME_TYPE:
                self.total_folders += 1
                self._gdrive_directory(filee)
            else:
                self.total_files += 1
                self._gdrive_file(filee)
