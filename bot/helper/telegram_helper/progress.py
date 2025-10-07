from asyncio import Event, Lock
from collections import defaultdict


class ProgressTracker:
    def __init__(self):
        self.progress_dict = defaultdict(dict)
        self.completion_events = defaultdict(Event)
        self.locks = defaultdict(Lock)

    async def update_progress(
        self, file_id: int, transferred: int, total: int, is_active: bool
    ):
        async with self.locks[file_id]:
            self.progress_dict[file_id] = {
                "transferred": transferred,
                "total": total,
                "is_active": is_active,
            }
            if transferred >= total > 0:
                self.completion_events[file_id].set()

    def get_progress(self, file_id: int):
        return self.progress_dict.get(
            file_id, {"transferred": 0, "total": 1, "is_active": True}
        )


async def tdlib_file_update(_, update):
    if update["@type"] == "updateFile":
        file = update["file"]
        file_id = file["id"]
        is_download = "is_downloading_active" in file["local"]
        is_active = (
            file["local"]["is_downloading_active"]
            if is_download
            else file["local"]["is_uploading_active"]
        )
        transferred = (
            file["local"]["downloaded_size"]
            if is_download
            else file["local"]["uploaded_size"]
        )
        total = file["size"] or file["expected_size"]

        await tracker.update_progress(file_id, transferred, total, is_active)


tracker = ProgressTracker()
