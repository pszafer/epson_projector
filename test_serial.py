#!/usr/bin/env python3

import argparse
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

async def main_serial(args):
    """Run main with serial connection."""
    projector = epson.Projector(host=args.serial_url,
                                type='serial',
                                timeout_scale=2.0)
    data = await projector.get_power()
    print(data)
    cmd = None
    if data == '01':
        cmd = PWR_OFF
    elif data == '00':
        cmd = PWR_ON
    if cmd:
        data2 = await projector.send_command(cmd)
        print(data2)

    serialno = await projector.get_serial_number()
    print("Projector serial number:", serialno)
    projector.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Example/test application for Epson Projector package through serial connection."
    )

    parser.add_argument(
        "serial_url",
        help="Can be a devicename like /dev/ttyUSB0 or COM3 for real serial port or use socket://<ip-or-host>:<port> for connections to tcp-to-serial solutions.",
    )
    args = parser.parse_args()

    asyncio.run(main_serial(args))
