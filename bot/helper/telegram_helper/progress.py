from asyncio import Lock
from collections import defaultdict

from bot import LOGGER


class ProgressTracker:
    def __init__(self):
        self.progress_dict = defaultdict(dict)
        self.locks = defaultdict(Lock)
        self.callbacks = {}

    async def update_progress(
        self,
        key,
        transferred,
        total,
        is_active,
        is_completed,
        file_id,
    ):
        async with self.locks[key]:
            if key not in self.progress_dict:
                return
            self.progress_dict[key] = {
                "transferred": transferred,
                "total": total,
                "is_active": is_active,
                "is_completed": is_completed,
            }
            callback = self.callbacks.get(key)

        if callback:
            try:
                await callback(key, self.progress_dict[key], is_completed, file_id)
            except Exception as e:
                LOGGER.error(f"Callback error for file {key}: {e}")
        if is_completed:
            await self.cancel_progress(key)

    async def add_to_progress(self, key, callback):
        async with self.locks[key]:
            self.progress_dict[key] = {}
            if callable(callback):
                self.callbacks[key] = callback

    async def cancel_progress(self, key):
        lock = self.locks.get(key)
        if not lock:
            self.progress_dict.pop(key, None)
            self.callbacks.pop(key, None)
            return
        async with lock:
            self.progress_dict.pop(key, None)
            self.callbacks.pop(key, None)
        self.locks.pop(key, None)


async def tdlib_file_update(_, update):
    file = update.file
    local_file = file.local
    remote_file = file.remote
    if local_file.path.startswith("/mltb/downloads/"):
        key = local_file.path
        transfer_type = "upload"
        file_id = None
    else:
        file_id = file.id
        key = remote_file.id
        transfer_type = "download"
    async with tracker.locks[key]:
        if key not in tracker.progress_dict:
            return
    if transfer_type == "upload":
        is_active = remote_file.is_uploading_active
        is_completed = remote_file.is_uploading_completed
        transferred = remote_file.uploaded_size
    else:
        key = remote_file.id
        is_active = local_file.is_downloading_active
        is_completed = local_file.is_downloading_completed
        transferred = local_file.downloaded_size
    total = file.size or file.expected_size
    await tracker.update_progress(key, transferred, total, is_active, is_completed, file_id)


tracker = ProgressTracker()
