import sys
import shutil
import os
import pathlib
import magic
import tarfile
import subprocess
import time
import math
import json

from PIL import Image

from .exceptions import NotSupportedExtractionArchive
from bot import aria2, LOGGER, DOWNLOAD_DIR, get_client, TG_SPLIT_SIZE, EQUAL_SPLITS

VIDEO_SUFFIXES = ("M4V", "MP4", "MOV", "FLV", "WMV", "3GP", "MPG", "WEBM", "MKV", "AVI")

def clean_download(path: str):
    if os.path.exists(path):
        LOGGER.info(f"Cleaning Download: {path}")
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            pass

def start_cleanup():
    try:
        shutil.rmtree(DOWNLOAD_DIR)
    except FileNotFoundError:
        pass

def clean_all():
    aria2.remove_all(True)
    get_client().torrents_delete(torrent_hashes="all")
    try:
        shutil.rmtree(DOWNLOAD_DIR)
    except FileNotFoundError:
        pass

def exit_clean_up(signal, frame):
    try:
        LOGGER.info("Please wait, while we clean up the downloads and stop running downloads")
        clean_all()
        sys.exit(0)
    except KeyboardInterrupt:
        LOGGER.warning("Force Exiting before the cleanup finishes!")
        sys.exit(1)

def get_path_size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total_size = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            abs_path = os.path.join(root, f)
            total_size += os.path.getsize(abs_path)
    return total_size

"""
def tar(org_path):
    tar_path = org_path + ".tar"
    path = pathlib.PurePath(org_path)
    LOGGER.info(f'Tar: orig_path: {org_path}, tar_path: {tar_path}')
    tar = tarfile.open(tar_path, "w")
    tar.add(org_path, arcname=path.name)
    tar.close()
    return tar_path
"""

def get_base_name(orig_path: str):
    if orig_path.endswith(".tar.bz2"):
        return orig_path.rsplit(".tar.bz2", 1)[0]
    elif orig_path.endswith(".tar.gz"):
        return orig_path.rsplit(".tar.gz", 1)[0]
    elif orig_path.endswith(".bz2"):
        return orig_path.rsplit(".bz2", 1)[0]
    elif orig_path.endswith(".gz"):
        return orig_path.rsplit(".gz", 1)[0]
    elif orig_path.endswith(".tar.xz"):
        return orig_path.rsplit(".tar.xz", 1)[0]
    elif orig_path.endswith(".tar"):
        return orig_path.rsplit(".tar", 1)[0]
    elif orig_path.endswith(".tbz2"):
        return orig_path.rsplit("tbz2", 1)[0]
    elif orig_path.endswith(".tgz"):
        return orig_path.rsplit(".tgz", 1)[0]
    elif orig_path.endswith(".zip"):
        return orig_path.rsplit(".zip", 1)[0]
    elif orig_path.endswith(".7z"):
        return orig_path.rsplit(".7z", 1)[0]
    elif orig_path.endswith(".Z"):
        return orig_path.rsplit(".Z", 1)[0]
    elif orig_path.endswith(".rar"):
        return orig_path.rsplit(".rar", 1)[0]
    elif orig_path.endswith(".iso"):
        return orig_path.rsplit(".iso", 1)[0]
    elif orig_path.endswith(".wim"):
        return orig_path.rsplit(".wim", 1)[0]
    elif orig_path.endswith(".cab"):
        return orig_path.rsplit(".cab", 1)[0]
    elif orig_path.endswith(".apm"):
        return orig_path.rsplit(".apm", 1)[0]
    elif orig_path.endswith(".arj"):
        return orig_path.rsplit(".arj", 1)[0]
    elif orig_path.endswith(".chm"):
        return orig_path.rsplit(".chm", 1)[0]
    elif orig_path.endswith(".cpio"):
        return orig_path.rsplit(".cpio", 1)[0]
    elif orig_path.endswith(".cramfs"):
        return orig_path.rsplit(".cramfs", 1)[0]
    elif orig_path.endswith(".deb"):
        return orig_path.rsplit(".deb", 1)[0]
    elif orig_path.endswith(".dmg"):
        return orig_path.rsplit(".dmg", 1)[0]
    elif orig_path.endswith(".fat"):
        return orig_path.rsplit(".fat", 1)[0]
    elif orig_path.endswith(".hfs"):
        return orig_path.rsplit(".hfs", 1)[0]
    elif orig_path.endswith(".lzh"):
        return orig_path.rsplit(".lzh", 1)[0]
    elif orig_path.endswith(".lzma"):
        return orig_path.rsplit(".lzma", 1)[0]
    elif orig_path.endswith(".lzma2"):
        return orig_path.rsplit(".lzma2", 1)[0]
    elif orig_path.endswith(".mbr"):
        return orig_path.rsplit(".mbr", 1)[0]
    elif orig_path.endswith(".msi"):
        return orig_path.rsplit(".msi", 1)[0]
    elif orig_path.endswith(".mslz"):
        return orig_path.rsplit(".mslz", 1)[0]
    elif orig_path.endswith(".nsis"):
        return orig_path.rsplit(".nsis", 1)[0]
    elif orig_path.endswith(".ntfs"):
        return orig_path.rsplit(".ntfs", 1)[0]
    elif orig_path.endswith(".rpm"):
        return orig_path.rsplit(".rpm", 1)[0]
    elif orig_path.endswith(".squashfs"):
        return orig_path.rsplit(".squashfs", 1)[0]
    elif orig_path.endswith(".udf"):
        return orig_path.rsplit(".udf", 1)[0]
    elif orig_path.endswith(".vhd"):
        return orig_path.rsplit(".vhd", 1)[0]
    elif orig_path.endswith(".xar"):
        return orig_path.rsplit(".xar", 1)[0]
    else:
        raise NotSupportedExtractionArchive('File format not supported for extraction')

