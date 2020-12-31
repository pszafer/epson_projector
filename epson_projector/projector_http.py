"""HTTP connection of Epson projector module."""
import logging

import aiohttp
import asyncio
import async_timeout

from .const import (ACCEPT_ENCODING, ACCEPT_HEADER, BUSY,
                    EPSON_KEY_COMMANDS, HTTP_OK, STATE_UNAVAILABLE)
from .projector_tcp import ProjectorTcp
_LOGGER = logging.getLogger(__name__)


class ProjectorHttp:
    """
    Epson projector class.

    Control your projector with Python.
    """

    def __init__(self, host, websession, port=80, encryption=False, loop=None):
        """
        Epson Projector controller.

        :param str ip:          IP address of Projector
        :param int port:        Port to connect to. Default 80.
        :param bool encryption: User encryption to connect

        """
        self._host = host
        self._port = port
        self._encryption = encryption
        http_proto = 'https' if self._encryption else 'http'
        self._http_url = '{http_proto}://{host}:{port}/cgi-bin/'.format(
            http_proto=http_proto,
            host=self._host,
            port=self._port)
        referer = "{http_proto}://{host}:{port}/cgi-bin/webconf".format(
            http_proto=http_proto,
            host=self._host,
            port=self._port)
        self._headers = {
            "Accept-Encoding": ACCEPT_ENCODING,
            "Accept": ACCEPT_HEADER,
            "Referer": referer
        }
        self.websession = websession
        self._loop = loop
        self._tcp_projector = None

    def close(self):
        return

    async def get_serial_number(self, timeout):
        if self._loop and self._host:
            if not self._tcp_projector:
                self._tcp_projector = ProjectorTcp(host=self._host, loop=self._loop)
            test = await self._tcp_projector.get_property("EEMP0100À¨E", timeout)
        return STATE_UNAVAILABLE

    async def get_property(self, command, timeout):
        """Get property state from device."""
        response = await self.send_request(
            timeout=timeout,
            params=EPSON_KEY_COMMANDS[command],
            type='json_query')
        if not response:
            return False
        try:
            if response == STATE_UNAVAILABLE:
                return STATE_UNAVAILABLE
            return response['projector']['feature']['reply']
        except KeyError:
            return BUSY

    async def send_command(self, command, timeout):
        """Send command to Epson."""
        response = await self.send_request(
            timeout=timeout,
            params=EPSON_KEY_COMMANDS[command],
            type='directsend',
            command=command)
        return response

    async def send_request(self, params, timeout,
                           type='json_query', command=False):
        """Send request to Epson."""
        try:
            with async_timeout.timeout(timeout):
                url = '{url}{type}'.format(
                    url=self._http_url,
                    type=type)
                async with self.websession.get(
                    url=url, params=params,
                        headers=self._headers) as response:
                    if response.status != HTTP_OK:
                        _LOGGER.warning(
                            "Error message %d from Epson.", response.status)
                        return False
                    if type == 'json_query':
                        return await response.json()
                    return response
        except (aiohttp.ClientError, aiohttp.ClientConnectionError, TimeoutError, asyncio.exceptions.TimeoutError):
            _LOGGER.error("Error request")
            return STATE_UNAVAILABLE
