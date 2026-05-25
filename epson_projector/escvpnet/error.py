"""ESC/VP.net specific errors."""


class EscVpNetException(Exception):
    """Base class for ESC/VP.net exceptions."""


class ConnectionError(EscVpNetException):
    """
    Connection error.

    There is an issue with the connection can be a timeout, connection refused, no route to host, etc.
    """


class ProtocolStatusException(EscVpNetException):
    """Parent for all protocol status exceptions."""


class BadRequestStatus(ProtocolStatusException):
    """Request cannot be understood as its grammar is wrong."""


class UnauthorizedStatus(ProtocolStatusException):
    """Password is required. (The client issues a request again with the password added.)"""


class ForbiddenStatus(ProtocolStatusException):
    """Password is wrong."""


class RequestNotAllowedStatus(ProtocolStatusException):
    """Disallowed type request."""


class ServiceUnavailableStatus(ProtocolStatusException):
    """The projector is BUSY, etc."""


class ProtocolVersionNotSupportedStatus(ProtocolStatusException):
    """Unsupported version."""


class UnknownStatus(ProtocolStatusException):
    """Unknown status code"""
