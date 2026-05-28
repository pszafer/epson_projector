from __future__ import annotations

import asyncio
import logging
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum, unique
from typing import final


_LOGGER = logging.getLogger(__name__)


@unique
class HeaderId(IntEnum):
    UNKNOWN = -1
    NULL = 0  # reserved
    PASSWORD = 1
    NEW_PASSWORD = 2
    PROJECTOR_NAME = 3
    IM_TYPE = 4
    PROJECTOR_COMMAND_TYPE = 5

    @classmethod
    def _missing_(cls, value: object) -> HeaderId:
        _LOGGER.warning("Unknown value '%s' for %s", value, cls.__name__)
        return cls.UNKNOWN


@dataclass
class RawHeaderData:
    header_id: HeaderId
    attribute_value: int
    info: bytes  # Info is defined as STR in the spec, but for projectorname it can have different encodings, so keeping it as bytes and decode in the specific header class

    _FORMAT = "<B B 16s"

    @staticmethod
    def size() -> int:
        return struct.calcsize(RawHeaderData._FORMAT)

    @classmethod
    def from_bytes(cls, data: bytes) -> "RawHeaderData":
        unpacked = struct.unpack(cls._FORMAT, data)
        return cls(
            header_id=HeaderId(unpacked[0]),
            attribute_value=unpacked[1],
            info=unpacked[2].rstrip(
                b"\x00"
            ),  # Strip trailing null bytes, here to not bother the specific header classes with that
        )

    def to_bytes(self) -> bytes:
        return struct.pack(
            self._FORMAT,
            self.header_id.value,
            self.attribute_value,
            self.info,
        )


class HeaderBase(ABC):
    @final
    @staticmethod
    def size() -> int:
        return RawHeaderData.size()

    @classmethod
    @abstractmethod
    def id(cls) -> HeaderId:
        pass

    @classmethod
    @abstractmethod
    def from_raw_header(cls, raw_header: RawHeaderData) -> "HeaderBase":
        pass

    @abstractmethod
    def to_bytes(self) -> bytes:
        pass


class PasswordHeader(HeaderBase):
    def __init__(self, password: str):
        self._password = password

    @classmethod
    def id(cls) -> HeaderId:
        return HeaderId.PASSWORD

    @classmethod
    def from_raw_header(cls, raw_header: RawHeaderData) -> "HeaderBase":
        assert raw_header.header_id == cls.id(), (
            f"Unexpected header id: {raw_header.header_id}"
        )
        return cls(password=raw_header.info.decode("ascii"))

    def to_bytes(self) -> bytes:
        return RawHeaderData(
            header_id=self.id(),
            attribute_value=1 if self._password else 0,
            info=self._password.encode("ascii"),
        ).to_bytes()


class NewPasswordHeader(PasswordHeader):
    @classmethod
    def id(cls) -> HeaderId:
        return HeaderId.NEW_PASSWORD


@unique
class CharacterEncoding(IntEnum):
    UNKNOWN = -1
    NULL = 0
    ASCII = 1
    SHIFT_JIS = 2  # reserved
    EUC_JP = 3  # reserved

    @classmethod
    def _missing_(cls, value: object) -> CharacterEncoding:
        _LOGGER.warning("Unknown value '%s' for %s", value, cls.__name__)
        return cls.UNKNOWN


