"""Main of Epson projector module."""
import logging
import time

import aiohttp
import async_timeout

from .const import (ACCEPT_ENCODING, ACCEPT_HEADER, ALL, BUSY,
                    EPSON_KEY_COMMANDS, HTTP_OK, INV_SOURCES, SOURCE,
                    TIMEOUT_TIMES, TURN_OFF, TURN_ON)

_LOGGER = logging.getLogger(__name__)


class Projector:
    """
    Epson projector class.

    Control your projector with Python.
    """

    def __init__(self, host, websession, port=80, encryption=False):
        """
        Epson Projector controller.

        :param str ip:          IP address of Projector
        :param int port:        Port to connect to. Default 80.
        :param bool encryption: User encryption to connect

        """
        self._host = host
        self._port = port
        self._encryption = encryption
        self._powering_on = False
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
        self.__initLock()

    def __initLock(self):
        """Init lock for sending request to projector when it is busy."""
        self._isLocked = False
        self._timer = 0
        self._operation = False

    def __setLock(self, command):
        """Set lock on requests."""
        if command in (TURN_ON, TURN_OFF):
            self._operation = command
        elif command in INV_SOURCES:
            self._operation = SOURCE
        else:
            self._operation = ALL
        self._isLocked = True
        self._timer = time.time()

    def __unLock(self):
        """Unlock sending requests to projector."""
        self._operation = False
        self._timer = 0
        self._isLocked = False

    def __checkLock(self):
        """
        Lock checking.

        Check if there is lock pending and check if enough time
        passed so requests can be unlocked.
        """
        if self._isLocked:
            if (time.time() - self._timer) > TIMEOUT_TIMES[self._operation]:
                self.__unLock()
                return False
            return True
        return False

    async def get_property(self, command):
        """Get property state from device."""
        _LOGGER.debug("Getting property %s", command)
        if self.__checkLock():
            return BUSY
        timeout = self.__get_timeout(command)
        response = await self.send_request(
            timeout=timeout,
            params=EPSON_KEY_COMMANDS[command],
            type='json_query')
        if not response:
            return False
        try:
            return response['projector']['feature']['reply']
        except KeyError:
            return BUSY

    async def send_command(self, command):
        """Send command to Epson."""
        _LOGGER.debug("Sending command to projector %s", command)
        if self.__checkLock():
            return False
        self.__setLock(command)
        response = await self.send_request(
            timeout=self.__get_timeout(command),
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
                    if command == TURN_ON and self._powering_on:
                        self._powering_on = False
                    if type == 'json_query':
                        return await response.json()
                    return response
        except (aiohttp.ClientError, aiohttp.ClientConnectionError):
            _LOGGER.error("Error request")
            return False

    def __get_timeout(self, command):
        if command in TIMEOUT_TIMES:
            return TIMEOUT_TIMES[command]
        else:
            return TIMEOUT_TIMES['ALL']
