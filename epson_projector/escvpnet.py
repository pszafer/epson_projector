"""
ESC/VP.net protocol implementation based on the document found here:
https://www.epson.com.au/d/pub/epson/techtips/escvp.netmanual_e_f.pdf
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
from enum import IntEnum, unique
import logging
import struct

PROTOCOL_IDENTIFIER = b"ESC/VP.net"
VERSION_1_0 = 0x10  # Protocol version 1.0

ESC_VPNET_PORT = 3629

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
class MessageType(IntEnum):
    UNKNOWN = -1
    NULL = 0  # reserved
    HELLO = 1
    PASSWORD = 2
    CONNECT = 3

    @classmethod
    def _missing_(cls, value: object) -> MessageType:
        _LOGGER.warning("Unknown value '%s' for %s", value, cls.__name__)
        return cls.UNKNOWN


@unique
class MessageStatus(IntEnum):
    UNKNOWN = -1
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
        return cls.UNKNOWN


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
    info: str

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
            info=unpacked[2].decode("ascii").rstrip("\x00"),
        )

    def to_bytes(self) -> bytes:
        return struct.pack(
            self._FORMAT,
            self.header_id.value,
            self.attribute_value,
            self.info.encode("ascii"),
        )


class HeaderBase(ABC):

    @staticmethod
    def size() -> int:
        return RawHeaderData.size()

    @classmethod
    @abstractmethod
    def id(cls) -> HeaderId:
        raise NotImplementedError("Header id is not implemented")

    @classmethod
    @abstractmethod
    def _from_raw_header(
        cls, raw_header: RawHeaderData
    ) -> "HeaderBase":
        raise NotImplementedError("Method _from_raw_header is not implemented")

    @abstractmethod
    def to_bytes(self) -> bytes:
        raise NotImplementedError("Method to_bytes is not implemented")

    @classmethod
    async def from_stream(cls, stream: asyncio.StreamReader) -> "HeaderBase":
        data = await stream.readexactly(RawHeaderData.size())
        return cls._from_raw_header(RawHeaderData.from_bytes(data))


class PasswordHeader(HeaderBase):

    def __init__(self, password: str):
        self._password = password

    @classmethod
    def id(cls) -> HeaderId:
        return HeaderId.PASSWORD

    @classmethod
    def _from_raw_header(
        cls, raw_header: RawHeaderData
    ) -> "HeaderBase":
        assert (
            raw_header.header_id == cls.id()
        ), f"Unexpected header id: {raw_header.header_id}"
        return cls(password=raw_header.info)

    def to_bytes(self) -> bytes:
        return RawHeaderData(
            header_id=self.id(),
            attribute_value=1 if self._password else 0,
            info=self._password,
        ).to_bytes()


class NewPasswordHeader(PasswordHeader):

    @classmethod
    def id(cls) -> HeaderId:
        return HeaderId.NEW_PASSWORD


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
    def _from_raw_header(
        cls, raw_header: RawHeaderData
    ) -> "HeaderBase":
        assert (
            raw_header.header_id == cls.id()
        ), f"Unexpected header id: {raw_header.header_id}"
        if raw_header.attribute_value > 1:
            raise NotImplementedError(
                f"Support for text encoding: {raw_header.attribute_value} is not implemented"
            )
        return cls(projector_name=raw_header.info)

    def to_bytes(self) -> bytes:
        return RawHeaderData(
            header_id=self.id(),
            attribute_value=1 if self._projector_name else 0,
            info=self._projector_name,
        ).to_bytes()


# ImType is currently an int because the mapping in the documentation it is unclear
# if the values are hex or decimal. It seems decimal, but there is "0C" for Type D
# Next to that the use of this information is unknown and the list seems out of date
# because LS11000W returns 56 which is unmapped.
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
    def _from_raw_header(
        cls, raw_header: RawHeaderData
    ) -> "HeaderBase":
        assert (
            raw_header.header_id == cls.id()
        ), f"Unexpected header id: {raw_header.header_id}"
        return cls(im_type=raw_header.attribute_value)

    def to_bytes(self) -> bytes:
        return RawHeaderData(
            header_id=self.id(),
            attribute_value=self._im_type,
            info="",
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
    def _from_raw_header(
        cls, raw_header: RawHeaderData
    ) -> HeaderBase:
        assert (
            raw_header.header_id == cls.id()
        ), f"Unexpected header id: {raw_header.header_id}"
        return cls(command_type=CommandType(raw_header.attribute_value))

    def to_bytes(self) -> bytes:
        return RawHeaderData(
            header_id=self.id(),
            attribute_value=self._command_type.value,
            info="",
        ).to_bytes()


class HeaderFactory:

    @staticmethod
    def from_bytes(data: bytes) -> HeaderBase | None:
        raw_header = RawHeaderData.from_bytes(data)

        if raw_header.header_id == PasswordHeader.id():
            return PasswordHeader._from_raw_header(raw_header)
        elif raw_header.header_id == NewPasswordHeader.id():
            return NewPasswordHeader._from_raw_header(raw_header)
        elif raw_header.header_id == ProjectorNameHeader.id():
            return ProjectorNameHeader._from_raw_header(raw_header)
        elif raw_header.header_id == ImTypeHeader.id():
            return ImTypeHeader._from_raw_header(raw_header)
        elif raw_header.header_id == ProjectorCommandTypeHeader.id():
            return ProjectorCommandTypeHeader._from_raw_header(raw_header)

        _LOGGER.warning("Header with id {%s} is not supported", raw_header.header_id)
        return None

    @staticmethod
    async def from_stream(stream: asyncio.StreamReader) -> HeaderBase | None:
        data = await stream.readexactly(RawHeaderData.size())
        return HeaderFactory.from_bytes(data)


@dataclass
class EscVpNetMessage:
    type_id: MessageType
    status: MessageStatus
    headers: list[HeaderBase] = field(default_factory=list)

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
    async def from_bytes(cls, data: bytes) -> EscVpNetMessage:
        stream = asyncio.StreamReader()
        stream.feed_data(data)
        stream.feed_eof()
        return await cls.from_stream(stream)

    @classmethod
    async def from_stream(cls, stream: asyncio.StreamReader) -> EscVpNetMessage:
        data = await stream.readexactly(struct.calcsize(cls._FORMAT))

        unpacked = struct.unpack(cls._FORMAT, data)

        protocol = unpacked[0]
        assert protocol == PROTOCOL_IDENTIFIER, f"Unexpected protocol: {protocol}"

        version = unpacked[1]
        assert version == VERSION_1_0, f"Unsupported protocol version: {version}"

        header_count = unpacked[5]
        headers = []

        for _ in range(header_count):
            if header := await HeaderFactory.from_stream(stream):
                headers.append(header)

        return cls(
            type_id=MessageType(unpacked[2]),
            status=MessageStatus(unpacked[4]),
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


def raise_from_status(status: MessageStatus):
    if status == MessageStatus.OK:
        return
    elif status == MessageStatus.BAD_REQUEST:
        raise ValueError("Bad request")
    elif status == MessageStatus.UNAUTHORIZED:
        raise PermissionError("Password is required")
    elif status == MessageStatus.FORBIDDEN:
        raise PermissionError("Password is wrong")
    elif status == MessageStatus.REQUEST_NOT_ALLOWED:
        raise RuntimeError("Request is not allowed in current state")
    elif status == MessageStatus.SERVICE_UNAVAILABLE:
        raise RuntimeError("Projector is busy")
    elif status == MessageStatus.PROTOCOL_VERSION_NOT_SUPPORTED:
        raise RuntimeError("Protocol version not supported")
    raise RuntimeError(f"Unknown status: {status}")


class HelloProtocol(asyncio.DatagramProtocol):

    def __init__(
        self, connection_made: asyncio.Future, responses: dict[str, bytes]
    ) -> None:
        super().__init__()
        self._connection_made = connection_made
        self._responses = responses

    def connection_made(self, _transport):
        self._connection_made.set_result(True)

    def datagram_received(self, data, addr):
        _LOGGER.debug("received [%s]: %s", addr, data)
        self._responses[addr[0]] = data


@dataclass
class ProjectorInfo:
    ip: str
    projector_name: str
    im_type: int
    command_type: CommandType


class EscVpNet:

    def __init__(self, host, port=ESC_VPNET_PORT):
        self._host = host
        self._port = port

    # Session-less mode (UDP) commands

    async def hello(self, response_wait_time: float = 2) -> list[ProjectorInfo]:

        responses: dict[str, bytes] = {}

        # Open UDP socket for listening for reponses to HELLO message
        loop = asyncio.get_running_loop()
        connection_made = loop.create_future()

        transport, _ = await loop.create_datagram_endpoint(
            lambda: HelloProtocol(connection_made, responses),
            local_addr=("0.0.0.0", ESC_VPNET_PORT),
            reuse_port=True,
            allow_broadcast=True,
        )
        await connection_made

        # Send HELLO message as broadcast
        transport.sendto(
            EscVpNetMessage(
                type_id=MessageType.HELLO, status=MessageStatus.REQUEST
            ).to_bytes(),
            ("<broadcast>", ESC_VPNET_PORT),
        )

        # Give responses some time to arrive
        try:
            await asyncio.sleep(response_wait_time)
        finally:
            transport.close()

        # Decode the responses
        # Note that the protocol will also have received the HELLO broadcast message itself
        hello_infos = []
        for ip_address, data in responses.items():
            message = await EscVpNetMessage.from_bytes(data)
            _LOGGER.debug("Received HELLO response from %s: %s", ip_address, message)

            if (
                message.type_id == MessageType.HELLO
                and message.status == MessageStatus.OK
            ):
                projector_name = None
                im_type = None
                command_type = None

                # The documentation seems to imply a fixed order,
                # but lets be flexible just in case.
                for header in message.headers:
                    if isinstance(header, ProjectorNameHeader):
                        projector_name = header.projector_name
                    elif isinstance(header, ImTypeHeader):
                        im_type = header.im_type
                    elif isinstance(header, ProjectorCommandTypeHeader):
                        command_type = header.command_type

                if projector_name and im_type is not None and command_type is not None:
                    hello_infos.append(
                        ProjectorInfo(
                            ip=ip_address,
                            projector_name=projector_name,
                            im_type=im_type,
                            command_type=command_type,
                        )
                    )

        return hello_infos

    # Session mode (TCP) commands

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

    async def password(
        self, password: str | None = None, new_password: str | None = None
    ) -> None:
        """
        Password request/response. Allows checking and changing of password.

        When only `password` is provided, it checks if the password is correct.
        When also `new_password` is provided, the password will be changed when the current password is correct.
        """
        try:
            async with asyncio.timeout(10):
                reader, writer = await asyncio.open_connection(
                    host=self._host, port=self._port
                )

                headers: list[HeaderBase] = []
                if password is not None:
                    headers.append(PasswordHeader(password=password))
                if new_password is not None:
                    headers.append(NewPasswordHeader(password=new_password))

                writer.write(
                    EscVpNetMessage(
                        type_id=MessageType.PASSWORD,
                        status=MessageStatus.REQUEST,
                        headers=headers,
                    ).to_bytes()
                )
                await writer.drain()

                response_message = await EscVpNetMessage.from_stream(reader)

                if response_message.status == MessageStatus.OK:
                    return
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

        return

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
                        type_id=MessageType.CONNECT,
                        status=MessageStatus.REQUEST,
                        headers=(
                            [PasswordHeader(password=password)]
                            if password is not None
                            else []
                        ),
                    ),
                    close_after_response=False,
                )

                if response_message.status == MessageStatus.OK:
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

    async def main(args):
        escvpnet = EscVpNet(host=args.host)

        if args.discover:
            responses = await escvpnet.hello()
            print(responses)
            return

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

        try:
            await escvpnet.password()
        except Exception as e:
            print(f"Error checking password: {e}")
        else:
            print("Can connect")

        try:
            await escvpnet.password("new_password", "new_password")
        except Exception as e:
            print(f"Error changing password: {e}")
        else:
            print("Password changed")

    import argparse

    parser = argparse.ArgumentParser(description="Test ESC/VP.net connection")
    parser.add_argument("host", help="IP address of the projector")
    parser.add_argument("--discover", action="store_true", help="Discover projectors in the network using HELLO message")
    parser.add_argument(
        "--loglevel",
        help="Set the logging level. Default is INFO.",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel)

    asyncio.run(main(args))
