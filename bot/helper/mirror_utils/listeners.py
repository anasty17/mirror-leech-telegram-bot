class MirrorListeners:
    def __init__(self, context, update):
        self.bot = context
        self.update = update
        self.message = update.message
        self.uid = self.message.message_id

    def onDownloadStarted(self):
        raise NotImplementedError

    def onDownloadProgress(self):
        raise NotImplementedError
    
    def onDownloadComplete(self):
        raise NotImplementedError

    def onDownloadError(self, error: str):
        raise NotImplementedError

    def onUploadStarted(self, progress_status_list: list, index: int):
        raise NotImplementedError

    def onUploadProgress(self, progress: list, index: int):
        raise NotImplementedError

    def onUploadComplete(self, link: str, progress_status_list: list, index: int):
        raise NotImplementedError

    def onUploadError(self, error: str, progress_status: list, index: int):
        raise NotImplementedError