from os import remove as osremove, path as ospath, mkdir, walk, listdir, rmdir, makedirs
from sys import exit as sysexit
from shutil import rmtree
from PIL import Image
from magic import Magic
from subprocess import run as srun, check_output, Popen
from time import time
from math import ceil
from re import split as re_split, I

from .exceptions import NotSupportedExtractionArchive
from bot import aria2, app, LOGGER, DOWNLOAD_DIR, get_client, IS_PREMIUM_USER, MAX_SPLIT_SIZE, config_dict, user_data

ARCH_EXT = [".tar.bz2", ".tar.gz", ".bz2", ".gz", ".tar.xz", ".tar", ".tbz2", ".tgz", ".lzma2",
            ".zip", ".7z", ".z", ".rar", ".iso", ".wim", ".cab", ".apm", ".arj", ".chm",
            ".cpio", ".cramfs", ".deb", ".dmg", ".fat", ".hfs", ".lzh", ".lzma", ".mbr",
            ".msi", ".mslz", ".nsis", ".ntfs", ".rpm", ".squashfs", ".udf", ".vhd", ".xar"]

def clean_target(path: str):
    if ospath.exists(path):
        LOGGER.info(f"Cleaning Target: {path}")
        if ospath.isdir(path):
            try:
                rmtree(path)
            except:
                pass
        elif ospath.isfile(path):
            try:
                osremove(path)
            except:
                pass

def clean_download(path: str):
    if ospath.exists(path):
        LOGGER.info(f"Cleaning Download: {path}")
        try:
            rmtree(path)
        except:
            pass

def start_cleanup():
    get_client().torrents_delete(torrent_hashes="all")
    try:
        rmtree(DOWNLOAD_DIR)
    except:
        pass
    makedirs(DOWNLOAD_DIR)

def clean_all():
    aria2.remove_all(True)
    get_client().torrents_delete(torrent_hashes="all")
    app.stop()
    try:
        rmtree(DOWNLOAD_DIR)
    except:
        pass

def exit_clean_up(signal, frame):
    try:
        LOGGER.info("Please wait, while we clean up the downloads and stop running downloads")
        clean_all()
        sysexit(0)
    except KeyboardInterrupt:
        LOGGER.warning("Force Exiting before the cleanup finishes!")
        sysexit(1)

def clean_unwanted(path: str):
    LOGGER.info(f"Cleaning unwanted files/folders: {path}")
    for dirpath, subdir, files in walk(path, topdown=False):
        for filee in files:
            if filee.endswith(".!qB") or filee.endswith('.parts') and filee.startswith('.'):
                osremove(ospath.join(dirpath, filee))
        if dirpath.endswith((".unwanted", "splited_files_mltb")):
            rmtree(dirpath)
    for dirpath, subdir, files in walk(path, topdown=False):
        if not listdir(dirpath):
            rmdir(dirpath)

def get_path_size(path: str):
    if ospath.isfile(path):
        return ospath.getsize(path)
    total_size = 0
    for root, dirs, files in walk(path):
        for f in files:
            abs_path = ospath.join(root, f)
            total_size += ospath.getsize(abs_path)
    return total_size

def get_base_name(orig_path: str):
    if ext := [ext for ext in ARCH_EXT if orig_path.lower().endswith(ext)]:
        ext = ext[0]
        return re_split(f'{ext}$', orig_path, maxsplit=1, flags=I)[0]
    else:
        raise NotSupportedExtractionArchive('File format not supported for extraction')

def get_mime_type(file_path):
    mime = Magic(mime=True)
    mime_type = mime.from_file(file_path)
    mime_type = mime_type or "text/plain"
    return mime_type

def take_ss(video_file, duration):
    des_dir = 'Thumbnails'
    if not ospath.exists(des_dir):
        mkdir(des_dir)
    des_dir = ospath.join(des_dir, f"{time()}.jpg")
    if duration is None:
        duration = get_media_info(video_file)[0]
    if duration == 0:
        duration = 3
    duration = duration // 2

    status = srun(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(duration),
                   "-i", video_file, "-frames:v", "1", des_dir])

    if status.returncode != 0 or not ospath.lexists(des_dir):
        return None

    with Image.open(des_dir) as img:
        img.convert("RGB").save(des_dir, "JPEG")

    return des_dir

