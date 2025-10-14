# Change and Bug Log

This file will be updated with every change made to the codebase.

---

## [2025-10-13] - Manual Porting of Alpha Features

This log details the surgical implementation of features from the `alpha` branch into the `manual-feature-port` branch.

### New Files Created
- **`changes.md`**: This file, to log all work.
- **`bot/helper/video_utils/processor.py`**: The core of the new video processing pipeline. Contains logic to analyze media streams and select them based on language preferences.
- **`bot/helper/ext_utils/mkvmerge_utils.py`**: A robust, container-aware video splitter using `mkvmerge` to handle large files for Telegram.

### Existing Files Modified
- **`bot/core/config_manager.py`**:
    - Added `PREFERRED_LANGUAGES` to allow user customization of track removal.
    - Added `USE_USER_SESSION_FOR_BIG_FILES` for flexible upload handling.
- **`bot/core/mltb_client.py`**:
    - Adjusted `MAX_SPLIT_SIZE` values to be more precise, preventing upload failures due to Telegram's size limits.
- **`bot/helper/ext_utils/media_utils.py`**:
    - Significantly improved the reliability of `get_media_info` and `get_document_type` by adding timeouts and better error handling.
    - Added a new `run_command` method to the `FFMpeg` class for more stable FFmpeg execution.
    - Removed the old, unreliable `ffmpeg`-based video splitter.
- **`bot/helper/listeners/task_listener.py`**:
    - Completely refactored the class to support the new, more robust task lifecycle.
    - Integrated the call to the new `process_video` function in `on_download_complete`.
    - Added logic to handle multi-file processing from extracted archives.
    - Implemented the new detailed completion messages.
- **`bot/helper/mirror_leech_utils/telegram_uploader.py`**:
    - Rewrote the `upload` method to integrate with the new `mkvmerge` and standard splitting logic.
    - Implemented a queue-based system to handle the upload of split parts sequentially.
- **`bot/modules/mirror_leech.py`**:
    - Simplified the main command logic by offloading the entire task lifecycle to the refactored `TaskListener` via the `on_task_created` method.
- **`bot/helper/telegram_helper/message_utils.py`**:
    - Added `tenacity` retry logic to the `edit_message` function to make it more resilient to Telegram API flood waits.