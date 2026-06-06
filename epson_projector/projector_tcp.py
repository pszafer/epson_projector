"""TCP connection of Epson projector module."""
from __future__ import annotations

import logging

import asyncio

from epson_projector.error import ProjectorUnavailableError, UnauthorizedError
from epson_projector.escvpnet.error import EscVpNetConnectionError, EscVpNetForbiddenStatus, EscVpNetUnauthorizedStatus
from epson_projector.escvpnet.escvpnet import EscVpNet
from epson_projector.projector_serial import DEFAULT_TIMEOUT

from .base_connection import BaseProjectorConnection
from .const import (
    BUSY,
    ERROR,
    CR,
    CR_COLON,
    GET_CR,
    EPSON_CODES,
    POWER,
    SERIAL_BYTE,
    SNO,
    TCP_SERIAL_PORT,
)
from .timeout import get_timeout

_LOGGER = logging.getLogger(__name__)


class ProjectorTcp(BaseProjectorConnection):
    """
    Epson TCP connector
    """

    def __init__(self, host, port=3629, password=None):
        """
        Epson TCP connector

        :param str host:     IP address of Projector
        :param int port:     Port to connect to. Default 3629.
        :param str password: Password for the projector. Default None.
        """
        self._host = host
        self._port = port
        self._password = password
        self._isOpen = False
        self._serial = None

    async def async_init(self) -> None:
        """Async init to open connection with projector."""
        try:
            async with asyncio.timeout(10):
                escvpnet = EscVpNet(host=self._host, port=self._port, password=self._password)
                self._reader, self._writer = await escvpnet.connect()
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

    async def get_property(self, command, timeout, bytes_to_read=16) -> str | bool | int:
        """Get property state from device."""
        response = await self.send_request(
            timeout=timeout, command=command + GET_CR, bytes_to_read=bytes_to_read
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
        response = await self.send_request(timeout=timeout, command=command + CR)
        return response

    async def send_request(self, timeout, command, bytes_to_read=16) -> str | bool | None:
        """Send TCP request to Epson."""
        if self._isOpen is False:
            await self.async_init()
        if self._isOpen and command:
            bytes_to_read = bytes_to_read if bytes_to_read else 16
            async with asyncio.timeout(timeout):
                self._writer.write(command.encode())
                await self._writer.drain()
                response = await self._reader.read(bytes_to_read)
                response = response.decode().replace(CR_COLON, "")
                if response == ERROR:
                    return False
                return response
        return None

    async def get_serial_number(self) -> str | None:
        """Send TCP request for serial number to Epson."""
        if not self._serial:
            try:
                response = await self.get_property(SNO, DEFAULT_TIMEOUT)
                if response and response != BUSY:
                    self._serial = response
                    return self._serial
            except asyncio.TimeoutError:
                _LOGGER.info(
                    "Timeout error receiving SERIAL of projector with SNO?, trying fallback method."
                )

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
