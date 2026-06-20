"""TCP connection of Epson projector module."""
from __future__ import annotations

import logging

import asyncio


from .base_connection import BaseProjectorConnection
from .const import (
    BUSY,
    COLON,
    ERROR,
    CR,
    CR_COLON,
    GET_CR,
)
from .easymp import get_serial_number
from .error import ProjectorUnavailableError, UnauthorizedError
from .escvpnet.error import EscVpNetConnectionError, EscVpNetForbiddenStatus, EscVpNetUnauthorizedStatus
from .escvpnet.escvpnet import ESC_VPNET_PORT, EscVpNet
from .imevent import ImEvent

_LOGGER = logging.getLogger(__name__)

class ProjectorTcp(BaseProjectorConnection):
    """
    Epson TCP connector
    """

    def __init__(self, host, port=ESC_VPNET_PORT, password=None, on_imevent=None):
        """
        Epson TCP connector

        :param str      host:       IP address of Projector
        :param int      port:       Port to connect to. Default 3629.
        :param str      password:   Password for the projector. Default None.
        :param callable on_imevent: Callback for IMEVENT messages. Default None.
        """
        self._host = host
        self._port = port
        self._password = password
        self._on_imevent = on_imevent

        self._serial = None
        self._listener_task = None
        self._writer: asyncio.StreamWriter | None = None

        # Writing to pending_request should only be done from the `request` method within the lock
        self._pending_request_future: asyncio.Future | None = None
        self._request_lock = asyncio.Lock()

    async def async_init(self) -> None:
        """Async init to open connection with projector."""
        try:
            async with asyncio.timeout(10):
                escvpnet = EscVpNet(host=self._host, port=self._port, password=self._password)
                reader, self._writer = await escvpnet.connect()
                self._listener_task = asyncio.create_task(self._listener_task_impl(reader, self._writer))
                _LOGGER.info("Connection open")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error")
        except (EscVpNetUnauthorizedStatus, EscVpNetForbiddenStatus) as e:
            raise UnauthorizedError("Password is incorrect or not provided.") from e
        except EscVpNetConnectionError as e:
            raise ProjectorUnavailableError("Connection error") from e

    async def close(self) -> None:
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
        if self._listener_task:
            self._listener_task.cancel()
            await self._listener_task
            self._listener_task = None

    async def _listener_task_impl(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Listener task for messages coming from the projector."""
        while not writer.is_closing():
            try:
                raw_response = await reader.readuntil(COLON.encode())
            except asyncio.IncompleteReadError:
                _LOGGER.debug("EOF reached")
                writer.close()
                self._writer = None
                break
                
            _LOGGER.debug("Received: %s", raw_response)

            # First handle supported unsolicited messages
            if raw_response.startswith(b"IMEVENT="):
                if self._on_imevent:
                    try:
                        imevent = ImEvent.from_message(raw_response)
                        self._on_imevent(imevent)
                    except ValueError as e:
                        _LOGGER.error("Error parsing IMEVENT: %s", e)
                continue

            # Should be response to pending command
            if (future := self._pending_request_future) and not future.done():
                future.set_result(raw_response)
                continue

            _LOGGER.warning("Received message while nothing pending: %s", raw_response)

    async def get_property(self, command, timeout) -> str | bool | int:
        """Get property state from device."""
        response = await self.send_request(timeout=timeout, command=command + GET_CR)
        _LOGGER.debug("Response is %s", response)
        if not response:
            return False
        try:
            resp_beginning = f"{command}="
            index_of_response = response.find(resp_beginning)
            if index_of_response == -1:
                return False
            _response = response[index_of_response:].replace(resp_beginning, "")
            if _response == ERROR:
                return False
            return _response
        except KeyError:
            return BUSY

    async def send_command(self, command, timeout) -> str | bool | None:
        """Send command to Epson."""
        response = await self.send_request(timeout=timeout, command=command + CR)
        return response

    async def send_request(self, timeout, command) -> str | bool | None:
        """Send TCP request to Epson."""
        if not self._writer:
            await self.async_init()

        if self._writer and command:
            async with self._request_lock:
                try:
                    async with asyncio.timeout(timeout):
                        pending_command = asyncio.get_running_loop().create_future()
                        self._pending_request_future = pending_command

                        raw_command = command.encode()
                        _LOGGER.debug("Sending: %s", raw_command)
                        self._writer.write(raw_command)
                        await self._writer.drain()

                        response = await pending_command
                        response = response.decode().replace(CR_COLON, "")

                        if response == ERROR:
                            return False
                        return response
                except asyncio.TimeoutError:
                    _LOGGER.error("Timeout error receiving response for command %s", command)
                    if pending_command_future := self._pending_request_future:
                        pending_command_future.cancel()
                    self._pending_request_future = None
                    raise
        return None

    async def get_serial_number(self) -> str | None:
        """Send TCP request for serial number to Epson."""
        if not self._serial:
            self._serial = await get_serial_number(self, self._host)
        return self._serial
