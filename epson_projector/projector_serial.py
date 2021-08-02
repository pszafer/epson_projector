"""Serial USB/RS232 connection of Epson projector module."""
import logging

import asyncio
import serial_asyncio
from serial.serialutil import SerialException
from .const import ESCVP_HELLO_COMMAND, COLON, CR, GET_CR, BUSY, ERROR, SNO
import async_timeout

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
MAX_TIMEOUTS = 3


class ProjectorSerial:
    """
    Epson Serial connector
    """

    def __init__(self, host):
        """
        Epson Serial connector

        :param str host:    Device to connect to.
        """
        self._host = host
        self._reader = None
        self._writer = None
        self._timeouts = 0
        self._isOpen = False
        self._loop = asyncio.get_running_loop()
        self._serial = None

    async def async_init(self):
        """Async init to open serial connection with projector."""

        _LOGGER.debug("Establishing serial connection")
        if self._writer and self._writer.is_closing():
            try:
                await self._writer.wait_closed()
            except:
                pass
        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT):
                (
                    self._reader,
                    self._writer,
                ) = await serial_asyncio.open_serial_connection(
                    url=self._host, baudrate=9600, loop=self._loop
                )
                if self._reader and self._writer:
                    self._isOpen = True
                    self._writer.write(ESCVP_HELLO_COMMAND.encode())
                    response = await self._reader.readuntil(COLON.encode())
                    if str(response.decode().strip(CR)) == ":":
                        _LOGGER.info("Connection open")
                        return True
                    else:
                        _LOGGER.info(
                            "Connection established, " "but wrong response %r.",
                            response,
                        )
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error during connection")
        except SerialException as se:
            _LOGGER.error(f"Problem opening serial connection: {se}")
            self._isOpen = False
        return self.closed_connection_info()

    def closed_connection_info(self):
        _LOGGER.info("Cannot open serial to Epson")
        return False

    def close(self):
        if self._writer and not self._writer.is_closing():
            _LOGGER.debug("Closing serial connection")
            self._writer.close()
            self._writer = None
            self._isOpen = False
            self._timeouts = 0

    def _check_timeout_reconnect(self):
        if self._timeouts >= MAX_TIMEOUTS:
            self._writer.close()

    async def get_property(self, command, timeout):
        """Get property state from device."""
        response = await self.send_request(timeout=timeout, command=command + GET_CR)
        if not response:
            return False
        try:
            return response.split("=")[1]
        except KeyError:
            return BUSY
        except IndexError:
            _LOGGER.error("Bad response %s", response)
            return False

    async def send_command(self, command, timeout):
        """Send command to Epson."""
        response = await self.send_request(timeout=timeout, command=command + CR)
        return response

    async def send_request(self, timeout, command):
        """Send request to Epson over serial."""
        if self._writer and not self._isOpen:
            self._writer.close()
        if self._writer is None or self._writer.is_closing():
            await self.async_init()
        if self._writer and self._isOpen and command:
            try:
                with async_timeout.timeout(timeout):
                    _LOGGER.debug("Sent to Epson: %r with timeout %d", command.encode(), timeout)
                    self._writer.write(command.encode())
                    response = await self._reader.readuntil(COLON.encode())
                    response = response[:-1].decode().rstrip(CR)
                    _LOGGER.info("Response from Epson %r", response)
                    if response == ERROR:
                        _LOGGER.error("Error request")
                    else:
                        return response
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout error during sending request")
                self._timeouts += 1
                self._check_timeout_reconnect()
            except SerialException as se:
                _LOGGER.error(f"Error during serial write/read: {se}")
                self.close()

        return False

    async def get_serial(self):
        """Send request for serial to Epson."""
        if not self._serial:
            response = await self.get_property(SNO, timeout=DEFAULT_TIMEOUT)
            if not response or response == BUSY:
                _LOGGER.error("Error retrieving serial number from projector")
            else:
                self._serial = response
        return self._serial
