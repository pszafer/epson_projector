"""TCP connection of Epson projector module."""
import logging

import asyncio
import async_timeout

from .const import (
    BUSY,
    ESCVPNET_HELLO_COMMAND,
    ESCVPNETNAME,
    ERROR,
    CR,
    CR_COLON,
    GET_CR,
    EPSON_CODES,
    POWER,
    PWR_ON,
    SERIAL_BYTE,
    TCP_SERIAL_PORT,
)
from .timeout import get_timeout

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
        self._serial = None
        if loop is None:
            self._loop = asyncio.get_event_loop()
        else:
            self._loop = loop

    async def async_init(self):
        """Async init to open connection with projector."""
        try:
            with async_timeout.timeout(10):
                self._reader, self._writer = await asyncio.open_connection(
                    host=self._host, port=self._port, loop=self._loop
                )
                self._writer.write(ESCVPNET_HELLO_COMMAND.encode())
                response = await self._reader.read(16)
                if response[0:10].decode() == ESCVPNETNAME and response[14] == 32:
                    self._isOpen = True
                    _LOGGER.info("Connection open")
                    return;
                else:
                    _LOGGER.info("Cannot open connection to Epson")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error")
        except ConnectionRefusedError:
            _LOGGER.error("Connection refused Error")
        except OSError as err:
            _LOGGER.error("No route to host? %s", err)

    def close(self):
        if self._isOpen:
            self._writer.close()

    async def get_property(self, command, timeout, bytes_to_read=16):
        """Get property state from device."""
        response = await self.send_request(timeout=timeout, command=command + GET_CR, bytes_to_read=bytes_to_read)
        _LOGGER.debug("Response is %s", response)
        if not response:
            return False
        try:
            resp_beginning=f'{command}='
            index_of_response=response.find(resp_beginning)
            if index_of_response == -1:
                return False
            return response[index_of_response:].replace(resp_beginning,'')
        except KeyError:
            return BUSY

    async def send_command(self, command, timeout):
        """Send command to Epson."""
        response = await self.send_request(timeout=timeout, command=command + CR)
        return response

    async def send_request(self, timeout, command, bytes_to_read=16):
        """Send TCP request to Epson."""
        if self._isOpen is False:
            await self.async_init()
        if self._isOpen and command:
            bytes_to_read = bytes_to_read if bytes_to_read else 16
            with async_timeout.timeout(timeout):
                self._writer.write(command.encode())
                response = await self._reader.read(bytes_to_read)
                response = response.decode().replace(CR_COLON, "")
                if response == ERROR:
                    return False
                return response

    async def get_serial(self):
        """Send TCP request for serial to Epson."""
        if not self._serial:
            try:
                with async_timeout.timeout(10):
                    power_on = await self.get_property(POWER, get_timeout(POWER))
                    if power_on == EPSON_CODES[POWER]:
                        reader, writer = await asyncio.open_connection(
                            host=self._host, port=TCP_SERIAL_PORT, loop=self._loop
                        )
                        _LOGGER.debug("Asking for serial number.")
                        writer.write(SERIAL_BYTE)
                        response = await reader.read(32)
                        self._serial = response[24:].decode()
                        writer.close()
                    else:
                        _LOGGER.error(
                            "Is projector turned on?"
                        )
            except asyncio.TimeoutError:
                _LOGGER.error(
                    "Timeout error receiving SERIAL of projector. Is projector turned on?"
                )
        return self._serial
