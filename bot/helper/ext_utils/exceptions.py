class DriveAuthError(Exception):
    pass


class KillThreadException(Exception):
    """ Custom Exception class for killing thread as soon as they aren't needed"""

    def __init__(self, message, error=None):
        super().__init__(message)
        self.error = error


class DownloadCancelled(Exception):

    def __init__(self, message, error=None):
        super().__init__(message)
        self.error = error
