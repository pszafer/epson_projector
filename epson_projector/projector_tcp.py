"""TCP connection of Epson projector module."""
from __future__ import annotations

import logging

import asyncio

from epson_projector.error import ProjectorUnavailableError, UnauthorizedError
from epson_projector.escvpnet.error import EscVpNetConnectionError, EscVpNetForbiddenStatus, EscVpNetUnauthorizedStatus
from epson_projector.escvpnet.escvpnet import ESC_VPNET_PORT, EscVpNet
from epson_projector.imevent import ImEvent

from .base_connection import BaseProjectorConnection
from .const import (
    BUSY,
    COLON,
    ERROR,
    CR,
    CR_COLON,
    GET_CR,
    EPSON_CODES,
    POWER,
    SERIAL_BYTE,
    TCP_SERIAL_PORT,
)
from .timeout import get_timeout

_LOGGER = logging.getLogger(__name__)

class ProjectorTcp(BaseProjectorConnection):
    """
    Epson TCP connector
    """

    def __init__(self, host, port=ESC_VPNET_PORT, password=None, on_imevent=None):
        """
        Epson TCP connector

        :param str host:     IP address of Projector
        :param int port:     Port to connect to. Default 3629.
        :param str password: Password for the projector. Default None.
        :param callable on_imevent: Callback for IMEVENT messages. Default None.
        """
        self._host = host
        self._port = port
        self._password = password
        self._on_imevent = on_imevent
        self._isOpen = False
        self._serial = None
        self._listener_task = None
        self._pending_command_future: asyncio.Future | None = None

    async def async_init(self) -> None:
        """Async init to open connection with projector."""
        try:
            async with asyncio.timeout(10):
                escvpnet = EscVpNet(host=self._host, port=self._port, password=self._password)
                self._reader, self._writer = await escvpnet.connect()
                self._listener_task = asyncio.create_task(self._listener_task_impl(self._reader, self._writer))
                self._isOpen = True
                _LOGGER.info("Connection open")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error")
        except (EscVpNetUnauthorizedStatus, EscVpNetForbiddenStatus) as e:
            raise UnauthorizedError("Password is incorrect or not provided.") from e
        except EscVpNetConnectionError as e:
            raise ProjectorUnavailableError("Connection error") from e

    def close(self) -> None:
        if self._isOpen:
            self._writer.close()

    async def _listener_task_impl(self, reader, writer) -> None:
        """Listener task for messages coming from the projector."""
        try:
            while not writer.is_closing():
                try:
                    raw_response = await reader.readuntil(COLON.encode())
                except asyncio.IncompleteReadError:
                    _LOGGER.debug("EOF reached")
                    return
                    
                _LOGGER.debug("Received: %s pending_command=%s)", raw_response, self._pending_command_future is not None)

                # First handle supported unsolicited messages
                if raw_response.startswith(b"IMEVENT="):
                    if self._on_imevent:
                        try:
                            imevent = ImEvent.from_message(raw_response)
                            self._on_imevent(imevent)
                        except ValueError as e:
                            _LOGGER.error("Error parsing IMEVENT: %s", e)
                    continue

                # Must be response to pending command
                if (future := self._pending_command_future) and not future.done():
                    future.set_result(raw_response)
                    self._pending_command_future = None
                    continue
    
                _LOGGER.warning("Received message while nothing pending: %s", raw_response)
        except Exception as e:
            _LOGGER.error("Error in listener task: %s", e)

    async def get_property(self, command, timeout, bytes_to_read=16) -> str | bool | int:
        """Get property state from device."""
        response = await self.send_request(
            timeout=timeout, params=command + GET_CR, bytes_to_read=bytes_to_read
        )
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
        response = await self.send_request(timeout=timeout, params=command + CR)
        return response

    async def send_request(self, timeout, params, bytes_to_read=16) -> str | bool | None:
        """Send TCP request to Epson."""
        if self._isOpen is False:
            await self.async_init()
        if self._isOpen and params:
            bytes_to_read = bytes_to_read if bytes_to_read else 16
            try:
                async with asyncio.timeout(timeout):
                    # Note that command has ?\r already appended
                    pending_command = asyncio.get_running_loop().create_future()
                    self._pending_command_future = pending_command

                    raw_command = params.encode()
                    _LOGGER.debug("Sending: %s", raw_command)
                    self._writer.write(raw_command)
                    await self._writer.drain()

                    response = await pending_command
                    response = response.decode().replace(CR_COLON, "")

                    if response == ERROR:
                        return False
                    return response
            except asyncio.TimeoutError as e:
                _LOGGER.error("Timeout error receiving response for command %s", params)
                if pending_command_future := self._pending_command_future:
                    pending_command_future.cancel()
                self._pending_command_future = None

                raise e
        return None

    async def get_serial_number(self) -> str | None:
        """Send TCP request for serial number to Epson."""
        if not self._serial:
            try:
                async with asyncio.timeout(10):
                    power_on = await self.get_property(POWER, get_timeout(POWER))
                    if power_on == EPSON_CODES[POWER]:
                        reader, writer = await asyncio.open_connection(
                            host=self._host, port=TCP_SERIAL_PORT
                        )
                        _LOGGER.debug("Asking for serial number.")
                        writer.write(SERIAL_BYTE)
                        await writer.drain()
                        response = await reader.read(32)
                        self._serial = response[24:].decode()
                        writer.close()
                    else:
                        _LOGGER.error("Is projector turned on?")
            except asyncio.TimeoutError:
                _LOGGER.error(
                    "Timeout error receiving SERIAL of projector. Is projector turned on?"
                )
        return self._serial