def split_file(path, size, file_, dirpath, split_size, listener, start_time=0, i=1, inLoop=False, noMap=False):
    if listener.seed and not listener.newDir:
        dirpath = f"{dirpath}/splited_files_mltb"
        if not ospath.exists(dirpath):
            mkdir(dirpath)
    user_id = listener.message.from_user.id
    user_dict = user_data.get(user_id, {})
    leech_split_size = user_dict.get('split_size') or config_dict['LEECH_SPLIT_SIZE']
    parts = ceil(size/leech_split_size)
    if (user_dict.get('equal_splits') or config_dict['EQUAL_SPLITS']) and not inLoop:
        split_size = ceil(size/parts) + 1000
    if get_media_streams(path)[0]:
        duration = get_media_info(path)[0]
        base_name, extension = ospath.splitext(file_)
        split_size = split_size - 5000000
        while i <= parts or start_time < duration - 4:
            parted_name = f"{str(base_name)}.part{str(i).zfill(3)}{str(extension)}"
            out_path = ospath.join(dirpath, parted_name)
            if not noMap:
                listener.suproc = Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start_time),
                                         "-i", path, "-fs", str(split_size), "-map", "0", "-map_chapters", "-1",
                                         "-async", "1", "-strict", "-2", "-c", "copy", out_path])
            else:
                listener.suproc = Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start_time),
                                          "-i", path, "-fs", str(split_size), "-map_chapters", "-1", "-async", "1",
                                          "-strict", "-2","-c", "copy", out_path])
            listener.suproc.wait()
            if listener.suproc.returncode == -9:
                return False
            elif listener.suproc.returncode != 0 and not noMap:
                LOGGER.warning(f"Retrying without map, -map 0 not working in all situations. Path: {path}")
                try:
                    osremove(out_path)
                except:
                    pass
                return split_file(path, size, file_, dirpath, split_size, listener, start_time, i, True, True)
            elif listener.suproc.returncode != 0:
                LOGGER.warning(f"Unable to split this video, if it's size less than {MAX_SPLIT_SIZE} will be uploaded as it is. Path: {path}")
                try:
                    osremove(out_path)
                except:
                    pass
                return "errored"
            out_size = get_path_size(out_path)
            if out_size > MAX_SPLIT_SIZE:
                dif = out_size - MAX_SPLIT_SIZE
                split_size = split_size - dif + 5000000
                osremove(out_path)
                return split_file(path, size, file_, dirpath, split_size, listener, start_time, i, True, noMap)
            lpd = get_media_info(out_path)[0]
            if lpd == 0:
                LOGGER.error(f'Something went wrong while splitting, mostly file is corrupted. Path: {path}')
                break
            elif duration == lpd:
                if not noMap:
                    LOGGER.warning(f"Retrying without map. -map 0 not working in all situations. Path: {path}")
                    try:
                        osremove(out_path)
                    except:
                        pass
                    return split_file(path, size, file_, dirpath, split_size, listener, start_time, i, True, True)
                else:
                    LOGGER.warning(f"This file has been splitted with default stream and audio, so you will only see one part with less size from orginal one because it doesn't have all streams and audios. This happens mostly with MKV videos. noMap={noMap}. Path: {path}")
                    break
            elif lpd <= 3:
                osremove(out_path)
                break
            start_time += lpd - 3
            i = i + 1
    else:
        out_path = ospath.join(dirpath, f"{file_}.")
        listener.suproc = Popen(["split", "--numeric-suffixes=1", "--suffix-length=3",
                                f"--bytes={split_size}", path, out_path])
        listener.suproc.wait()
        if listener.suproc.returncode == -9:
            return False
    return True

def get_media_info(path):

    try:
        result = check_output(["ffprobe", "-hide_banner", "-loglevel", "error", "-print_format",
                               "json", "-show_format", "-show_streams", path]).decode('utf-8')
    except Exception as e:
        LOGGER.error(f'{e}. Mostly file not found!')
        return 0, None, None

    fields = eval(result).get('format')
    if fields is None:
        LOGGER.error(f"get_media_info: {result}")
        return 0, None, None

    duration = round(float(fields.get('duration', 0)))

    if fields := fields.get('tags'):
        artist = fields.get('artist')
        if artist is None:
            artist = fields.get('ARTIST')
        title = fields.get('title')
        if title is None:
            title = fields.get('TITLE')
    else:
        title = None
        artist = None

    return duration, artist, title

def get_media_streams(path):

    is_video = False
    is_audio = False
    is_image = False

    mime_type = get_mime_type(path)
    if mime_type.startswith('audio'):
        is_audio = True
        return is_video, is_audio, is_image

    if mime_type.startswith('image'):
        is_image = True
        return is_video, is_audio, is_image

    if path.endswith('.bin') or not mime_type.startswith('video') and not mime_type.endswith('octet-stream'):
        return is_video, is_audio, is_image

    try:
        result = check_output(["ffprobe", "-hide_banner", "-loglevel", "error", "-print_format",
                               "json", "-show_streams", path]).decode('utf-8')
    except Exception as e:
        if not mime_type.endswith('octet-stream'):
            LOGGER.error(f'{e}. Mostly file not found!')
        return is_video, is_audio, is_image

    fields = eval(result).get('streams')
    if fields is None:
        LOGGER.error(f"get_media_streams: {result}")
        return is_video, is_audio, is_image

    for stream in fields:
        if stream.get('codec_type') == 'video':
            is_video = True
        elif stream.get('codec_type') == 'audio':
            is_audio = True

    return is_video, is_audio, is_image

