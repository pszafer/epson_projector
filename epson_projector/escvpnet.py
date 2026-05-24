"""ESC/VP.net protocol"""

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
from enum import IntEnum, unique
import logging
import struct

PROTOCOL_IDENTIFIER = b"ESC/VP.net"
VERSION_1_0 = 0x10  # Protocol version 1.0

COLON = b":"

_LOGGER = logging.getLogger(__name__)


class EscVp21Communication:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer

    async def raw_send(self, payload: str) -> str:
        if self._writer and not self._writer.is_closing():
            self._writer.write(payload.encode("ascii"))
            await self._writer.drain()
            response = await self._reader.readuntil(COLON)
            return response[:-1].decode("ascii")  # remove trailing colon

        raise RuntimeError("ESC/VP.net session is not connected")

    async def get(self, command: str) -> str:
        response = await self.raw_send(command + "?\r")
        if response == "ERR":
            raise RuntimeError(f"Error response to command {command}")
        return response

    async def set(self, command: str, value: str) -> None:
        response = await self.raw_send(f"{command} {value}\r")
        if response == "ERR":
            raise RuntimeError(
                f"Error response to command {command} with value {value}"
            )

    def close(self):
        if self._writer and not self._writer.is_closing():
            _LOGGER.debug("Closing ESC/VP.net session")
            self._writer.close()

    @property
    def is_connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()


@unique
class EscVpNetMessageType(IntEnum):
    NULL = 0  # reserved
    HELLO = 1
    PASSWORD = 2
    CONNECT = 3


@unique
class EscVpNetMessageStatus(IntEnum):
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


@unique
class EscVpNetHeaderId(IntEnum):
    NULL = 0  # reserved
    PASSWORD = 1
    NEW_PASSWORD = 2
    PROJECTOR_NAME = 3
    IM_TYPE = 4
    PROJECTOR_COMMAND_TYPE = 5


@dataclass
class EscVpNetRawHeaderData:
    header_id: EscVpNetHeaderId
    attribute_value: int
    info: str

    _FORMAT = "<B B 16s"

    @staticmethod
    def size() -> int:
        return struct.calcsize(EscVpNetRawHeaderData._FORMAT)

    @classmethod
    def from_bytes(cls, data: bytes) -> "EscVpNetRawHeaderData":
        unpacked = struct.unpack(cls._FORMAT, data)
        return cls(
            header_id=EscVpNetHeaderId(unpacked[0]),
            attribute_value=unpacked[1],
            info=unpacked[2].decode("ascii").rstrip("\x00"),
        )

    def to_bytes(self) -> bytes:
        return struct.pack(
            self._FORMAT,
            self.header_id.value,
            self.attribute_value,
            self.info.encode("ascii"),
        )


class EscVpNetHeaderBase(ABC):

    @staticmethod
    def size() -> int:
        return EscVpNetRawHeaderData.size()

    @classmethod
    @abstractmethod
    def id(cls) -> EscVpNetHeaderId:
        raise NotImplementedError("Header id is not implemented")

    @classmethod
    @abstractmethod
    def _from_raw_header(cls, raw_header: EscVpNetRawHeaderData) -> "EscVpNetHeaderBase":
        raise NotImplementedError("Method _from_raw_header is not implemented")

    @abstractmethod
    def to_bytes(self) -> bytes:
        raise NotImplementedError("Method to_bytes is not implemented")

    @classmethod
    async def from_stream(cls, stream: asyncio.StreamReader) -> "EscVpNetHeaderBase":
        data = await stream.readexactly(EscVpNetRawHeaderData.size())
        return cls._from_raw_header(EscVpNetRawHeaderData.from_bytes(data))


