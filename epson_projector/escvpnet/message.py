from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass, field
from enum import IntEnum, unique

from .headers import HeaderBase, HeaderFactory

_LOGGER = logging.getLogger(__name__)

PROTOCOL_IDENTIFIER = b"ESC/VP.net"
VERSION_1_0 = 0x10  # Protocol version 1.0


@unique
class MessageType(IntEnum):
    _UNKNOWN = -1
    NULL = 0  # reserved
    HELLO = 1
    PASSWORD = 2
    CONNECT = 3

    @classmethod
    def _missing_(cls, value: object) -> MessageType:
        _LOGGER.warning("Unknown value '%s' for %s", value, cls.__name__)
        return cls._UNKNOWN


@unique
class MessageStatus(IntEnum):
    _UNKNOWN = -1
    REQUEST = 0x00
    OK = 0x20
    BAD_REQUEST = 0x40
    UNAUTHORIZED = 0x41  # Password is required
    FORBIDDEN = 0x43  # Password is wrong
    REQUEST_NOT_ALLOWED = (
        0x45  # Request is not allowed in current state (e.g. HELLO on TCP)
    )
    SERVICE_UNAVAILABLE = 0x53  # Projector is BUSY
    PROTOCOL_VERSION_NOT_SUPPORTED = 0x55

    @classmethod
    def _missing_(cls, value: object) -> MessageStatus:
        _LOGGER.warning("Unknown value '%s' for %s", value, cls.__name__)
        return cls._UNKNOWN


@dataclass
class Message:
    """ESC/VP.net message."""

    type_id: MessageType
    status: MessageStatus
    headers: list[HeaderBase] = field(default_factory=list)

    # 10 bytes protocol name (ESC/VP.net),
    # 1 byte version, top nibble major, bottom nibble minor,
    # 1 byte type,
    # 2 reserved bytes,
    # 1 bytes status,
    # 1 byte header count
    # Followed by header count headers
    _FORMAT = "<10s B B H B B"

    @classmethod
    async def from_bytes(cls, data: bytes) -> Message:
        stream = asyncio.StreamReader()
        stream.feed_data(data)
        stream.feed_eof()
        return await cls.from_stream(stream)

    @classmethod
    async def from_stream(cls, stream: asyncio.StreamReader) -> Message:
        data = await stream.readexactly(struct.calcsize(cls._FORMAT))

        unpacked = struct.unpack(cls._FORMAT, data)

        protocol = unpacked[0]
        if protocol != PROTOCOL_IDENTIFIER:
            raise ValueError(f"Unexpected protocol: {protocol!r}")

        version = unpacked[1]
        if version != VERSION_1_0:
            raise ValueError(f"Unsupported protocol version: {version}")

        type_ = MessageType(unpacked[2])

        status = MessageStatus(unpacked[4])

        header_count = unpacked[5]
        headers = []

        for _ in range(header_count):
            if header := await HeaderFactory.from_stream(stream):
                headers.append(header)

        return cls(
            type_id=type_,
            status=status,
            headers=headers,
        )

    def to_bytes(self) -> bytes:
        header_count = len(self.headers) if self.headers else 0

        message = struct.pack(
            self._FORMAT,
            PROTOCOL_IDENTIFIER,
            VERSION_1_0,
            self.type_id.value,
            0,  # reserved
            self.status.value,
            header_count,
        )

        if self.headers:
            for header in self.headers:
                message += header.to_bytes()

        return message
