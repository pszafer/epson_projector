"""ESC/VP.net specific errors."""


class EscVpNetException(Exception):
    """Base class for ESC/VP.net exceptions."""


class EscVpNetConnectionError(EscVpNetException):
    """
    Connection error.

    There is an issue with the connection can be a timeout, connection refused, no route to host, etc.
    """


class EscVpNetProtocolStatusException(EscVpNetException):
    """Parent for all protocol status exceptions."""


class EscVpNetBadRequestStatus(EscVpNetProtocolStatusException):
    """Request cannot be understood as its grammar is wrong."""


class EscVpNetUnauthorizedStatus(EscVpNetProtocolStatusException):
    """Password is required. (The client issues a request again with the password added.)"""


class EscVpNetForbiddenStatus(EscVpNetProtocolStatusException):
    """Password is wrong."""


class EscVpNetRequestNotAllowedStatus(EscVpNetProtocolStatusException):
    """Disallowed type request."""


class EscVpNetServiceUnavailableStatus(EscVpNetProtocolStatusException):
    """The projector is BUSY, etc."""


class EscVpNetProtocolVersionNotSupportedStatus(EscVpNetProtocolStatusException):
    """Unsupported version."""


class EscVpNetUnknownStatus(EscVpNetProtocolStatusException):
    """Unknown status code"""
