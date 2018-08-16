"""Test and example of usage of Epson module."""
import epson_projector as epson
from epson_projector.const import (POWER)

import asyncio
import aiohttp


async def main_web():
    """Run main with aiohttp ClientSession."""
    async with aiohttp.ClientSession() as session:
        await run(session)


async def run(websession):
    """Use Projector class of epson module and check if it is turned on."""
    projector = epson.Projector(
        host='192.168.4.131',
        websession=websession,
        port=80,
        type='http',
        encryption=False)
    data = await projector.get_property(POWER)
    print(data)

asyncio.get_event_loop().run_until_complete(main_web())
