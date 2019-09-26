import sys
from bot import aria2, LOGGER, DOWNLOAD_DIR
import shutil
import os
import pathlib


def clean_download(path: str):
    if os.path.exists(path):
        shutil.rmtree(path)


def exit_clean_up(signal, frame):
    try:
        LOGGER.info("Please wait, while we clean up the downloads and stop running downloads")
        aria2.autopurge()
        aria2.remove_all(True)
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
