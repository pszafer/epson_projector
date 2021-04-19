"""HTTP connection of Epson projector module."""
import logging

import aiohttp
import asyncio
import async_timeout

from .const import (
    ACCEPT_ENCODING,
    ACCEPT_HEADER,
    BUSY,
    EPSON_KEY_COMMANDS,
    DIRECT_SEND,
    HTTP_OK,
    STATE_UNAVAILABLE,
    POWER,
    EPSON_CODES,
    TCP_SERIAL_PORT,
    SERIAL_BYTE,
    JSON_QUERY,
)
from .timeout import get_timeout

_LOGGER = logging.getLogger(__name__)


class ProjectorHttp:
    """
    Epson projector class.

    Control your projector with Python.
    """

    def __init__(self, host, websession, loop, port=80):
        """
        Epson Projector controller.

        :param str host:        IP address or hostname of Projector
        :param int port:        Port to connect to. Default 80.
        :param bool encryption: User encryption to connect

        """
        self._host = host
        self._http_url = f"http://{self._host}:{port}/cgi-bin/"
        self._headers = {
            "Accept-Encoding": ACCEPT_ENCODING,
            "Accept": ACCEPT_HEADER,
            "Referer": f"http://{self._host}:{port}/cgi-bin/webconf",
        }
        self.websession = websession
        self._loop = loop

    def close(self):
        return

    async def get_property(self, command, timeout):
        """Get property state from device."""
        response = await self.send_request(
            timeout=timeout, params=EPSON_KEY_COMMANDS[command], type=JSON_QUERY
        )
        if not response:
            return False
        try:
            if response == STATE_UNAVAILABLE:
                return STATE_UNAVAILABLE
            return response["projector"]["feature"]["reply"]
        except KeyError:
            return BUSY

    async def send_command(self, command, timeout):
        """Send command to Epson."""
        response = await self.send_request(
            timeout=timeout, params=EPSON_KEY_COMMANDS[command], type=DIRECT_SEND
        )
        return response

    async def send_request(self, params, timeout, type=JSON_QUERY):
        """Send request to Epson."""
        try:
            with async_timeout.timeout(timeout):
                url = "{url}{type}".format(url=self._http_url, type=type)
                async with self.websession.get(
                    url=url, params=params, headers=self._headers
                ) as response:
                    if response.status != HTTP_OK:
                        _LOGGER.warning("Error message %d from Epson.", response.status)
                        return False
                    if type == JSON_QUERY:
                        return await response.json()
                    return response
        except (
            aiohttp.ClientError,
            aiohttp.ClientConnectionError,
            TimeoutError,
            asyncio.exceptions.TimeoutError,
        ):
            _LOGGER.error("Error request")
            return STATE_UNAVAILABLE

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
                        _LOGGER.error("Is projector turned on?")
            except asyncio.TimeoutError:
                _LOGGER.error(
                    "Timeout error receiving SERIAL of projector. Is projector turned on?"
                )
        return self._serial
