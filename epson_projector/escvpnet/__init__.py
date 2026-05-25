"""
ESC/VP.net protocol implementation based on the document found here:
https://www.epson.com.au/d/pub/epson/techtips/escvp.netmanual_e_f.pdf
"""

from __future__ import annotations

from .error import (
    BadRequestStatus,
    ServiceUnavailableStatus,
    EscVpNetException,
    ProtocolVersionNotSupportedStatus,
    RequestNotAllowedStatus,
    UnauthorizedStatus,
    ForbiddenStatus,
    UnknownStatus,
)
from .escvp21_communication import EscVp21Communication
from .escvpnet import EscVpNet

__all__ = [
    "BadRequestStatus",
    "ServiceUnavailableStatus",
    "EscVpNet",
    "EscVp21Communication",
    "EscVpNetException",
    "BadRequestStatus",
    "ServiceUnavailableStatus",
    "UnauthorizedStatus",
    "ForbiddenStatus",
    "ProtocolVersionNotSupportedStatus",
    "RequestNotAllowedStatus",
    "UnknownStatus",
]
