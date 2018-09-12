import asyncio
import epson_projector as epson
from epson_projector.const import (POWER)
import logging

_LOGGER = logging.getLogger(__name__)


async def main_serial(loop):
    """Run main with serial connection."""
    await run(loop)


async def run(loop):
    projector = epson.Projector(host='/dev/ttyVirtualS0',
                                type='serial',
                                loop=loop)
    data = await projector.get_property(POWER)
    print(data)
    data2 = await projector.send_command(POWER)
    print(data2)
    projector.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main_serial(loop))
loop.close()
