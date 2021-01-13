"""Main of Epson projector module."""
import logging

from .const import (BUSY, TCP_PORT, HTTP_PORT, POWER)
from .timeout import get_timeout

from .lock import Lock

_LOGGER = logging.getLogger(__name__)


class Projector:
    """
    Epson projector class.

    Control your projector with Python.
    """

    def __init__(self, host, loop, websession=None, type='tcp',
                 encryption=False, timeout_scale=1.0):
        """
        Epson Projector controller.

        :param str host:        Hostname/IP/serial to the projector
        :param obj loop:        Asyncio loop to pass for TCP/serial connection
        :param obj websession:  Websession to pass for HTTP protocol
        :param bool encryption: User encryption to connect, only for HTTP.
        :param timeout_scale    Factor to multiply default timeouts by (for slow projectors)

        """
        self._lock = Lock()
        self._type = type
        self._timeout_scale = timeout_scale
        self._power = None
        if self._type == 'http':
            self._host = host
            from .projector_http import ProjectorHttp
            self._projector = ProjectorHttp(host, websession,
                                            HTTP_PORT, encryption, loop)
        elif self._type == 'tcp':
            from .projector_tcp import ProjectorTcp
            self._host = host
            self._projector = ProjectorTcp(host, TCP_PORT, loop)
        elif self._type == 'serial':
            from .projector_serial import ProjectorSerial
            self._host = host
            self._projector = ProjectorSerial(host, loop)

    def close(self):
        """Close connection. Not used in HTTP"""
        self._projector.close()

    def set_timeout_scale(self, timeout_scale=1.0):
        self._timeout_scale = timeout_scale

    async def get_serial_number(self):
        return await self._projector.get_serial()

    async def get_power(self):
        """Get Power info."""
        _LOGGER.debug("Getting POWER info")
        power = await self.get_property(command=POWER, bytes_to_read=98)
        if power:
            self._power = power
        return self._power


    async def get_property(self, command, timeout=None, bytes_to_read=None):
        """Get property state from device."""
        _LOGGER.debug("Getting property %s", command)
        timeout = timeout if timeout else get_timeout(command, self._timeout_scale)
        if self._lock.checkLock():
            return BUSY
        return await self._projector.get_property(command=command,
                                                  timeout=timeout,
                                                  bytes_to_read=bytes_to_read)

    async def send_command(self, command):
        """Send command to Epson."""
        _LOGGER.debug("Sending command to projector %s", command)
        if self._lock.checkLock():
            return False
        self._lock.setLock(command)
        return await self._projector.send_command(command,
                                                  get_timeout(command, self._timeout_scale))

    async def send_request(self, command):
        """Get property state from device."""
        _LOGGER.debug("Getting property %s", command)
        if self._lock.checkLock():
            return BUSY
        return await self._projector.send_request(params=command, timeout=10)

