class Message:
    pass

class Download:
    def __init__(self, gid, download):
        self.isDownloading = download.is_complete
        self.gid = gid
        self.download = download
