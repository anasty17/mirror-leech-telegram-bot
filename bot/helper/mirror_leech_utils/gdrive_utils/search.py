from logging import getLogger

from .... import drives_names, drives_ids, index_urls, user_data
from ....helper.ext_utils.status_utils import get_readable_file_size
from ....helper.mirror_leech_utils.gdrive_utils.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)


class GoogleDriveSearch(GoogleDriveHelper):

    def __init__(self, stop_dup=False, no_multi=False, is_recursive=True, item_type=""):
        super().__init__()
        self._stop_dup = stop_dup
        self._no_multi = no_multi
        self._is_recursive = is_recursive
        self._item_type = item_type

    def _drive_query(self, dir_id, file_name, is_recursive):
        try:
            if is_recursive:
                if self._stop_dup:
                    query = f"name = '{file_name}' and "
                else:
                    file_name = file_name.split()
                    query = "".join(
                        f"name contains '{name}' and "
                        for name in file_name
                        if name != ""
                    )
                    if self._item_type == "files":
                        query += f"mimeType != '{self.G_DRIVE_DIR_MIME_TYPE}' and "
                    elif self._item_type == "folders":
                        query += f"mimeType = '{self.G_DRIVE_DIR_MIME_TYPE}' and "
                query += "trashed = false"
                if dir_id == "root":
                    return (
                        self.service.files()
                        .list(
                            q=f"{query} and 'me' in owners",
                            pageSize=200,
                            spaces="drive",
                            fields="files(id, name, mimeType, size, parents)",
                            orderBy="folder, name asc",
                        )
                        .execute()
                    )
                else:
                    return (
                        self.service.files()
                        .list(
                            supportsAllDrives=True,
                            includeItemsFromAllDrives=True,
                            driveId=dir_id,
                            q=query,
                            spaces="drive",
                            pageSize=150,
                            fields="files(id, name, mimeType, size, teamDriveId, parents)",
                            corpora="drive",
                            orderBy="folder, name asc",
                        )
                        .execute()
                    )
            else:
                if self._stop_dup:
                    query = f"'{dir_id}' in parents and name = '{file_name}' and "
                else:
                    query = f"'{dir_id}' in parents and "
                    file_name = file_name.split()
                    for name in file_name:
                        if name != "":
                            query += f"name contains '{name}' and "
                    if self._item_type == "files":
                        query += f"mimeType != '{self.G_DRIVE_DIR_MIME_TYPE}' and "
                    elif self._item_type == "folders":
                        query += f"mimeType = '{self.G_DRIVE_DIR_MIME_TYPE}' and "
                query += "trashed = false"
                return (
                    self.service.files()
                    .list(
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        q=query,
                        spaces="drive",
                        pageSize=150,
                        fields="files(id, name, mimeType, size)",
                        orderBy="folder, name asc",
                    )
                    .execute()
                )
        except Exception as err:
            err = str(err).replace(">", "").replace("<", "")
            LOGGER.error(err)
            return {"files": []}

    def drive_list(self, file_name, target_id="", user_id=""):
        msg = ""
        file_name = self.escapes(str(file_name))
        contents_no = 0
        telegraph_content = []
        Title = False

        if target_id.startswith("mtp:"):
            drives = self.get_user_drive(target_id, user_id)
        elif target_id:
            drives = [
                (
                    "From Owner",
                    target_id.replace("tp:", "", 1),
                    index_urls[0] if index_urls else "",
                )
            ]
        else:
            drives = zip(drives_names, drives_ids, index_urls)
        if (
            not target_id.startswith("mtp:")
            and len(drives_ids) > 1
            or target_id.startswith("tp:")
        ):
            self.use_sa = False

        self.service = self.authorize()

        for drive_name, dir_id, index_url in drives:
            isRecur = (
                False if self._is_recursive and len(dir_id) > 23 else self._is_recursive
            )
            response = self._drive_query(dir_id, file_name, isRecur)
            if not response["files"]:
                if self._no_multi:
                    break
                else:
                    continue
            if not Title:
                msg += f"<h4>Search Result For {file_name}</h4>"
                Title = True
            if drive_name:
                msg += f"╾────────────╼<br><b>{drive_name}</b><br>╾────────────╼<br>"
            for file in response.get("files", []):
                mime_type = file.get("mimeType")
                if mime_type == self.G_DRIVE_DIR_MIME_TYPE:
                    furl = self.G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(file.get("id"))
                    msg += f"📁 <code>{file.get('name')}<br>(folder)</code><br>"
                    msg += f"<b><a href={furl}>Drive Link</a></b>"
                    if index_url:
                        url = f'{index_url}findpath?id={file.get("id")}'
                        msg += f' <b>| <a href="{url}">Index Link</a></b>'
                elif mime_type == "application/vnd.google-apps.shortcut":
                    furl = self.G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(file.get("id"))
                    msg += (
                        f"⁍<a href='{self.G_DRIVE_DIR_BASE_DOWNLOAD_URL.format(file.get('id'))}'>{file.get('name')}"
                        f"</a> (shortcut)"
                    )
                else:
                    furl = self.G_DRIVE_BASE_DOWNLOAD_URL.format(file.get("id"))
                    msg += f"📄 <code>{file.get('name')}<br>({get_readable_file_size(int(file.get('size', 0)))})</code><br>"
                    msg += f"<b><a href={furl}>Drive Link</a></b>"
                    if index_url:
                        url = f'{index_url}findpath?id={file.get("id")}'
                        msg += f' <b>| <a href="{url}">Index Link</a></b>'
                        if mime_type.startswith(("image", "video", "audio")):
                            urlv = f'{index_url}findpath?id={file.get("id")}&view=true'
                            msg += f' <b>| <a href="{urlv}">View Link</a></b>'
                msg += "<br><br>"
                contents_no += 1
                if len(msg.encode("utf-8")) > 39000:
                    telegraph_content.append(msg)
                    msg = ""
            if self._no_multi:
                break

        if msg != "":
            telegraph_content.append(msg)

        return telegraph_content, contents_no

    def get_user_drive(self, target_id, user_id):
        dest_id = target_id.replace("mtp:", "", 1)
        self.token_path = f"tokens/{user_id}.pickle"
        self.use_sa = False
        user_dict = user_data.get(user_id, {})
        INDEX = user_dict["index_url"] if user_dict.get("index_url") else ""
        return [("User Choice", dest_id, INDEX)]
