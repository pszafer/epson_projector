#!/usr/bin/env python3

"""Test and example of usage of Epson module."""
import argparse
import epson_projector as epson
from epson_projector.const import POWER, VOLUME, PWR_ON

import asyncio
import aiohttp
import logging

_LOGGER = logging.getLogger(__name__)


async def main_web(args):
    """Run main with aiohttp ClientSession."""

    """Use Projector class of epson module and check if it is turned on."""
    projector = epson.Projector.create_http(
        host=args.host,
        password=args.password,
        port=args.port,
    )

    data = await projector.get_property(POWER)
    print(data)
    data = await projector.get_serial_number()
    print(data)
#    await projector.send_command(PWR_ON)
    # data = await projector.send_request("EEMP0100À¨E")
    # print(data)

    await projector.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Example/test application for Epson Projector package through http connection."
    )

    parser.add_argument(
        "host",
        help="Hostname or IP address of the projector.",
    )
    parser.add_argument(
        "--port",
        help="Port of the projector. Usually not needed, but helpful when connecting to an emulator.",
        default=80,
    )
    parser.add_argument(
        "--password",
        help="Password for the projector. Leave empty if not needed.",
    )
    parser.add_argument(
        "--loglevel",
        help="Set the logging level. Default is INFO.",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel)

    asyncio.run(main_web(args))
