#!/usr/bin/env python3

import argparse
import asyncio
from getpass import getpass
import epson_projector as epson
from epson_projector.const import (POWER, PWR_OFF, VOLUME)


async def main_tcp(args):
    """Run main with TCP session."""
    password = None
    if args.password:
        password = getpass()

    projector = epson.Projector(host=args.host, type='tcp', tcp_password=password)

    data = await projector.get_power()
    print("Power:", data)

    data = await projector.get_property(VOLUME)
    print("VOL:", data)

    data = await projector.get_serial_number()
    print("Serialnumber:", data)

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
    parser.add_argument(
        "--password",
        action='store_true',
        help="Ask for password",
    )
    args = parser.parse_args()

    asyncio.run(main_tcp(args))
