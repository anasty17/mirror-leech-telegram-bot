class DriveAuthError(Exception):
    pass

# Custom Exception class for killing thread as soon as they aren't needed
class KillThreadException(Exception):
    def __init__(self, message, error=None):
        super().__init__(message)
        self.error = error
