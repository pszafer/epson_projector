"""Test and example of usage of Epson module."""
import epson_projector as epson
from epson_projector.const import (POWER, VOLUME)

import asyncio
import aiohttp
import logging

_LOGGER = logging.getLogger(__name__)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
_LOGGER.addHandler(console_handler)
_LOGGER.setLevel(logging.DEBUG)

logging.basicConfig(level=logging.DEBUG)

async def main_web():
    """Run main with aiohttp ClientSession."""
    async with aiohttp.ClientSession() as session:
        await run(session)


async def run(websession):
    """Use Projector class of epson module and check if it is turned on."""
    projector = epson.Projector(
        host='192.168.11.37',
        websession=websession,
        type='http',
        loop=asyncio.get_event_loop(),
        encryption=False)
    data = await projector.get_property(POWER)
    print(data)
    print("dupa")
    # data = await projector.send_request("EEMP0100À¨E")
    # print(data)

asyncio.get_event_loop().run_until_complete(main_web())
