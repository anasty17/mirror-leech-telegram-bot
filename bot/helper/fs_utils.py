import sys
from bot import aria2, LOGGER, DOWNLOAD_DIR
import shutil
import os
import pathlib
import mimetypes


def clean_download(path: str):
    if os.path.exists(path):
        shutil.rmtree(path)


def exit_clean_up(signal, frame):
    try:
        LOGGER.info("Please wait, while we clean up the downloads and stop running downloads")
        for download in aria2.get_downloads():
            download.remove()
        shutil.rmtree(DOWNLOAD_DIR)
        sys.exit(0)
    except KeyboardInterrupt:
        LOGGER.warning("Force Exiting before the cleanup finishes!")
        sys.exit(1)


def tar(orig_path: str):
    path = pathlib.PurePath(orig_path)
    base = path.name
    root = path.parent.name
    shutil.make_archive(base_name=orig_path, format='tar', root_dir=root, base_dir=base)


def get_mime_type(file_path):
    mime_type = mimetypes.guess_type(file_path)[0]
    mime_type = mime_type if mime_type else "text/plain"
    return mime_type
