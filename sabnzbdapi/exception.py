from httpx import RequestError, DecodingError


class APIError(Exception):
    """Base error for all exceptions from this Client."""


class APIConnectionError(RequestError, APIError):
    """Base class for all communications errors including HTTP errors."""


class LoginFailed(DecodingError, APIConnectionError):
    """This can technically be raised with any request since log in may be attempted for
    any request and could fail."""


class NotLoggedIn(APIConnectionError):
    """Raised when login is not successful."""
