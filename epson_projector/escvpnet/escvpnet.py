from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from .escvp21_communication import EscVp21Communication

from .headers import CommandType, HeaderBase, ImTypeHeader, NewPasswordHeader, PasswordHeader, ProjectorCommandTypeHeader, ProjectorNameHeader
from .message import Message, MessageStatus, MessageType

from .error import (
    BadRequestError,
    BusyError,
    PasswordRequiredError,
    PasswordWrongError,
    ProtocolVersionNotSupportedError,
    RequestNotAllowedError,
    UnknownStatusError,
)


ESC_VPNET_PORT = 3629


_LOGGER = logging.getLogger(__name__)


def verify_password(password: str | None):
    if password is not None and (not isinstance(password, str) or len(password) > 16):
        raise ValueError("Password must be a string of maximum length 16")




def raise_from_status(status: MessageStatus):
    if status == MessageStatus.OK:
        return
    elif status == MessageStatus.BAD_REQUEST:
        raise BadRequestError("Bad request")
    elif status == MessageStatus.UNAUTHORIZED:
        raise PasswordRequiredError("Password is required")
    elif status == MessageStatus.FORBIDDEN:
        raise PasswordWrongError("Password is wrong")
    elif status == MessageStatus.REQUEST_NOT_ALLOWED:
        raise RequestNotAllowedError(
            "Request is not allowed in current state"
        )
    elif status == MessageStatus.SERVICE_UNAVAILABLE:
        raise BusyError("Projector is busy")
    elif status == MessageStatus.PROTOCOL_VERSION_NOT_SUPPORTED:
        raise ProtocolVersionNotSupportedError(
            "Protocol version not supported"
        )
    raise UnknownStatusError(f"Unknown status: {status}")


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
            Message(
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
            message = await Message.from_bytes(data)
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
        Password request/response. Allows checking and changing of password.

        When only `password` is provided, it checks if the password is correct.
        When also `new_password` is provided, the password will be changed when the current password is correct.
        """
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None

        verify_password(password)
        verify_password(new_password)

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
                    Message(
                        type_id=MessageType.PASSWORD,
                        status=MessageStatus.REQUEST,
                        headers=headers,
                    ).to_bytes()
                )
                await writer.drain()

                response_message = await Message.from_stream(reader)

                raise_from_status(response_message.status)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error while opening ESC/VP.net session")
            raise
        except ConnectionRefusedError:
            _LOGGER.error("Connection refused while opening ESC/VP.net session")
            raise
        except asyncio.IncompleteReadError:
            _LOGGER.error("Connecton closed before reading complete response")
            raise
        except OSError as err:
            _LOGGER.error("Network error while opening ESC/VP.net session: %s", err)
            raise
        finally:
            if writer and not writer.is_closing():
                writer.close()

        return

    async def connect(self, password: str | None = None) -> EscVp21Communication:
        connected = False
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None

        verify_password(password)

        try:
            async with asyncio.timeout(10):
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


