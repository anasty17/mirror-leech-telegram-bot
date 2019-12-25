# Generic status class. All other status classes must inherit this class


class Status:

    def progress(self):
        """
        Calculates the progress of the mirror (upload or download)
        :return: progress in percentage
        """
        raise NotImplementedError

    def speed(self):
        """:return: speed in bytes per second"""
        raise NotImplementedError

    def name(self):
        """:return name of file/directory being processed"""
        raise NotImplementedError

    def path(self):
        """:return path of the file/directory"""
        raise NotImplementedError

    def size(self):
        """:return Size of file folder"""
        raise NotImplementedError

    def eta(self):
        """:return ETA of the process to complete"""
        raise NotImplementedError

    def status(self):
        """:return String describing what is the object of this class will be tracking (upload/download/something
        else) """
        raise NotImplementedError

    def processed_bytes(self):
        """:return The size of file that has been processed (downloaded/uploaded/archived)"""
        raise NotImplementedError
