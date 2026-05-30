class InvalidLinkException(Exception):
    """Raised when provided URL is invalid"""


class SongLinkErrorException(Exception):
    """Raised when song.link returns error code"""


class UnsupportedDataTypeException(Exception):
    """Raised when song.link returns an unsupported data type"""
