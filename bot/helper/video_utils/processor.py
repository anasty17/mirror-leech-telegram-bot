from bot import LOGGER, task_dict_lock, task_dict, bot_loop
from bot.core.config_manager import Config
from bot.helper.ext_utils.files_utils import get_path_size
from ..mirror_leech_utils.status_utils.ffmpeg_status import FFmpegStatus
from ..ext_utils.media_utils import FFMpeg
import asyncio
import json
from time import time
import os.path as ospath
from aiofiles.os import rename as aiorename, path as aiopath
from json import JSONDecodeError

async def get_media_info(path):
    """Get media information using ffprobe with a timeout."""
    default_info = {"format": {"duration": 0, "tags": {}}, "streams": []}
    try:
        process = await asyncio.create_subprocess_exec(
            'ffprobe', '-hide_banner', '-loglevel', 'error', '-print_format', 'json',
            '-show_format', '-show_streams', path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
        except asyncio.TimeoutError:
            LOGGER.error(f"ffprobe timed out while processing {path}")
            process.kill()
            return default_info

        if process.returncode != 0:
            LOGGER.error(f"ffprobe error for {path}: {stderr.decode(errors='ignore').strip()}")
            return default_info

        try:
            return json.loads(stdout)
        except JSONDecodeError:
            LOGGER.error(f"Failed to parse ffprobe output: {stdout.decode(errors='ignore').strip()}")
            return default_info
    except Exception as e:
        LOGGER.error(f"Exception in get_media_info for {path}: {e}", exc_info=True)
        return default_info

async def run_ffmpeg(command, path, listener):
    """Run the generated ffmpeg command and report progress."""
    ffmpeg = FFMpeg(listener)

    processed_path = await ffmpeg.run_command(command, path)

    if processed_path:
        LOGGER.info(f"Video processing successful: {processed_path}")
        return processed_path
    else:
        LOGGER.error(f"ffmpeg exited with non-zero return code.")
        if listener.is_cancelled:
            return None
        await listener.on_upload_error(f"ffmpeg exited with non-zero return code.")
        return None

async def process_video(path, listener):
    """Main function to process the video based on user's final logic."""
    LOGGER.info("Starting video processing for: %s", path)
    await listener.update_and_log_status("Processing with FFmpeg...")

    if hasattr(listener, 'streams_kept') and listener.streams_kept:
        LOGGER.info("Streams already processed by manual selection, skipping automatic processing.")
        # If streams are manually selected, we still need media_info for the completion message.
        if not listener.media_info:
             listener.media_info = await get_media_info(path)
        return path, listener.media_info

    listener.original_name = ospath.basename(path)
    media_info = await get_media_info(path)
    if not media_info or 'streams' not in media_info:
        await listener.on_upload_error("Could not get media info from the input file.")
        return None, None

    all_streams = media_info['streams']
    LOGGER.info("Found %d streams in the media file.", len(all_streams))

    lang_map = {
        'te': 'tel', 'tel': 'tel', 'telugu': 'tel', 'తెలుగు': 'tel',
        'hi': 'hin', 'hin': 'hin', 'hindi': 'hin', 'हिंदी': 'hin',
        'en': 'eng', 'eng': 'eng', 'english': 'eng', 'ఇంగ్లీష్': 'eng',
        'ta': 'tam', 'tam': 'tam', 'tamil': 'tam', 'தமிழ்': 'tam',
        'ml': 'mal', 'mal': 'mal', 'malayalam': 'mal', 'മലയാളം': 'mal',
        'kn': 'kan', 'kan': 'kan', 'kannada': 'kan', 'ಕನ್ನಡ': 'kan',
        'ur': 'urd', 'urd': 'urd', 'urdu': 'urd', 'اردو': 'urd',
        'bn': 'ben', 'ben': 'ben', 'bengali': 'ben', 'বাংলা': 'ben',
    }

    def get_lang_code(stream):
        tags = stream.get('tags', {})
        lang = tags.get('language', 'und').lower()
        title = tags.get('title', '').lower()

        if lang in lang_map:
            return lang_map[lang]

        for key, value in lang_map.items():
            if key in title:
                LOGGER.info("Found language '%s' from title '%s' for stream %d", value, title, stream.get('index'))
                return value
        return lang

    all_video_streams = [s for s in all_streams if s.get('codec_type') == 'video']
    audio_streams_to_process = [s for s in all_streams if s.get('codec_type') == 'audio']

    art_streams = [s for s in all_video_streams if s.get('disposition', {}).get('attached_pic')]
    main_video_streams = [s for s in all_video_streams if not s.get('disposition', {}).get('attached_pic')]

    subtitle_streams_to_process = [s for s in all_streams if s.get('codec_type') == 'subtitle']

    lang_string = Config.PREFERRED_LANGUAGES or "tel"
    raw_preferred_langs = [lang.strip().strip('"\'') for lang in lang_string.split(',')]
    preferred_langs = [lang_map.get(lang, lang) for lang in raw_preferred_langs if lang]
    LOGGER.info("Using normalized language priority: %s", preferred_langs)

    selected_audio = []
    found_preferred_audio = False
    for pref_lang in preferred_langs:
        lang_audio_streams = [s for s in audio_streams_to_process if get_lang_code(s) == pref_lang]
        if lang_audio_streams:
            selected_audio = lang_audio_streams
            found_preferred_audio = True
            LOGGER.info("Found preferred audio language '%s', selecting %d stream(s).", pref_lang, len(lang_audio_streams))
            break

    if not found_preferred_audio:
        LOGGER.info("No preferred audio language found, keeping all audio tracks.")
        selected_audio = audio_streams_to_process

    selected_subtitles = []

    streams_to_keep_in_ffmpeg = main_video_streams + art_streams + selected_audio
    LOGGER.info("Total streams to keep: %d", len(streams_to_keep_in_ffmpeg))

    if len(streams_to_keep_in_ffmpeg) == len(all_streams):
         LOGGER.info("No streams to remove, skipping processing.")
         listener.streams_kept = main_video_streams + selected_audio
         kept_indices = {s['index'] for s in streams_to_keep_in_ffmpeg}
         listener.streams_removed = [s for s in all_streams if s['index'] not in kept_indices]
         listener.art_streams = art_streams
         return path, media_info

    cmd = ['ffmpeg', '-i', path, '-v', 'error']
    for stream in streams_to_keep_in_ffmpeg:
        cmd.extend(['-map', f'0:{stream["index"]}'])

    cmd.extend(['-c:v', 'copy', '-c:a', 'copy', '-c:s', 'copy', '-avoid_negative_ts', 'make_zero', '-fflags', '+genpts', '-max_interleave_delta', '0'])

    base_name, _ = path.rsplit('.', 1)
    output_path = f"{base_name}.processed.mkv"
    cmd.extend(['-f', 'matroska', '-y', output_path])

    LOGGER.info("Running ffmpeg command: %s", " ".join(cmd))
    processed_path = await run_ffmpeg(cmd, path, listener)

    if processed_path:
        final_path = processed_path.replace('.processed.mkv', '.mkv')
        await aiorename(processed_path, final_path)
        if not await aiopath.exists(final_path):
            LOGGER.error(f"Final processed file {final_path} does not exist after rename!")
            return None, None
        LOGGER.info("Video processing successful. Output: %s", final_path)

        listener.streams_kept = main_video_streams + selected_audio + selected_subtitles
        listener.art_streams = art_streams

        kept_indices = {s['index'] for s in listener.streams_kept + listener.art_streams}
        listener.streams_removed = [s for s in all_streams if s['index'] not in kept_indices]

        LOGGER.info("Final decision: Kept %d streams, Removed %d streams.", len(listener.streams_kept), len(listener.streams_removed))

        return final_path, media_info

    return None, None