class ProjectorNameHeader(HeaderBase):
    def __init__(self, projector_name: str):
        self._projector_name = projector_name

    @property
    def projector_name(self) -> str:
        return self._projector_name

    @classmethod
    def id(cls) -> HeaderId:
        return HeaderId.PROJECTOR_NAME

    @classmethod
    def from_raw_header(cls, raw_header: RawHeaderData) -> "HeaderBase":
        assert raw_header.header_id == cls.id(), (
            f"Unexpected header id: {raw_header.header_id}"
        )

        match CharacterEncoding(raw_header.attribute_value):
            case CharacterEncoding.ASCII:
                projector_name = raw_header.info.decode("ascii")
            case CharacterEncoding.SHIFT_JIS:
                projector_name = raw_header.info.decode("shift_jis")
            case CharacterEncoding.EUC_JP:
                projector_name = raw_header.info.decode("euc_jp")
            case _:
                raise NotImplementedError(
                    f"Support for text encoding: {raw_header.attribute_value} is not implemented"
                )

        return cls(projector_name)

    def to_bytes(self) -> bytes:
        return RawHeaderData(
            header_id=self.id(),
            attribute_value=CharacterEncoding.ASCII.value
            if self._projector_name
            else CharacterEncoding.NULL.value,
            info=self._projector_name.encode("ascii"),
        ).to_bytes()


# ImType is an int because the mapping in the documentation is unclear
# if the values are hex or decimal. It seems decimal, but there is "0C" for Type D
# Next to that the use of this information is unknown and the list seems out of date
# because LS11000W returns 56 which is unmapped. So keeping it simple.
class ImTypeHeader(HeaderBase):
    def __init__(self, im_type: int):
        self._im_type = im_type

    @property
    def im_type(self) -> int:
        return self._im_type

    @classmethod
    def id(cls) -> HeaderId:
        return HeaderId.IM_TYPE

    @classmethod
    def from_raw_header(cls, raw_header: RawHeaderData) -> "HeaderBase":
        assert raw_header.header_id == cls.id(), (
            f"Unexpected header id: {raw_header.header_id}"
        )
        return cls(im_type=raw_header.attribute_value)

    def to_bytes(self) -> bytes:
        return RawHeaderData(
            header_id=self.id(),
            attribute_value=self._im_type,
            info=b"",
        ).to_bytes()


@unique
class CommandType(IntEnum):
    UNKNOWN = -1
    ESC_VP_LEVEL_6 = 0x16  # Reserved
    ESC_VP21_V1_0 = 0x21

    @classmethod
    def _missing_(cls, value: object) -> CommandType:
        _LOGGER.warning("Unknown value '%s' for %s", value, cls.__name__)
        return cls.UNKNOWN


class ProjectorCommandTypeHeader(HeaderBase):
    def __init__(self, command_type: CommandType):
        self._command_type = command_type

    @property
    def command_type(self) -> CommandType:
        return self._command_type

    @classmethod
    def id(cls) -> HeaderId:
        return HeaderId.PROJECTOR_COMMAND_TYPE

    @classmethod
    def from_raw_header(cls, raw_header: RawHeaderData) -> HeaderBase:
        assert raw_header.header_id == cls.id(), (
            f"Unexpected header id: {raw_header.header_id}"
        )
        return cls(command_type=CommandType(raw_header.attribute_value))

    def to_bytes(self) -> bytes:
        return RawHeaderData(
            header_id=self.id(),
            attribute_value=self._command_type.value,
            info=b"",
        ).to_bytes()


class HeaderFactory:
    @staticmethod
    def from_bytes(data: bytes) -> HeaderBase | None:
        raw_header = RawHeaderData.from_bytes(data)

        if raw_header.header_id == PasswordHeader.id():
            return PasswordHeader.from_raw_header(raw_header)
        elif raw_header.header_id == NewPasswordHeader.id():
            return NewPasswordHeader.from_raw_header(raw_header)
        elif raw_header.header_id == ProjectorNameHeader.id():
            return ProjectorNameHeader.from_raw_header(raw_header)
        elif raw_header.header_id == ImTypeHeader.id():
            return ImTypeHeader.from_raw_header(raw_header)
        elif raw_header.header_id == ProjectorCommandTypeHeader.id():
            return ProjectorCommandTypeHeader.from_raw_header(raw_header)

        _LOGGER.warning("Header with id {%s} is not supported", raw_header.header_id)
        return None

    @staticmethod
    async def from_stream(stream: asyncio.StreamReader) -> HeaderBase | None:
        data = await stream.readexactly(RawHeaderData.size())
        return HeaderFactory.from_bytes(data)
