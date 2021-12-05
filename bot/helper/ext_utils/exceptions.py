class DirectDownloadLinkException(Exception):
    """Not method found for extracting direct download link from the http link"""
    pass


class DirectTorrentMagnetException(Exception):
    """Not method found for scrape torrent magnet from the torrent site link"""
    pass


class NotSupportedExtractionArchive(Exception):
    """The archive format use is trying to extract is not supported"""
    pass
