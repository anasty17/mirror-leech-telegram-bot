from aiofiles.os import remove, path as aiopath, listdir, rmdir
from aioshutil import rmtree as aiormtree
from magic import Magic
from os import walk, path as ospath, makedirs
from re import split as re_split, I, search as re_search, escape
from shutil import rmtree
from subprocess import run as srun
from sys import exit as sexit

from bot import aria2, LOGGER, DOWNLOAD_DIR, qbittorrent_client
from bot.helper.ext_utils.bot_utils import sync_to_async, cmd_exec
from .exceptions import NotSupportedExtractionArchive

ARCH_EXT = [
    ".tar.bz2",
    ".tar.gz",
    ".bz2",
    ".gz",
    ".tar.xz",
    ".tar",
    ".tbz2",
    ".tgz",
    ".lzma2",
    ".zip",
    ".7z",
    ".z",
    ".rar",
    ".iso",
    ".wim",
    ".cab",
    ".apm",
    ".arj",
    ".chm",
    ".cpio",
    ".cramfs",
    ".deb",
    ".dmg",
    ".fat",
    ".hfs",
    ".lzh",
    ".lzma",
    ".mbr",
    ".msi",
    ".mslz",
    ".nsis",
    ".ntfs",
    ".rpm",
    ".squashfs",
    ".udf",
    ".vhd",
    ".xar",
]

FIRST_SPLIT_REGEX = r"(\.|_)part0*1\.rar$|(\.|_)7z\.0*1$|(\.|_)zip\.0*1$|^(?!.*(\.|_)part\d+\.rar$).*\.rar$"

SPLIT_REGEX = r"\.r\d+$|\.7z\.\d+$|\.z\d+$|\.zip\.\d+$"


def is_first_archive_split(file):
    return bool(re_search(FIRST_SPLIT_REGEX, file))


def is_archive(file):
    return file.endswith(tuple(ARCH_EXT))


def is_archive_split(file):
    return bool(re_search(SPLIT_REGEX, file))


async def clean_target(path):
    if await aiopath.exists(path):
        LOGGER.info(f"Cleaning Target: {path}")
        try:
            if await aiopath.isdir(path):
                await aiormtree(path, ignore_errors=True)
            else:
                await remove(path)
        except Exception as e:
            LOGGER.error(str(e))


async def clean_download(path):
    if await aiopath.exists(path):
        LOGGER.info(f"Cleaning Download: {path}")
        try:
            await aiormtree(path, ignore_errors=True)
        except Exception as e:
            LOGGER.error(str(e))


def clean_all():
    aria2.remove_all(True)
    qbittorrent_client.torrents_delete(torrent_hashes="all")
    try:
        LOGGER.info("Cleaning Download Directory")
        rmtree(DOWNLOAD_DIR, ignore_errors=True)
    except:
        pass
    makedirs(DOWNLOAD_DIR, exist_ok=True)


def exit_clean_up(signal, frame):
    try:
        LOGGER.info("Please wait, while we clean up and stop the running downloads")
        clean_all()
        srun(["pkill", "-9", "-f", "gunicorn|aria2c|qbittorrent-nox|ffmpeg|java"])
        sexit(0)
    except KeyboardInterrupt:
        LOGGER.warning("Force Exiting before the cleanup finishes!")
        sexit(1)


async def clean_unwanted(path, custom_list=None):
    if custom_list is None:
        custom_list = []
    LOGGER.info(f"Cleaning unwanted files/folders: {path}")
    for dirpath, _, files in await sync_to_async(walk, path, topdown=False):
        for filee in files:
            f_path = ospath.join(dirpath, filee)
            if (
                filee.endswith(".!qB")
                or f_path in custom_list
                or filee.endswith(".parts")
                and filee.startswith(".")
            ):
                await remove(f_path)
        if dirpath.endswith((".unwanted", "splited_files_mltb", "copied_mltb")):
            await aiormtree(dirpath, ignore_errors=True)
    for dirpath, _, files in await sync_to_async(walk, path, topdown=False):
        if not await listdir(dirpath):
            await rmdir(dirpath)


async def get_path_size(path):
    if await aiopath.isfile(path):
        return await aiopath.getsize(path)
    total_size = 0
    for root, _, files in await sync_to_async(walk, path):
        for f in files:
            abs_path = ospath.join(root, f)
            total_size += await aiopath.getsize(abs_path)
    return total_size


async def count_files_and_folders(path, extension_filter, unwanted_files=None):
    if unwanted_files is None:
        unwanted_files = []
    total_files = 0
    total_folders = 0
    for dirpath, dirs, files in await sync_to_async(walk, path):
        total_files += len(files)
        for f in files:
            if f.endswith(tuple(extension_filter)):
                total_files -= 1
            elif unwanted_files:
                f_path = ospath.join(dirpath, f)
                if f_path in unwanted_files:
                    total_files -= 1
        total_folders += len(dirs)
    return total_folders, total_files


def get_base_name(orig_path):
    extension = next((ext for ext in ARCH_EXT if orig_path.lower().endswith(ext)), "")
    if extension != "":
        return re_split(f"{extension}$", orig_path, maxsplit=1, flags=I)[0]
    else:
        raise NotSupportedExtractionArchive("File format not supported for extraction")


def get_mime_type(file_path):
    mime = Magic(mime=True)
    mime_type = mime.from_file(file_path)
    mime_type = mime_type or "text/plain"
    return mime_type


async def join_files(path):
    files = await listdir(path)
    results = []
    exists = False
    for file_ in files:
        if re_search(r"\.0+2$", file_) and await sync_to_async(
            get_mime_type, f"{path}/{file_}"
        ) not in ["application/x-7z-compressed", "application/zip"]:
            exists = True
            final_name = file_.rsplit(".", 1)[0]
            fpath = f"{path}/{final_name}"
            cmd = f'cat "{fpath}."* > "{fpath}"'
            _, stderr, code = await cmd_exec(cmd, True)
            if code != 0:
                LOGGER.error(f"Failed to join {final_name}, stderr: {stderr}")
                if await aiopath.isfile(fpath):
                    await remove(fpath)
            else:
                results.append(final_name)

    if not exists:
        LOGGER.warning("No files to join!")
    elif results:
        LOGGER.info("Join Completed!")
        for res in results:
            for file_ in files:
                if re_search(rf"{escape(res)}\.0[0-9]+$", file_):
                    await remove(f"{path}/{file_}")
