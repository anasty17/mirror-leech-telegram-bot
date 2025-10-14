import os
import glob
import shutil
from aiofiles.os import remove as aioremove, path as aiopath
from bot import LOGGER
from bot.helper.ext_utils.bot_utils import cmd_exec

# Use decimal-based bytes for Telegram limits, as per official documentation
BUFFER_BYTES = 10 * 1024 * 1024  # 10MB buffer for mkvmerge container overhead

async def get_file_size(file_path):
    """Safely get the size of a file."""
    try:
        return await aiopath.getsize(file_path)
    except OSError as e:
        LOGGER.error(f"Could not get size of file {file_path}: {e}")
        return 0

async def split_video_if_needed(file_path: str, max_tg_size: int = 2000000000) -> list:
    """
    Splits a video file using mkvmerge with a dynamic, proportional retry strategy.

    - Uses decimal-based byte calculations for accuracy with Telegram limits.
    - Starts with an optimistic split size and proportionally reduces it if parts are oversized.
    - `max_tg_size` can be set for different user tiers (e.g., 4000000000 for premium).
    """
    if not shutil.which('mkvmerge'):
        LOGGER.error("mkvmerge is not installed. Cannot split file.")
        return [file_path]

    original_size = await get_file_size(file_path)
    if original_size == 0:
        return []
    if original_size <= max_tg_size:
        LOGGER.info(f"File size ({original_size} bytes) is within the {max_tg_size // 1000000}MB limit. No split needed.")
        return [file_path]

    dir_name = os.path.dirname(file_path)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_pattern = f"{os.path.join(dir_name, base_name)} - Part %03d.mkv"

    # Start with an optimistic split size slightly below the max limit
    current_split_size = max_tg_size - BUFFER_BYTES

    # Set a reasonable minimum to avoid infinite loops on problematic files
    min_split_size = 100 * 1000 * 1000 # 100MB

    while current_split_size >= min_split_size:
        LOGGER.info(f"✂️ Attempting to split with size: {current_split_size // 1000000}MB")

        # Clean up any split files from previous attempts
        for old_file in glob.glob(output_pattern.replace("%03d", "*")):
            try:
                await aioremove(old_file)
            except OSError as e:
                LOGGER.warning(f"Could not remove old split part {old_file}: {e}")

        # Build and execute the mkvmerge command
        cmd = ["mkvmerge", "-o", output_pattern, "--split", f"size:{current_split_size}", file_path]
        _, stderr, return_code = await cmd_exec(cmd)

        if return_code != 0:
            LOGGER.error(f"mkvmerge failed with return code {return_code}. Stderr: {stderr[:200]}...")
            # If mkvmerge fails outright, splitting is unlikely to succeed.
            return [file_path]

        split_files = sorted(glob.glob(output_pattern.replace("%03d", "*")))
        if len(split_files) <= 1:
            # This can happen if the file is smaller than the split size, but we already checked for that.
            # More likely, mkvmerge failed to split for other reasons.
            LOGGER.warning(f"No split occurred at {current_split_size // 1000000}MB. This might indicate an issue with the file.")
            # Reduce size and retry as a fallback
            current_split_size -= 10 * 1000 * 1000 # Reduce by 10MB
            continue

        # Check if any part is oversized
        max_part_size = 0
        for part in split_files:
            size = await get_file_size(part)
            if size > max_part_size:
                max_part_size = size

        if max_part_size < max_tg_size:
            LOGGER.info(f"✅ Success! Split created {len(split_files)} parts with max part size {max_part_size // 1000000}MB.")
            return split_files
        else:
            # Proportional reduction
            overshoot_ratio = max_part_size / max_tg_size
            LOGGER.warning(f"❌ Part oversized ({max_part_size // 1000000}MB). Overshoot ratio: {overshoot_ratio:.2f}. Retrying with smaller size.")
            # Reduce the split size proportionally to the overshoot, with an extra 1% buffer
            current_split_size = int((current_split_size / overshoot_ratio) * 0.99)

    LOGGER.error("❌ All dynamic mkvmerge attempts failed. Cannot create valid split parts.")
    return [file_path]