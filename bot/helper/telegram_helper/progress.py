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
        file_id: int,
        transfer_type: str,
        transferred: int,
        total: int,
        is_active: bool,
        completed: bool,
    ):
        if completed:
            await self.cancel_progress(file_id)
            return
        async with self.locks[file_id]:
            if file_id not in self.progress_dict:
                return
            self.progress_dict[file_id] = {
                "transfer_type": transfer_type,
                "transferred": transferred,
                "total": total,
                "is_active": is_active,
                "completed": completed,
            }

        if callback := self.callbacks.get(file_id):
            try:
                if hasattr(callback, "__await__"):
                    await callback(file_id, self.progress_dict[file_id])
                else:
                    callback(file_id, self.progress_dict[file_id])
            except Exception as e:
                LOGGER.error(f"Callback error for file {file_id}: {e}")

    async def add_to_progress(self, file_id: int, transfer_type: str, callback=None):
        async with self.locks[file_id]:
            self.progress_dict[file_id] = {"transfer_type": transfer_type}
            if callback and callable(callback):
                self.callbacks[file_id] = callback

    async def cancel_progress(self, file_id: int):
        lock = self.locks.get(file_id)
        if not lock:
            self.progress_dict.pop(file_id, None)
            self.callbacks.pop(file_id, None)
            return
        async with lock:
            self.progress_dict.pop(file_id, None)
            self.callbacks.pop(file_id, None)
        self.locks.pop(file_id, None)


async def tdlib_file_update(_, update):
    file = update.file
    file_id = file.id
    async with tracker.locks[file_id]:
        if file_id not in tracker.progress_dict:
            return
        transfer_type = tracker.progress_dict[file_id]["transfer_type"]
    if transfer_type == "download":
        local_file = file.local
        is_active = local_file.is_downloading_active
        completed = local_file.is_downloading_completed
        transferred = local_file.downloaded_size
    else:
        remote_file = file.remote
        is_active = remote_file.is_uploading_active
        completed = remote_file.is_uploading_completed
        transferred = remote_file.uploaded_size
    total = file.size or file.expected_size
    await tracker.update_progress(
        file_id, transfer_type, transferred, total, is_active, completed
    )


tracker = ProgressTracker()