class EscVpNetPasswordHeader(EscVpNetHeaderBase):

    def __init__(self, password: str):
        self._password = password

    @classmethod
    def id(cls) -> EscVpNetHeaderId:
        return EscVpNetHeaderId.PASSWORD

    @classmethod
    def _from_raw_header(cls, raw_header: EscVpNetRawHeaderData) -> "EscVpNetHeaderBase":
        assert (
            raw_header.header_id == cls.id()
        ), f"Unexpected header id: {raw_header.header_id}"
        return cls(password=raw_header.info)

    def to_bytes(self) -> bytes:
        return EscVpNetRawHeaderData(
            header_id=self.id(),
            attribute_value=1 if self._password else 0,
            info=self._password,
        ).to_bytes()

class EscVpNetNewPasswordHeader(EscVpNetPasswordHeader):

    @classmethod
    def id(cls) -> EscVpNetHeaderId:
        return EscVpNetHeaderId.NEW_PASSWORD


class EscVpNetProjectorNameHeader(EscVpNetHeaderBase):

    def __init__(self, projector_name: str):
        self._projector_name = projector_name

    @property
    def projector_name(self) -> str:
        return self._projector_name

    @classmethod
    def id(cls) -> EscVpNetHeaderId:
        return EscVpNetHeaderId.PROJECTOR_NAME

    @classmethod
    def _from_raw_header(cls, raw_header: EscVpNetRawHeaderData) -> "EscVpNetHeaderBase":
        assert (
            raw_header.header_id == cls.id()
        ), f"Unexpected header id: {raw_header.header_id}"
        if raw_header.attribute_value > 1:
            raise NotImplementedError(f"Support for encoding: {raw_header.attribute_value} is not implemented")
        return cls(projector_name=raw_header.info)

    def to_bytes(self) -> bytes:
        return EscVpNetRawHeaderData(
            header_id=self.id(),
            attribute_value=1 if self._projector_name else 0,
            info=self._projector_name,
        ).to_bytes()

# ImType is currently an int because the mapping in the documentation is unclear
# if the values are hex or decimal. It seems decimal, but there is "0C" for Type D
# Next to that the use of this information is unknown.
class EscVpNetImTypeHeader(EscVpNetHeaderBase):

    def __init__(self, im_type: int):
        self._im_type = im_type

    @property
    def im_type(self) -> int:
        return self._im_type

    @classmethod
    def id(cls) -> EscVpNetHeaderId:
        return EscVpNetHeaderId.IM_TYPE

    @classmethod
    def _from_raw_header(cls, raw_header: EscVpNetRawHeaderData) -> "EscVpNetHeaderBase":
        assert (
            raw_header.header_id == cls.id()
        ), f"Unexpected header id: {raw_header.header_id}"
        return cls(im_type=raw_header.attribute_value)

    def to_bytes(self) -> bytes:
        return EscVpNetRawHeaderData(
            header_id=self.id(),
            attribute_value=self._im_type,
            info="",
        ).to_bytes()

@unique
class CommandType(IntEnum):
    ESC_VP_LEVEL_6 = 0x16  # Reserved
    ESCC_VP21_V1_0 = 0x21

class EscVpNetProjectorCommandTypeHeader(EscVpNetHeaderBase):

    def __init__(self, command_type: CommandType):
        self._command_type = command_type

    @property
    def command_type(self) -> CommandType:
        return self._command_type

    @classmethod
    def id(cls) -> EscVpNetHeaderId:
        return EscVpNetHeaderId.PROJECTOR_COMMAND_TYPE

    @classmethod
    def _from_raw_header(cls, raw_header: EscVpNetRawHeaderData) -> "EscVpNetHeaderBase":
        assert (
            raw_header.header_id == cls.id()
        ), f"Unexpected header id: {raw_header.header_id}"
        return cls(command_type=CommandType(raw_header.attribute_value))

    def to_bytes(self) -> bytes:
        return EscVpNetRawHeaderData(
            header_id=self.id(),
            attribute_value=self._command_type.value,
            info="",
        ).to_bytes()

