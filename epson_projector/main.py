"""Main of Epson projector module."""
import logging

from aiohttp.hdrs import USER_AGENT, CONTENT_TYPE
import aiohttp
import async_timeout

import asyncio

import os
os.environ['PYTHONASYNCIODEBUG'] = '1'

import ssl
import certifi
import logging

ACCEPT_ENCODING = "gzip, deflate"
ACCEPT_HEADER = "application/json, text/javascript"

SERVER_SOFTWARE = "Epson aiohttp Python"

_LOGGER = logging.getLogger(__name__)

EPSON_KEY_COMMANDS = {
    "TURN_ON": [('KEY', '3B')],
    "TURN_OFF": [('KEY', '3B'), ('KEY', '3B')],
    "HDMILINK": [('jsoncallback', 'HDMILINK?')],
    "PWR": [('jsoncallback', 'PWR?')],
    "SOURCE": [('jsoncallback', 'SOURCE?')],
    "CMODE": [('jsoncallback', 'CMODE?')],
    "VOLUME": [('jsoncallback', 'VOL?')],
    "CMODE_AUTO": [('CMODE', '00')],
    "CMODE_CINEMA": [('CMODE', '15')],
    "CMODE_NATURAL": [('CMODE', '07')],
    "CMODE_BRIGHT": [('CMODE', '0C')],
    "CMODE_DYNAMIC": [('CMODE', '06')],
    "CMODE_3DDYNAMIC": [('CMODE', '18')],
    "CMODE_3DCINEMA": [('CMODE', '17')],
    "CMODE_3DTHX": [('CMODE', '19')],
    "CMODE_BWCINEMA": [('CMODE', '20')],
    "CMODE_ARGB": [('CMODE', '21')],
    "CMODE_DCINEMA": [('CMODE', '22')],
    "CMODE_THX": [('CMODE', '13')],
    "CMODE_GAME": [('CMODE', '0D')],
    "CMODE_STAGE": [('CMODE', '16')],
    "CMODE_AUTOCOLOR": [('CMODE', 'C1')],
    "CMODE_XV": [('CMODE', '0B')],
    "CMODE_THEATRE": [('CMODE', '05')],
    "CMODE_THEATREBLACK": [('CMODE', '09')],
    "CMODE_THEATREBLACK2": [('CMODE', '0A')],
    "VOL_UP": [('KEY', '56')],
    "VOL_DOWN": [('KEY', '57')],
    "MUTE": [('KEY', 'D8')],
    "HDMI1": [('KEY', '4D')],
    "HDMI2": [('KEY', '40')],
    "PC": [('KEY', '44')],
    "VIDEO": [('KEY', '46')],
    "USB": [('KEY', '85')],
    "LAN": [('KEY', '53')],
    "WFD": [('KEY', '56')],
    "PLAY": [('KEY', 'D1')],
    "PAUSE": [('KEY', 'D3')],
    "STOP": [('KEY', 'D2')],
    "BACK": [('KEY', 'D4')],
    "FAST": [('KEY', 'D5')],
}

TIMEOUT_TIMES = {
    'TURN_ON': 40,
    'TURN_OFF': 10,
    'SOURCE': 5,
    'ALL': 3
}

DEFAULT_SOURCES = {
    'HDMI1': 'HDMI1',
    'HDMI2': 'HDMI2',
    'PC': 'PC',
    'VIDEO': 'VIDEO',
    'USB': 'USB',
    'LAN': 'LAN',
    'WFD': 'WiFi Direct'
}

SOURCE_LIST = {
    '30': 'HDMI1',
    '10': 'PC',
    '40': 'VIDEO',
    '52': 'USB',
    '53': 'LAN',
    '56': 'WDF',
    'A0': 'HDMI2'
}

INV_SOURCES = {v: k for k, v in DEFAULT_SOURCES.items()}

