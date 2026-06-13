"""HTTP connection of Epson projector module."""
import logging

import aiohttp
import asyncio


from .base_connection import BaseProjectorConnection
from .const import (
    ACCEPT_ENCODING,
    ACCEPT_HEADER,
    BUSY,
    EPSON_KEY_COMMANDS,
    DIRECT_SEND,
    HTTP_OK,
    STATE_UNAVAILABLE,
    JSON_QUERY,
)
from .error import ProjectorUnavailableError
from .easymp import get_serial_number

_LOGGER = logging.getLogger(__name__)


class ProjectorHttp(BaseProjectorConnection):
    """
    Epson projector class.

    Control your projector with Python.
    """

    def __init__(self, host, websession, port=80):
        """
        Epson Projector controller.

        :param str host:        IP address or hostname of Projector
        :param obj websession:  AioHttpWebsession for HTTP protocol
        :param int port:        Port to connect to. Default 80.
        """
        self._host = host
        self._http_url = f"http://{self._host}:{port}/cgi-bin/"
        self._headers = {
            "Accept-Encoding": ACCEPT_ENCODING,
            "Accept": ACCEPT_HEADER,
            "Referer": f"http://{self._host}:{port}/cgi-bin/webconf",
        }
        self._serial = None
        self.websession = websession

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
            async with asyncio.timeout(timeout):
                url = "{url}{type}".format(url=self._http_url, type=type)
                _LOGGER.debug("Sending request: %s", params)
                async with self.websession.get(
                    url=url, params=params, headers=self._headers
                ) as response:
                    _LOGGER.debug("Received response, status: %s", response.status)
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
            raise ProjectorUnavailableError(STATE_UNAVAILABLE)

    async def get_serial_number(self):
        """Request for serial number to Epson."""
        if not self._serial:
            self._serial = await get_serial_number(self, self._host)

        return self._serial