class EscVpNetHeaderFactory:

    @staticmethod
    def from_bytes(data: bytes) -> EscVpNetHeaderBase | None:
        raw_header = EscVpNetRawHeaderData.from_bytes(data)

        if raw_header.header_id == EscVpNetPasswordHeader.id():
            return EscVpNetPasswordHeader._from_raw_header(raw_header)
        elif raw_header.header_id == EscVpNetNewPasswordHeader.id():
            return EscVpNetNewPasswordHeader._from_raw_header(raw_header)
        elif raw_header.header_id == EscVpNetProjectorNameHeader.id():
            return EscVpNetProjectorNameHeader._from_raw_header(raw_header)
        elif raw_header.header_id == EscVpNetImTypeHeader.id():
            return EscVpNetImTypeHeader._from_raw_header(raw_header)
        elif raw_header.header_id == EscVpNetProjectorCommandTypeHeader.id():
            return EscVpNetProjectorCommandTypeHeader._from_raw_header(raw_header)

        logging.warning(
            "Header with id {%s} is not supported", raw_header.header_id
        )
        return None

    @staticmethod
    async def from_stream(stream: asyncio.StreamReader) -> EscVpNetHeaderBase | None:
        data = await stream.readexactly(EscVpNetRawHeaderData.size())
        return EscVpNetHeaderFactory.from_bytes(data)


@dataclass
class EscVpNetMessage:
    type_id: EscVpNetMessageType
    status: EscVpNetMessageStatus
    headers: list[EscVpNetHeaderBase] = field(default_factory=list)

    """
    ESC/VP.net message.
    
    10 bytes protocol name (ESC/VP.net), 
    1 byte version, 
    1 byte type, 
    2 reserved bytes, 
    1 bytes status,
    1 byte header count
    Followed by header count headers
    """
    _FORMAT = "<10s B B H B B"

    @classmethod
    async def from_stream(cls, stream: asyncio.StreamReader) -> "EscVpNetMessage":
        data = await stream.readexactly(struct.calcsize(cls._FORMAT))

        unpacked = struct.unpack(cls._FORMAT, data)

        protocol = unpacked[0]
        assert protocol == PROTOCOL_IDENTIFIER, f"Unexpected protocol: {protocol}"

        version = unpacked[1]
        assert version == VERSION_1_0, f"Unsupported protocol version: {version}"

        header_count = unpacked[5]
        headers = []

        for _ in range(header_count):
            if header := await EscVpNetHeaderFactory.from_stream(stream):
                headers.append(header)

        return cls(
            type_id=EscVpNetMessageType(unpacked[2]),
            status=EscVpNetMessageStatus(unpacked[4]),
            headers=headers,
        )

    def to_bytes(self) -> bytes:
        header_count = len(self.headers) if self.headers is not None else 0

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


def raise_from_status(status: EscVpNetMessageStatus):
    if status == EscVpNetMessageStatus.BAD_REQUEST:
        raise ValueError("Bad request")
    elif status == EscVpNetMessageStatus.UNAUTHORIZED:
        raise PermissionError("Password is required")
    elif status == EscVpNetMessageStatus.FORBIDDEN:
        raise PermissionError("Password is wrong")
    elif status == EscVpNetMessageStatus.REQUEST_NOT_ALLOWED:
        raise RuntimeError("Request is not allowed in current state")
    elif status == EscVpNetMessageStatus.SERVICE_UNAVAILABLE:
        raise RuntimeError("Projector is busy")
    elif status == EscVpNetMessageStatus.PROTOCOL_VERSION_NOT_SUPPORTED:
        raise RuntimeError("Protocol version not supported")
    raise RuntimeError(f"Unknown status: {status}")


