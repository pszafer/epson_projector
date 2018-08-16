import asyncio
import epson_projector as epson
from epson_projector.const import (POWER)


async def main_serial(loop):
    """Run main with serial connection."""
    await run(loop)


async def run(loop):
    projector = epson.Projector(host='/dev/ttyUSB1',
                                type='serial',
                                loop=loop)
    data = await projector.get_property(POWER)
    print(data)
    projector.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main_serial(loop))
loop.close()
