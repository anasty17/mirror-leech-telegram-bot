import os
import subprocess
import aiofiles.os
import asyncio
import re
from bot import LOGGER, MAX_SPLIT_SIZE, config_dict, user_data
from bot.helper.ext_utils.bot_utils import cmd_exec
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.fs_utils import ARCH_EXT, get_mime_type

async def is_multi_streams(path):
    try:
        result = await cmd_exec(["ffprobe", "-hide_banner", "-loglevel", "error", "-print_format",
                                 "json", "-show_streams", path])
        if result[1]:
            LOGGER.warning(f'Get Video Streams: {result[1]}')
    except Exception as e:
        LOGGER.error(f'Get Video Streams: {e}. Mostly File not found!')
        return False
    fields = eval(result[0]).get('streams')
    if fields is None:
        LOGGER.error(f"get_video_streams: {result}")
        return False
    videos = sum(1 for stream in fields if stream.get('codec_type') == 'video')
    audios = sum(1 for stream in fields if stream.get('codec_type') == 'audio')
    return videos > 1 or audios > 1


async def get_media_info(path):
    try:
        result = await cmd_exec(["ffprobe", "-hide_banner", "-loglevel", "error", "-print_format",
                                 "json", "-show_format", path])
        if result[1]:
            LOGGER.warning(f'Get Media Info: {result[1]}')
    except Exception as e:
        LOGGER.error(f'Get Media Info: {e}. Mostly File not found!')
        return 0, None, None
    fields = eval(result[0]).get('format')
    if fields is None:
        LOGGER.error(f"get_media_info: {result}")
        return 0, None, None
    duration = round(float(fields.get('duration', 0)))
    tags = fields.get('tags', {})
    artist = tags.get('artist') or tags.get('ARTIST')
    title = tags.get('title') or tags.get('TITLE')
    return duration, artist, title


async def get_document_type(path):
    if path.endswith(tuple(ARCH_EXT)) or re.search(r'.+(\.|_)(rar|7z|zip|bin)(\.0*\d+)?$', path):
        return False, False, False
    mime_type = await sync_to_async(get_mime_type, path)
    if mime_type.startswith('audio'):
        return False, True, False
    if mime_type.startswith('image'):
        return False, False, True
    if not mime_type.startswith('video') and not mime_type.endswith('octet-stream'):
        return False, False, False
    try:
        result = await cmd_exec(["ffprobe", "-hide_banner", "-loglevel", "error", "-print_format",
                                 "json", "-show_streams", path])
        if result[1]:
            LOGGER.warning(f'Get Document Type: {result[1]}')
    except Exception as e:
        LOGGER.error(f'Get Document Type: {e}. Mostly File not found!')
        return False, False, False
    fields = eval(result[0]).get('streams')
    if fields is None:
        LOGGER.error(f"get_document_type: {result}")
        return False, False, False
    is_video = any(stream.get('codec_type') == 'video' for stream in fields)
    is_audio = any(stream.get('codec_type') == 'audio' for stream in fields)
    return is_video, is_audio, False


async def take_ss(video_file, duration):
    des_dir = 'Thumbnails'
    if not await aiofiles.os.path.exists(des_dir):
        await aiofiles.os.mkdir(des_dir)
    des_dir = os.path.join(des_dir, f"{time()}.jpg")
    if duration is None:
        duration, _, _ = await get_media_info(video_file)
    if duration == 0:
        duration = 3
    duration = duration // 2
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(duration),
        "-i", video_file, "-vf", "thumbnail", "-frames:v", "1", des_dir
    ]
    try:
        status = await asyncio.create_subprocess_exec(*cmd, stderr=subprocess.PIPE)
        if await status.wait() != 0 or not await aiofiles.os.path.exists(des_dir):
            err = (await status.stderr.read()).decode().strip()
            LOGGER.error(f'Error while extracting thumbnail. Name: {video_file} stderr: {err}')
            return None
    except Exception as e:
        LOGGER.error(f'Error while extracting thumbnail: {e}. Name: {video_file}')
        return None
    return des_dir


