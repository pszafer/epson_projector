"""TCP connection of Epson projector module."""
import logging

import asyncio
import async_timeout

from .const import (BUSY, ESCVPNET_HELLO_COMMAND,
                    ESCVPNETNAME, ERROR, CR, CR_COLON, GET_CR)

_LOGGER = logging.getLogger(__name__)


class ProjectorTcp:
    """
    Epson TCP connector
    """

    def __init__(self, host, port=3629, loop=None):
        """
        Epson TCP connector

        :param str host:    IP address of Projector
        :param int port:    Port to connect to. Default 3629.
        :param obj loop:    Pass asyncio loop to connector

        """
        self._host = host
        self._port = port
        self._isOpen = False
        if loop is None:
            self._loop = asyncio.get_event_loop()
        else:
            self._loop = loop

    async def async_init(self):
        """Async init to open connection with projector."""
        returnvalue = False
        try:
            with async_timeout.timeout(10):
                self._reader, self._writer = await asyncio.open_connection(
                    host=self._host,
                    port=self._port,
                    loop=self._loop)
                self._writer.write(ESCVPNET_HELLO_COMMAND.encode())
                response = await self._reader.read(16)
                if (response[0:10].decode() == ESCVPNETNAME and
                        response[14] == 32):
                    self._isOpen = True
                    _LOGGER.info("Connection open")
                    returnvalue = True
                else:
                    _LOGGER.info("Cannot open connection to Epson")
                    returnvalue = False
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error")
            returnvalue = False
        except ConnectionRefusedError:
            _LOGGER.error("Connection refused Error")
            returnvalue = False
        return returnvalue

    def close(self):
        if self._isOpen:
            self._writer.close()

    async def get_property(self, command, timeout):
        """Get property state from device."""
        response = await self.send_request(
            timeout=timeout,
            command=command+GET_CR
            )
        if not response:
            return False
        try:
            return response.split('=')[1]
        except KeyError:
            return BUSY

    async def send_command(self, command, timeout):
        """Send command to Epson."""
        response = await self.send_request(
            timeout=timeout,
            command=command+CR)
        return response

    async def send_request(self, timeout, command):
        """Send TCP request to Epson."""
        if self._isOpen is False:
            await self.async_init()
        if self._isOpen and command:
            with async_timeout.timeout(timeout):
                self._writer.write(command.encode())
                # self._writer.write('\r'.encode())
                response = await self._reader.read(16)
                response = response.decode().replace(CR_COLON, "")
                if response == ERROR:
                    _LOGGER.error("Error request")
                    return False
                return response
