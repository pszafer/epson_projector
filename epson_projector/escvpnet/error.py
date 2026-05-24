"""ESC/VP.net specific errors."""

class EscVpNetException(Exception):
    """Base class for ESC/VP.net exceptions."""


class BadRequestError(EscVpNetException):
    """Bad request response."""


class PasswordRequiredError(EscVpNetException):
    """Password is required response."""


class PasswordWrongError(EscVpNetException):
    """Password is wrong response."""


class RequestNotAllowedError(EscVpNetException):
    """Request is not allowed in current state response."""


class BusyError(EscVpNetException):
    """Projector is busy response."""


class ProtocolVersionNotSupportedError(EscVpNetException):
    """Protocol version not supported response."""


class UnknownStatusError(EscVpNetException):
    """Unknown status response."""