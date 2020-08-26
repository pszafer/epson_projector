"""Main of Epson projector module."""
import logging

from .const import (BUSY, TIMEOUT_TIMES)

from .lock import Lock

_LOGGER = logging.getLogger(__name__)


class Projector:
    """
    Epson projector class.

    Control your projector with Python.
    """

    def __init__(self, host, websession=None, type='http', port=80,
                 encryption=False, loop=None, timeout_scale=1.0):
        """
        Epson Projector controller.

        :param str host:        Hostname/IP/serial to the projector
        :param obj websession:  Websession to pass for HTTP protocol
        :param int port:        Port to connect to if using HTTP/TCP connection
        :param bool encryption: User encryption to connect, only for HTTP.
        :param obj loop:        Asyncio loop to pass for TCP/serial connection
        :param timeout_scale    Factor to multiply default timeouts by (for slow projectors)

        """
        self._lock = Lock()
        self._type = type
        self._timeout_scale = timeout_scale
        if self._type == 'http':
            self._host = host
            from .projector_http import ProjectorHttp
            self._projector = ProjectorHttp(host, websession,
                                            port, encryption)
        elif self._type == 'tcp':
            from .projector_tcp import ProjectorTcp
            self._host = host
            self._projector = ProjectorTcp(host, port, loop)
        elif self._type == 'serial':
            from .projector_serial import ProjectorSerial
            self._host = host
            self._projector = ProjectorSerial(host, loop)

    def close(self):
        """Close connection. Not used in HTTP"""
        self._projector.close()

    def set_timeout_scale(self, timeout_scale=1.0):
        self._timeout_scale = timeout_scale

    async def get_property(self, command):
        """Get property state from device."""
        _LOGGER.debug("Getting property %s", command)
        if self._lock.checkLock():
            return BUSY
        return await self._projector.get_property(command,
                                                  self.__get_timeout(command))

    async def send_command(self, command):
        """Send command to Epson."""
        _LOGGER.debug("Sending command to projector %s", command)
        if self._lock.checkLock():
            return False
        self._lock.setLock(command)
        return await self._projector.send_command(command,
                                                  self.__get_timeout(command))

    def __get_timeout(self, command):
        if command in TIMEOUT_TIMES:
            return TIMEOUT_TIMES[command] * self._timeout_scale
        else:
            return TIMEOUT_TIMES['ALL'] * self._timeout_scale
