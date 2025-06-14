#!/usr/bin/env python3

import argparse
import asyncio
import epson_projector as epson
from epson_projector.const import (POWER, PWR_OFF, VOLUME)


async def main_tcp(args):
    """Run main with TCP session."""
    projector = epson.Projector(host=args.host,
                                type='tcp')
    data = await projector.get_power()
    print(data)
    # data2 = await projector.get_property(VOLUME)
    # print(data2)
    # print("VOL @", data2)
    dataa = await projector.get_serial_number()
    print("proj2", dataa)
    # await projector.send_command(PWR_OFF)
    projector.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(  # noqa: F821
        description="Example/test application for Epson Projector package through tcp connection."
    )

    parser.add_argument(
        "host",
        help="Hostname or IP address of the projector.",
    )
    args = parser.parse_args()

    asyncio.run(main_tcp(args))