def get_mime_type(file_path):
    mime = magic.Magic(mime=True)
    mime_type = mime.from_file(file_path)
    mime_type = mime_type or "text/plain"
    return mime_type

def take_ss(video_file):
    des_dir = 'Thumbnails'
    if not os.path.exists(des_dir):
        os.mkdir(des_dir)
    des_dir = os.path.join(des_dir, f"{time.time()}.jpg")
    duration = get_media_info(video_file)[0]
    if duration == 0:
        duration = 3
    duration = duration // 2
    try:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(duration),
                        "-i", video_file, "-vframes", "1", des_dir])
    except:
        return None

    if not os.path.lexists(des_dir):
        return None
    Image.open(des_dir).convert("RGB").save(des_dir, "JPEG")
    return des_dir

def split(path, size, filee, dirpath, split_size, start_time=0, i=1, inLoop=False):
    parts = math.ceil(size/TG_SPLIT_SIZE)
    if EQUAL_SPLITS and not inLoop:
        split_size = math.ceil(size/parts)
    if filee.upper().endswith(VIDEO_SUFFIXES):
        base_name, extension = os.path.splitext(filee)
        split_size = split_size - 2500000
        while i <= parts :
            parted_name = "{}.part{}{}".format(str(base_name), str(i).zfill(3), str(extension))
            out_path = os.path.join(dirpath, parted_name)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i",
                            path, "-ss", str(start_time), "-fs", str(split_size),
                            "-async", "1", "-strict", "-2", "-c", "copy", out_path])
            out_size = get_path_size(out_path)
            if out_size > 2097152000:
                dif = out_size - 2097152000
                split_size = split_size - dif + 2500000
                os.remove(out_path)
                return split(path, size, filee, dirpath, split_size, start_time, i, inLoop=True)
            lpd = get_media_info(out_path)[0]
            if lpd <= 4 or out_size < 1000000:
                os.remove(out_path)
                break
            start_time += lpd - 3
            i = i + 1
    else:
        out_path = os.path.join(dirpath, filee + ".")
        subprocess.run(["split", "--numeric-suffixes=1", "--suffix-length=3", f"--bytes={split_size}", path, out_path])

def get_media_info(path):
    try:
        result = subprocess.check_output(["ffprobe", "-hide_banner", "-loglevel", "error", "-print_format",
                                          "json", "-show_format", path]).decode('utf-8')
        fields = json.loads(result)['format']
    except Exception as e:
        LOGGER.error(f"get_media_info: {e}")
        return 0, None, None
    try:
        duration = round(float(fields['duration']))
    except:
        duration = 0
    try:
        artist = str(fields['tags']['artist'])
    except:
        artist = None
    try:
        title = str(fields['tags']['title'])
    except:
        title = None
    return duration, artist, title

def get_video_resolution(path):
    try:
        result = subprocess.check_output(["ffprobe", "-hide_banner", "-loglevel", "error", "-select_streams", "v:0",
                                          "-show_entries", "stream=width,height", "-of", "json", path]).decode('utf-8')
        fields = json.loads(result)['streams'][0]

        width = int(fields['width'])
        height = int(fields['height'])
        return width, height
    except Exception as e:
        LOGGER.error(f"get_video_resolution: {e}")
        return 480, 320

