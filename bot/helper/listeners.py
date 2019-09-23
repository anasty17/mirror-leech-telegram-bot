class MirrorListeners:
    def __init__(self, context, update, reply_message):
        self.context = context
        self.update = update
        self.reply_message = reply_message

    def onDownloadStarted(self, link: str):
        raise NotImplementedError

    def onDownloadProgress(self, progress_str_list: list):
        raise NotImplementedError
    
    def onDownloadComplete(self, download):
        raise NotImplementedError

    def onDownloadError(self, error: str):
        raise NotImplementedError

    def onUploadStarted(self, filename: str):
        raise NotImplementedError

    def onUploadComplete(self, link: str, file_name: str):
        raise NotImplementedError

    def onUploadError(self, error: str):
        raise NotImplementedError