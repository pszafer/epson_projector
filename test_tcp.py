import asyncio
import epson_projector as epson
from epson_projector.const import (POWER, PWR_OFF, VOLUME)


async def main_tcp(loop):
    """Run main with TCP session."""
    await run(loop)


async def run(loop):
    projector = epson.Projector(host='192.168.11.37',
                                type='tcp',
                                loop=loop)
    data = await projector.get_power()
    print(data)
    # data2 = await projector.get_property(VOLUME)
    # print(data2)
    # print("VOL @", data2)
    dataa = await projector.get_serial_number()
    print("proj2", dataa)
    # await projector.send_command(PWR_OFF)
    # projector.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main_tcp(loop))
loop.close()