CMODE_LIST = {
    '00': 'Auto',
    '15': 'Cinema',
    '07': 'Natural',
    '0C': 'Bright Cinema/Living',
    '06': 'Dynamic',
    '17': '3D Cinema',
    '18': '3D Dynamic',
    '19': '3D THX',
    '20': 'B&W Cinema',
    '21': 'Adobe RGB',
    '22': 'Digital Cinema',
    '13': 'THX',
    '0D': 'Game',
    '16': 'Stage',
    'C1': 'AutoColor',
    '0B': 'x.v. color',
    '05': 'Theatre',
    '09': 'Theatre Black 1/HD',
    '0A': 'Theatre Black 2/Silver Screen'
}

CMODE_LIST_SET = {
    'cinema': 'CMODE_CINEMA',
    'natural': 'CMODE_NATURAL',
    'bright cinema': 'CMODE_BRIGHT',
    'dynamic': 'CMODE_DYNAMIC',
    '3ddynamic': 'CMODE_3DDYNAMIC',
    '3dcinema': 'CMODE_3DCINEMA',
    'auto': 'CMODE_AUTO',
    '3dthx': 'CMODE_3DTHX',
    'bwcinema': 'CMODE_BWCINEMA',
    'adobe rgb': 'CMODE_ARGB',
    'digital cinema': 'CMODE_DCINEMA',
    'thx': 'CMODE_THX',
    'game': 'CMODE_GAME',
    'stage': 'CMODE_STAGE',
    'autocolor': 'CMODE_AUTOCOLOR',
    'xv': 'CMODE_XV',
    'theatre': 'CMODE_THEATRE',
    'theatre black': 'CMODE_THEATREBLACK',
    'theatre black 2': 'CMODE_THEATREBLACK2'
}


class Projector(object):
    """
    Epson projector class.

    Control your projector with Python.
    """

    def __init__(self, host, port=80, encryption=False):
        """
        Epson Projector controller.

        :param str ip:          IP address of Projector
        :param int port:        Port to connect to. Default 80.
        :param bool encryption: User encryption to connect

        """
        self._host = host
        self._port = port
        self._encryption = encryption
        if self._encryption:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            ssl_context.load_verify_locations(
                cafile=certifi.where(),
                capath=None)
        else:
            ssl_context = False
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
        _LOGGER.warning("TEST1")
        loop = asyncio.get_event_loop()
        tcpconnection = aiohttp.TCPConnector(loop=loop, ssl=ssl_context)
        self.websession = aiohttp.ClientSession(loop=loop,
            connector=tcpconnection
        )

    @asyncio.coroutine
    def get_property(self, command):
        """Get property state from device."""
        _LOGGER.info("enter get")
        print("TEST2")
        try:
            if command in TIMEOUT_TIMES:
                timeout = TIMEOUT_TIMES[command]
            else:
                timeout = TIMEOUT_TIMES['ALL']
            print(timeout)
            with async_timeout.timeout(timeout):
                response = yield from self.websession.get(
                    url='{url}{type}'.format(
                        url=self._http_url,
                        type='json_query'),
                    params=EPSON_KEY_COMMANDS[command],
                    headers=self._headers)
                if response.status != HTTP_OK:
                    _LOGGER.warning(
                        "Error message %d from Epson.", response.status)
                    return False
                resp = yield from response.json()
                reply_code = resp['projector']['feature']['reply']
                return reply_code
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error getting info")
            self._state = STATE_OFF
            return False
        return True

    @asyncio.coroutine
    def send_command(self, command):
        """Send command to Epson."""
        _LOGGER.debug("COMMAND %s", command)
        params = self.key_commands[command]
        try:
            if command in TIMEOUT_TIMES:
                timeout = TIMEOUT_TIMES[command]
            else:
                timeout = TIMEOUT_TIMES['ALL']
            with async_timeout.timeout(timeout):
                url = '{url}{type}'.format(
                    url=self._http_url,
                    type='directsend')
                response = yield from self.websession.get(
                    url,
                    params=params,
                    headers=self._headers)
            if response.status != HTTP_OK:
                return None
            return True
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error sending command")
        return None

    @asyncio.coroutine
    def test(self, comm):
        prop = self.get_property(comm)
        return prop