class EscVpNet:

    def __init__(self, host, port=3629):
        self._host = host
        self._port = port

    async def _communicate(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        message: EscVpNetMessage,
        close_after_response=True,
    ) -> EscVpNetMessage:
        try:
            writer.write(message.to_bytes())
            await writer.drain()

            response_message = await EscVpNetMessage.from_stream(reader)
            return response_message
        finally:
            if close_after_response and writer and not writer.is_closing():
                writer.close()
                await writer.wait_closed()

    # Session-less mode commands

    async def hello(self) -> str:
        raise NotImplementedError("HELLO command is not implemented yet")

    # Session mode commands

    async def password(self, password: str | None = None, new_password: str | None = None) -> bool:
        """
        Password request/response. Allows checking and changing of password.
        
        When `password` is provided, it checks if the password is correct.
        When `new_password` is provided, the password will be changed.
        """
        try:
            async with asyncio.timeout(10):
                reader, writer = await asyncio.open_connection(
                    host=self._host, port=self._port
                )

                headers:list[EscVpNetHeaderBase] = []
                if password is not None:
                    headers.append(EscVpNetPasswordHeader(password=password))
                if new_password is not None:
                    headers.append(EscVpNetNewPasswordHeader(password=new_password))

                writer.write(
                    EscVpNetMessage(
                        type_id=EscVpNetMessageType.PASSWORD,
                        status=EscVpNetMessageStatus.REQUEST,
                        headers=headers
                    ).to_bytes()
                )
                await writer.drain()

                response_message = await EscVpNetMessage.from_stream(reader)

                if response_message.status == EscVpNetMessageStatus.OK:
                    return True
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error while opening ESC/VP.net session")
        except ConnectionRefusedError:
            _LOGGER.error("Connection refused while opening ESC/VP.net session")
        except asyncio.IncompleteReadError:
            _LOGGER.error("Connecton closed before reading complete response")
        except OSError as err:
            _LOGGER.error("Network error while opening ESC/VP.net session: %s", err)
        finally:
            if writer and not writer.is_closing():
                writer.close()

        return False

    async def password_update(self, old_password: str, new_password: str) -> None:
        raise NotImplementedError("Password update is not implemented yet")

    async def connect(self, password: str | None = None) -> EscVp21Communication:
        connected = False
        try:
            async with asyncio.timeout(10):
                reader, writer = await asyncio.open_connection(
                    host=self._host, port=self._port
                )

                response_message = await self._communicate(
                    reader,
                    writer,
                    EscVpNetMessage(
                        type_id=EscVpNetMessageType.CONNECT,
                        status=EscVpNetMessageStatus.REQUEST,
                        headers=(
                            [EscVpNetPasswordHeader(password=password)]
                            if password is not None
                            else []
                        ),
                    ),
                    close_after_response=False,
                )

                if response_message.status == EscVpNetMessageStatus.OK:
                    _LOGGER.info("ESC/VP.net session open")
                    connected = True
                    return EscVp21Communication(reader=reader, writer=writer)

                raise_from_status(response_message.status)

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error while opening ESC/VP.net session")
        except ConnectionRefusedError:
            _LOGGER.error("Connection refused while opening ESC/VP.net session")
        except asyncio.IncompleteReadError:
            _LOGGER.error("Connecton closed before reading complete response")
        except OSError as err:
            _LOGGER.error("Network error while opening ESC/VP.net session: %s", err)
        finally:
            if not connected and writer is not None and not writer.is_closing():
                writer.close()
                await writer.wait_closed()

        raise RuntimeError("Failed to open ESC/VP.net session")


if __name__ == "__main__":

    async def main():
        escvpnet = EscVpNet(host=args.host)
        escvp21 = await escvpnet.connect("new_password")

        if escvp21:
            try:
                response = await escvp21.get("SNO")
                print(f"SNO: {response}")
                response = await escvp21.get("PWR")
                print(f"PWR: {response}")
                response = await escvp21.get("LAMP")
                print(f"LAMP: {response}")
                await escvp21.set("PWR", "OFF")
            finally:
                escvp21.close()

        ok = await escvpnet.password()
        print(f"Can connect: {ok}")
        ok = await escvpnet.password(None, "new_password")
        print(f"Can change password: {ok}")

    import argparse

    parser = argparse.ArgumentParser(description="Test ESC/VP.net connection")
    parser.add_argument("host", help="IP address of the projector")
    parser.add_argument(
        "--loglevel",
        help="Set the logging level. Default is INFO.",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel)

    asyncio.run(main())
