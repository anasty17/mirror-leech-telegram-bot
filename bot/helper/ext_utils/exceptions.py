class DirectDownloadLinkException(Exception):
    """Not method found for extracting direct download link from the http link"""
    pass


class NotSupportedExtractionArchive(Exception):
    """The archive format use is trying to extract is not supported"""
    pass
