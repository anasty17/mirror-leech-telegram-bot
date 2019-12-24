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

    def onUploadStarted(self):
        raise NotImplementedError

    def onUploadProgress(self):
        raise NotImplementedError

    def onUploadComplete(self, link: str):
        raise NotImplementedError

    def onUploadError(self, error: str):
        raise NotImplementedError