async def split_file(path, size, file_, dirpath, split_size, listener, start_time=0, i=1, inLoop=False, multi_streams=True):
    if listener.suproc == 'cancelled' or (listener.suproc is not None and listener.suproc.returncode == -9):
        return False
    if listener.seed and not listener.newDir:
        dirpath = f"{dirpath}/splited_files_mltb"
        if not await aiofiles.os.path.exists(dirpath):
            await aiofiles.os.mkdir(dirpath)
    user_id = listener.message.from_user.id
    user_dict = user_data.get(user_id, {})
    leech_split_size = user_dict.get('split_size') or config_dict['LEECH_SPLIT_SIZE']
    parts = -(-size // leech_split_size)
    if (user_dict.get('equal_splits') or config_dict['EQUAL_SPLITS']) and not inLoop:
        split_size = ((size + parts - 1) // parts) + 1000
    is_video, _, _ = await get_document_type(path)
    if is_video:
        if multi_streams:
            multi_streams = await is_multi_streams(path)
        duration, _, _ = await get_media_info(path)
        base_name, extension = os.path.splitext(file_)
        split_size -= 5000000
        while i <= parts or start_time < duration - 4:
            parted_name = f"{base_name}.part{i:03}{extension}"
            out_path = os.path.join(dirpath, parted_name)
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start_time), "-i", path,
                "-fs", str(split_size), "-map", "0", "-map_chapters", "-1", "-async", "1", "-strict",
                "-2", "-c", "copy", out_path
            ]
            if not multi_streams:
                del cmd[10]
                del cmd[10]
            if listener.suproc == 'cancelled' or (listener.suproc is not None and listener.suproc.returncode == -9):
                return False
            listener.suproc = await asyncio.create_subprocess_exec(*cmd, stderr=subprocess.PIPE)
            code = await listener.suproc.wait()
            if code == -9:
                return False
            elif code != 0:
                err = (await listener.suproc.stderr.read()).decode().strip()
                try:
                    await aiofiles.os.remove(out_path)
                except:
                    pass
                if multi_streams:
                    LOGGER.warning(f"{err}. Retrying without map, -map 0 not working in all situations. Path: {path}")
                    return await split_file(path, size, file_, dirpath, split_size, listener, start_time, i, True, False)
                else:
                    LOGGER.warning(f"{err}. Unable to split this video, if its size is less than {MAX_SPLIT_SIZE}, it will be uploaded as it is. Path: {path}")
                return "errored"
            out_size = await aiofiles.os.path.getsize(out_path)
            if out_size > MAX_SPLIT_SIZE:
                dif = out_size - MAX_SPLIT_SIZE
                split_size -= dif + 5000000
                await aiofiles.os.remove(out_path)
                return await split_file(path, size, file_, dirpath, split_size, listener, start_time, i, True)
            lpd, _, _ = await get_media_info(out_path)
            if lpd == 0:
                LOGGER.error(f'Something went wrong while splitting, mostly the file is corrupted. Path: {path}')
                break
            elif duration == lpd:
                LOGGER.warning(f"This file has been split with the default stream and audio, so you will only see one part with a smaller size from the original one because it doesn't have all the streams and audios. This mostly happens with MKV videos. Path: {path}")
                break
            elif lpd <= 3:
                await aiofiles.os.remove(out_path)
                break
            start_time += lpd - 3
            i += 1
    else:
        out_path = os.path.join(dirpath, f"{file_}.")
        listener.suproc = await asyncio.create_subprocess_exec("split", "--numeric-suffixes=1", "--suffix-length=3",
                                                               f"--bytes={split_size}", path, out_path, stderr=subprocess.PIPE)
        code = await listener.suproc.wait()
        if code == -9:
            return False
        elif code != 0:
            err = (await listener.suproc.stderr.read()).decode().strip()
            LOGGER.error(err)
    return True
