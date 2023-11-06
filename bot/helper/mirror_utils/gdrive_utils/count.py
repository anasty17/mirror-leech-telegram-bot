from logging import getLogger
from tenacity import RetryError

from bot.helper.mirror_utils.gdrive_utils.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)


class gdCount(GoogleDriveHelper):
    def __init__(self):
        super().__init__()

    def count(self, link, user_id):
        try:
            file_id = self.getIdFromUrl(link, user_id)
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
        meta = self.getFileMetadata(file_id)
        name = meta["name"]
        LOGGER.info(f"Counting: {name}")
        mime_type = meta.get("mimeType")
        if mime_type == self.G_DRIVE_DIR_MIME_TYPE:
            self._gDrive_directory(meta)
            mime_type = "Folder"
        else:
            if mime_type is None:
                mime_type = "File"
            self.total_files += 1
            self._gDrive_file(meta)
        return name, mime_type, self.proc_bytes, self.total_files, self.total_folders

    def _gDrive_file(self, filee):
        size = int(filee.get("size", 0))
        self.proc_bytes += size

    def _gDrive_directory(self, drive_folder):
        files = self.getFilesByFolderId(drive_folder["id"])
        if len(files) == 0:
            return
        for filee in files:
            shortcut_details = filee.get("shortcutDetails")
            if shortcut_details is not None:
                mime_type = shortcut_details["targetMimeType"]
                file_id = shortcut_details["targetId"]
                filee = self.getFileMetadata(file_id)
            else:
                mime_type = filee.get("mimeType")
            if mime_type == self.G_DRIVE_DIR_MIME_TYPE:
                self.total_folders += 1
                self._gDrive_directory(filee)
            else:
                self.total_files += 1
                self._gDrive_file(filee)
