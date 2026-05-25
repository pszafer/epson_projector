from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from .escvp21_communication import EscVp21Communication

from .headers import (
    CommandType,
    HeaderBase,
    ImTypeHeader,
    NewPasswordHeader,
    PasswordHeader,
    ProjectorCommandTypeHeader,
    ProjectorNameHeader,
)
from .message import Message, MessageStatus, MessageType

from .error import (
    BadRequestStatus,
    ServiceUnavailableStatus,
    ProtocolVersionNotSupportedStatus,
    RequestNotAllowedStatus,
    UnauthorizedStatus,
    ForbiddenStatus,
    UnknownStatus,
)


ESC_VPNET_PORT = 3629
COMMAND_TIMEOUT = 5

_LOGGER = logging.getLogger(__name__)


def verify_password(password: str | None):
    if password is None:
        # Password None means no password, so it is valid
        return
    if len(password) > 16:
        raise ValueError("Password must be a string of maximum length 16")
    try:
        password.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("Password must be ASCII")


def raise_from_status(status: MessageStatus):
    if status == MessageStatus.OK:
        return
    elif status == MessageStatus.BAD_REQUEST:
        raise BadRequestStatus("Bad request")
    elif status == MessageStatus.UNAUTHORIZED:
        raise UnauthorizedStatus("Password is required")
    elif status == MessageStatus.FORBIDDEN:
        raise ForbiddenStatus("Password is wrong")
    elif status == MessageStatus.REQUEST_NOT_ALLOWED:
        raise RequestNotAllowedStatus("Request is not allowed in current state")
    elif status == MessageStatus.SERVICE_UNAVAILABLE:
        raise ServiceUnavailableStatus("Projector is busy")
    elif status == MessageStatus.PROTOCOL_VERSION_NOT_SUPPORTED:
        raise ProtocolVersionNotSupportedStatus("Protocol version not supported")
    raise UnknownStatus(f"Unknown status: {status}")


class HelloProtocol(asyncio.DatagramProtocol):
    """Protocol for receiving responses to HELLO message."""

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
    """Class for ESC/VP.net communication."""

    def __init__(self, host, port=ESC_VPNET_PORT):
        self._host = host
        self._port = port
        self._escvp21: EscVp21Communication | None = None

    # Session-less mode (UDP) commands

    async def hello(self, response_wait_time: float = 2) -> list[ProjectorInfo]:
        """Send HELLO UDP broadcast and wait for responses, returning the decoded responses."""

        loop = asyncio.get_running_loop()
        responses: dict[str, bytes] = {}

        # Setup UDP listening socket
        connection_made = loop.create_future()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: HelloProtocol(connection_made, responses),
            local_addr=("0.0.0.0", ESC_VPNET_PORT),
            reuse_port=True,
            allow_broadcast=True,
        )

        # Wait until the listening socket is setup
        await connection_made

        # Send HELLO message as UDP broadcast
        transport.sendto(
            Message(type_id=MessageType.HELLO, status=MessageStatus.REQUEST).to_bytes(),
            ("<broadcast>", ESC_VPNET_PORT),
        )

        # Give responses some time to arrive
        try:
            await asyncio.sleep(response_wait_time)
        finally:
            transport.close()

        # Decode the responses
        # Note that the HelloProtocol will also have received the HELLO broadcast message itself
        projector_infos = []
        for ip_address, data in responses.items():
            message = await Message.from_bytes(data)
            _LOGGER.debug("Received response from %s: %s", ip_address, message)

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
                    projector_infos.append(
                        ProjectorInfo(
                            ip=ip_address,
                            projector_name=projector_name,
                            im_type=im_type,
                            command_type=command_type,
                        )
                    )

        return projector_infos

    # Session mode (TCP) commands

    async def _communicate(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        message: Message,
        close_after_response=True,
    ) -> Message:
        try:
            writer.write(message.to_bytes())
            await writer.drain()

            response_message = await Message.from_stream(reader)
            return response_message
        finally:
            if close_after_response and writer and not writer.is_closing():
                writer.close()
                await writer.wait_closed()

    async def password(
        self, password: str | None = None, new_password: str | None = None
    ) -> None:
        """
        PASSWORD request/response. Allows checking and changing of password.

        When only `password` is provided, it checks if the password is correct or needed.
        When also `new_password` is provided, the password will be changed to `new_password` (when the current password is correct).
        """
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None

        verify_password(password)
        verify_password(new_password)

        try:
            async with asyncio.timeout(COMMAND_TIMEOUT):
                reader, writer = await asyncio.open_connection(
                    host=self._host, port=self._port
                )

                headers: list[HeaderBase] = []
                if password is not None:
                    headers.append(PasswordHeader(password=password))
                if new_password is not None:
                    headers.append(NewPasswordHeader(password=new_password))

                writer.write(
                    Message(
                        type_id=MessageType.PASSWORD,
                        status=MessageStatus.REQUEST,
                        headers=headers,
                    ).to_bytes()
                )
                await writer.drain()

                response_message = await Message.from_stream(reader)

                raise_from_status(response_message.status)
        except asyncio.TimeoutError as e:
            raise ConnectionError("Timeout while communicating with projector") from e
        except ConnectionRefusedError as e:
            raise ConnectionError(
                "Connection refused while communicating with projector"
            ) from e
        except asyncio.IncompleteReadError as e:
            raise ConnectionError(
                "Connection closed before reading complete response"
            ) from e
        except OSError as e:
            raise ConnectionError(
                "Network error while communicating with projector"
            ) from e
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()

        return

    async def connect(self, password: str | None = None) -> EscVp21Communication:
        """Use CONNECT to start an ESC/VP21 session"""

        connected = False
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None

        verify_password(password)

        try:
            async with asyncio.timeout(COMMAND_TIMEOUT):
                reader, writer = await asyncio.open_connection(
                    host=self._host, port=self._port
                )

                response_message = await self._communicate(
                    reader,
                    writer,
                    Message(
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

                    # Keep a referenced for keep-alive mechanism
                    # TODO: figure out how to do that. It is a VP.net responsibility
                    #       to keep the TCP alive, but kind of need to know if there was traffic
                    #       on the other hand, can just send NULL commands periodically regardless of traffic
                    self._escvp21 = EscVp21Communication(reader=reader, writer=writer)
                    return self._escvp21

                raise_from_status(response_message.status)

        except asyncio.TimeoutError as e:
            raise ConnectionError("Timeout while communicating with projector") from e
        except ConnectionRefusedError as e:
            raise ConnectionError(
                "Connection refused while communicating with projector"
            ) from e
        except asyncio.IncompleteReadError as e:
            raise ConnectionError(
                "Connection closed before reading complete response"
            ) from e
        except OSError as e:
            raise ConnectionError(
                "Network error while communicating with projector"
            ) from e
        finally:
            if not connected and writer is not None:
                writer.close()
                await writer.wait_closed()

        # TODO: Replace expception
        raise RuntimeError("Failed to open ESC/VP.net session")
