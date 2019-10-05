class MirrorListeners:
    def __init__(self, context, update, reply_message):
        self.context = context
        self.update = update
        self.message = update.message
        self.uid = self.message.message_id
        self.reply_message = reply_message

    def onDownloadStarted(self, link: str):
        raise NotImplementedError

    def onDownloadProgress(self, progress_status_list: list, index: int):
        raise NotImplementedError
    
    def onDownloadComplete(self, progress_status_list: list, index: int):
        raise NotImplementedError

    def onDownloadError(self, error: str, progress_status_list: list, index: int):
        raise NotImplementedError

    def onUploadStarted(self, progress_status_list: list, index: int):
        raise NotImplementedError

    def onUploadProgress(self, progress: list, index: int):
        raise NotImplementedError

    def onUploadComplete(self, link: str, progress_status_list: list, index: int):
        raise NotImplementedError

    def onUploadError(self, error: str, progress_status: list, index: int):
        raise NotImplementedError