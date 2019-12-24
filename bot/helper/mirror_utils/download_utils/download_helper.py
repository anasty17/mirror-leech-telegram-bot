# An abstract class which will be inherited by the tool specific classes like aria2_helper or mega_download_helper
import threading


class MethodNotImplementedError(NotImplementedError):
    def __init__(self):
        super(self, 'Not implemented method')


class DownloadHelper:
    def __init__(self):
        self.name = ''  # Name of the download; empty string if no download has been started
        self.size = 0.0  # Size of the download
        self.downloaded_bytes = 0.0  # Bytes downloaded
        self.speed = 0.0  # Download speed in bytes per second
        self.progress = 0.0
        self.progress_string = '0.00%'
        self.eta = 0  # Estimated time of download complete
        self.eta_string = '0s' # A listener class which have event callbacks
        self._resource_lock = threading.Lock()

    def add_download(self, link: str, path):
        raise MethodNotImplementedError

    def cancel_download(self):
        # Returns None if successfully cancelled, else error string
        raise MethodNotImplementedError
