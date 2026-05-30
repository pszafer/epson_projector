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
    EscVpNetBadRequestStatus,
    EscVpNetServiceUnavailableStatus,
    EscVpNetProtocolVersionNotSupportedStatus,
    EscVpNetRequestNotAllowedStatus,
    EscVpNetUnauthorizedStatus,
    EscVpNetForbiddenStatus,
    EscVpNetUnknownStatus,
    EscVpNetConnectionError,
)


ESC_VPNET_PORT = 3629
COMMAND_TIMEOUT = 5

_LOGGER = logging.getLogger(__name__)


def verify_password(password: str | None) -> None:
    if password is None:
        # Password None means no password, so it is valid
        return
    if len(password) > 16:
        raise ValueError("Password must be a string of maximum length 16")
    try:
        password.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("Password must be ASCII")


def raise_from_status(status: MessageStatus) -> None:
    match status:
        case MessageStatus.OK:
            return
        case MessageStatus.BAD_REQUEST:
            raise EscVpNetBadRequestStatus("Bad request")
        case MessageStatus.UNAUTHORIZED:
            raise EscVpNetUnauthorizedStatus("Password is required")
        case MessageStatus.FORBIDDEN:
            raise EscVpNetForbiddenStatus("Password is wrong")
        case MessageStatus.REQUEST_NOT_ALLOWED:
            raise EscVpNetRequestNotAllowedStatus(
                "Request is not allowed in current state"
            )
        case MessageStatus.SERVICE_UNAVAILABLE:
            raise EscVpNetServiceUnavailableStatus("Projector is busy")
        case MessageStatus.PROTOCOL_VERSION_NOT_SUPPORTED:
            raise EscVpNetProtocolVersionNotSupportedStatus(
                "Protocol version not supported"
            )
        case _:
            raise EscVpNetUnknownStatus(f"Unknown status: {status}")


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

    def __init__(
        self, host: str, port: int = ESC_VPNET_PORT, password: str | None = None
    ) -> None:
        self._host = host
        self._port = port
        self._escvp21: EscVp21Communication | None = None

        verify_password(password)
        self._password = password

    async def __aenter__(self) -> EscVp21Communication:
        """Async context manager entry: connect and return EscVp21Communication."""
        self._escvp21 = await self.connect()
        return self._escvp21

    async def __aexit__(self, exc_type, exc, tb):
        """Async context manager exit: close the connection if open."""
        if self._escvp21 is not None:
            self._escvp21.close()
            self._escvp21 = None

    # Session-less mode (UDP) commands

    @staticmethod
    def _projector_info_from_hello(
        ip_address: str, message: Message
    ) -> ProjectorInfo | None:
        if message.type_id != MessageType.HELLO or message.status != MessageStatus.OK:
            return None

        projector_name: str | None = None
        im_type: int | None = None
        command_type: CommandType | None = None

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
            return ProjectorInfo(
                ip=ip_address,
                projector_name=projector_name,
                im_type=im_type,
                command_type=command_type,
            )

        return None

    @staticmethod
    async def discover(response_wait_time: float = 2) -> list[ProjectorInfo]:
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
        # But it will be ignored since it does not have the expected response status
        projector_infos = []
        for ip_address, data in responses.items():
            message = await Message.from_bytes(data)
            _LOGGER.debug("Received response from %s: %s", ip_address, message)

            projector_info = EscVpNet._projector_info_from_hello(ip_address, message)
            if projector_info is not None:
                projector_infos.append(projector_info)

        return projector_infos

    # Session mode (TCP) commands

    @staticmethod
    def _build_password_request(
        password: str | None = None,
        new_password: str | None = None,
    ) -> Message:
        headers: list[HeaderBase] = []
        if password is not None:
            headers.append(PasswordHeader(password=password))
        if new_password is not None:
            headers.append(NewPasswordHeader(password=new_password))

        return Message(
            type_id=MessageType.PASSWORD,
            status=MessageStatus.REQUEST,
            headers=headers,
        )

    async def _request(
        self,
        message: Message,
        close_after_response: bool = True,
    ) -> tuple[Message, asyncio.StreamReader, asyncio.StreamWriter]:
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None
        request_succeeded = False

        try:
            async with asyncio.timeout(COMMAND_TIMEOUT):
                reader, writer = await asyncio.open_connection(
                    host=self._host, port=self._port
                )

                writer.write(message.to_bytes())
                await writer.drain()

                response_message = await Message.from_stream(reader)
                request_succeeded = True

                return response_message, reader, writer
        except (
            asyncio.TimeoutError,
            ConnectionRefusedError,
            asyncio.IncompleteReadError,
            OSError,
        ) as e:
            if isinstance(e, asyncio.TimeoutError):
                error_message = "Timeout while communicating with projector"
            elif isinstance(e, ConnectionRefusedError):
                error_message = "Connection refused while communicating with projector"
            elif isinstance(e, asyncio.IncompleteReadError):
                error_message = "Connection closed before reading complete response"
            else:
                error_message = "Network error while communicating with projector"

            raise EscVpNetConnectionError(error_message) from e
        finally:
            # Close on failures and when requested.
            if writer and (close_after_response or not request_succeeded):
                writer.close()
                await writer.wait_closed()

    async def confirm_password(self) -> bool:
        """
        Use PASSWORD request to check if password can be used to connect.

        Returns True if password is valid (or not needed if None was passed)
        """
        response_message, _, _ = await self._request(
            self._build_password_request(password=self._password)
        )

        return response_message.status == MessageStatus.OK

    async def change_password(self, new_password: str | None = None) -> None:
        """
        Use PASSWORD request to change the password.

        `new_password`, new password to set. It can be None to remove the password.
        """
        verify_password(new_password)

        response_message, _, _ = await self._request(
            self._build_password_request(
                password=self._password,
                new_password=new_password,
            )
        )

        raise_from_status(response_message.status)

    async def connect(self) -> EscVp21Communication:
        """Use CONNECT request to start an ESC/VP21 session"""

        response_message, reader, writer = await self._request(
            Message(
                type_id=MessageType.CONNECT,
                status=MessageStatus.REQUEST,
                headers=(
                    [PasswordHeader(password=self._password)]
                    if self._password is not None
                    else []
                ),
            ),
            # Need to keep open to use socket for ESC/VP21 communication on successful connection
            close_after_response=False,
        )

        if response_message.status != MessageStatus.OK:
            # Need to close manually here since using `close_after_response=False`
            writer.close()
            await writer.wait_closed()

            raise_from_status(response_message.status)

        _LOGGER.debug("ESC/VP.net session open")

        return EscVp21Communication(reader=reader, writer=writer)
