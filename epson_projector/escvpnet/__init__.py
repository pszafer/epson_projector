"""
ESC/VP.net protocol implementation based on the document found here:
https://www.epson.com.au/d/pub/epson/techtips/escvp.netmanual_e_f.pdf
"""

from __future__ import annotations

from .error import (
    EscVpNetBadRequestStatus,
    EscVpNetServiceUnavailableStatus,
    EscVpNetException,
    EscVpNetProtocolVersionNotSupportedStatus,
    EscVpNetRequestNotAllowedStatus,
    EscVpNetUnauthorizedStatus,
    EscVpNetForbiddenStatus,
    EscVpNetUnknownStatus,
)
from .escvp21_communication import EscVp21Communication
from .escvpnet import EscVpNet

__all__ = [
    "EscVpNetBadRequestStatus",
    "EscVpNetServiceUnavailableStatus",
    "EscVpNet",
    "EscVp21Communication",
    "EscVpNetException",
    "EscVpNetUnauthorizedStatus",
    "EscVpNetForbiddenStatus",
    "EscVpNetProtocolVersionNotSupportedStatus",
    "EscVpNetRequestNotAllowedStatus",
    "EscVpNetUnknownStatus",
]
