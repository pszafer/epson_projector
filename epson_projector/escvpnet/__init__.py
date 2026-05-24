"""
ESC/VP.net protocol implementation based on the document found here:
https://www.epson.com.au/d/pub/epson/techtips/escvp.netmanual_e_f.pdf
"""

from __future__ import annotations

from .error import (
    BadRequestError,
    BusyError,
    EscVpNetException,
    PasswordRequiredError,
    PasswordWrongError,
    ProtocolVersionNotSupportedError,
    RequestNotAllowedError,
    UnknownStatusError,
)
from .escvp21_communication import EscVp21Communication
from .escvpnet import EscVpNet

__all__ = [
    "BadRequestError",
    "BusyError",
    "EscVpNet",
    "EscVp21Communication",
    "EscVpNetException",
    "PasswordRequiredError",
    "PasswordWrongError",
    "RequestNotAllowedError",
    "ProtocolVersionNotSupportedError",
    "UnknownStatusError",
]
