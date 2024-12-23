from googleapiclient.errors import HttpError
from logging import getLogger

from ....helper.mirror_leech_utils.gdrive_utils.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)


class GoogleDriveDelete(GoogleDriveHelper):
    def __init__(self):
        super().__init__()

    def deletefile(self, link, user_id):
        try:
            file_id = self.get_id_from_url(link, user_id)
        except (KeyError, IndexError):
            return "Google Drive ID could not be found in the provided link"
        self.service = self.authorize()
        msg = ""
        try:
            self.service.files().delete(
                fileId=file_id, supportsAllDrives=True
            ).execute()
            msg = "Successfully deleted"
            LOGGER.info(f"Delete Result: {msg}")
        except HttpError as err:
            if "File not found" in str(err) or "insufficientFilePermissions" in str(
                err
            ):
                if not self.alt_auth and self.use_sa:
                    self.alt_auth = True
                    self.use_sa = False
                    LOGGER.error("File not found. Trying with token.pickle...")
                    return self.deletefile(link, user_id)
                err = "File not found or insufficientFilePermissions!"
            LOGGER.error(f"Delete Result: {err}")
            msg = str(err)
        return msg
