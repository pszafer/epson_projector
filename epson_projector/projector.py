"""Main of Epson projector module."""
import logging

from .base_connection import BaseProjectorConnection
from .const import BUSY, TCP_PORT, HTTP_PORT, POWER
from .timeout import get_timeout

from .lock import Lock

_LOGGER = logging.getLogger(__name__)


class Projector:
    """
    Epson projector class.

    Control your projector with Python.
    """

    def __init__(
        self,
        connection: BaseProjectorConnection,
        timeout_scale=1.0,
    ):
        """
        Epson Projector controller.

        :param BaseProjectorConnection connection: Pre-initialized connection to use.
        :param timeout_scale     Factor to multiply default timeouts by (for slow projectors)
        """
        self._lock = Lock()
        self._timeout_scale = timeout_scale
        self._power = None
        self._projector = connection

    @staticmethod
    def create_http(
        host: str,
        password: str | None = None,
        port: int = HTTP_PORT,
        timeout_scale=1.0,
    ) -> "Projector":
        """
        Create an Epson Projector connected through HTTP.

        :param str host:             Hostname/IP/serial to the projector
        :param str | None password:  Optional password for HTTP
        :param int port:             HTTP port. Default 80.
        :param timeout_scale         Factor to multiply default timeouts by (for slow projectors)
        """
        from .projector_http import ProjectorHttp

        return Projector(connection=ProjectorHttp(
            host=host, password=password, port=port
        ), timeout_scale=timeout_scale)

    @staticmethod
    def create_escvpnet(
        host: str,
        password: str | None = None,
        timeout_scale=1.0
    ) -> "Projector":
        """
        Create an Epson Projector connected through ESC/VP.net.

        :param str host:             Hostname/IP/serial to the projector
        :param str | None password:  Optional password for ESC/VP.net connection
        :param timeout_scale     Factor to multiply default timeouts by (for slow projectors)
        """
        from .projector_tcp import ProjectorTcp
        return Projector(connection=ProjectorTcp(host, TCP_PORT, password=password), timeout_scale=timeout_scale)

    @staticmethod
    def create_serial(
        url: str,
        timeout_scale=1.0,
    ) -> "Projector":
        """
        Create an Epson Projector connected through serial.

        :param str url:          Serialx supported URL for the projector
        :param timeout_scale     Factor to multiply default timeouts by (for slow projectors)
        """
        from .projector_serial import ProjectorSerial
        return Projector(connection=ProjectorSerial(url), timeout_scale=timeout_scale)


    async def close(self):
        """Close connection."""
        await self._projector.close()

    def set_timeout_scale(self, timeout_scale=1.0):
        """Set timeout scale for commands (to compensate for slow projectors)."""
        self._timeout_scale = timeout_scale

    async def get_serial_number(self):
        """Get serial number from device."""
        return await self._projector.get_serial_number()

    async def get_power(self):
        """Get Power info."""
        _LOGGER.debug("Getting POWER info")
        power = await self.get_property(command=POWER)
        if power:
            self._power = power
        return self._power

    async def get_property(self, command, timeout=None):
        """Get property state from device."""
        _LOGGER.debug("Getting property %s", command)
        timeout = timeout if timeout else get_timeout(command, self._timeout_scale)
        if self._lock.checkLock():
            return BUSY
        return await self._projector.get_property(command=command, timeout=timeout)

    async def send_command(self, command):
        """Send command to Epson."""
        _LOGGER.debug("Sending command to projector %s", command)
        if self._lock.checkLock():
            return False
        self._lock.setLock(command)
        return await self._projector.send_command(
            command, get_timeout(command, self._timeout_scale)
        )

    async def send_request(self, command):
        """Get property state from device."""
        _LOGGER.debug("Getting property %s", command)
        if self._lock.checkLock():
            return BUSY
        return await self._projector.send_request(params=command, timeout=10)
