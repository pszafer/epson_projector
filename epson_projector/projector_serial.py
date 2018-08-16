"""TCP connection of Epson projector module."""
import logging

import asyncio
import serial_asyncio
from serial.serialutil import SerialException
import async_timeout

from .const import (BUSY, ERROR)

_LOGGER = logging.getLogger(__name__)


class ProjectorSerial:
    """
    Epson Serial connector
    """

    def __init__(self, host, loop=None):
        """
        Epson Serial connector

        :param str host:    Device to connect to.
        :param obj loop:    Pass asyncio loop to connector

        """
        self._host = host
        self._isOpen = False
        self._reader = None
        self._writer = None
        if loop is None:
            self._loop = asyncio.get_event_loop()
        else:
            self._loop = loop

    async def async_init(self):
        """Async init to open serial connection with projector."""
        returnvalue = False
        try:
            with async_timeout.timeout(10):
                self._reader,
                self._writer = await serial_asyncio.open_serial_connection(
                    url=self._host,
                    baudrate=9600,
                    loop=self._loop)
                if (self._reader and self._writer):
                    response = await self._reader.read(16)
                    if response.decode() == ":":
                        self._isOpen = True
                        _LOGGER.info("Connection open")
                        returnvalue = True
                    else:
                        return self.close_connection_info()
                else:
                    return self.close_connection_info()
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error")
            returnvalue = False
        except SerialException:
            _LOGGER.error("Device not found")
            returnvalue = False
        return returnvalue

    def close_connection_info(self):
        _LOGGER.info("Cannot open serial to Epson")
        return False


    def close(self):
        if self._isOpen:
            self._writer.close()
            self._reader.close()

    async def get_property(self, command, timeout):
        """Get property state from device."""
        response = await self.send_request(
            timeout=timeout,
            command=command+'?\r'
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
            command=command+'\r')
        return response

    async def send_request(self, timeout, command):
        """Send request to Epson over serial."""
        if self._isOpen is False:
            await self.async_init()
        if self._isOpen and command:
            with async_timeout.timeout(timeout):
                self._writer.write(command.encode())
                # self._writer.write('\r'.encode())
                response = await self._reader.read(16)
                # response = response.decode().replace("\r:", "")
                if response == ERROR:
                    _LOGGER.error("Error request")
                    return False
                return response
        else:
            return False
