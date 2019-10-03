import asyncio
import epson_projector as epson
from epson_projector.const import (POWER, PWR_ON, PWR_OFF)
import logging

_LOGGER = logging.getLogger(__name__)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
_LOGGER.addHandler(console_handler)
_LOGGER.setLevel(logging.DEBUG)

logging.basicConfig(level=logging.DEBUG)

async def main_serial(loop):
    """Run main with serial connection."""
    await run(loop)


async def run(loop):
    projector = epson.Projector(host='/dev/ttyUSB0',
                                type='serial',
                                loop=loop, timeout_scale=2.0)
    data = await projector.get_property(POWER)
    print(data)
    cmd = None
    if data == '01':
        cmd = PWR_OFF
    elif data == '00':
        cmd = PWR_ON
    if cmd:
        data2 = await projector.send_command(cmd)
        print(data2)
    projector.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main_serial(loop))
loop.close()
