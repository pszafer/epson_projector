#!/usr/bin/env python3

"""Test and example of usage of Epson module."""
import argparse
import epson_projector as epson
from epson_projector.const import POWER, VOLUME, PWR_ON

import asyncio
import aiohttp
import logging

_LOGGER = logging.getLogger(__name__)

console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
_LOGGER.addHandler(console_handler)
_LOGGER.setLevel(logging.DEBUG)

logging.basicConfig(level=logging.DEBUG)


async def main_web(args):
    """Run main with aiohttp ClientSession."""

    middlewares = []
    if args.password:
        _LOGGER.info("Using password for authentication")
        digest_auth = aiohttp.DigestAuthMiddleware(
            login="EPSONWEB", password=args.password
        )
        middlewares.append(digest_auth)

    async with aiohttp.ClientSession(middlewares=middlewares) as websession:
        """Use Projector class of epson module and check if it is turned on."""
        projector = epson.Projector(
            host=args.host,
            websession=websession,
            type="http",
            http_port=args.port,
        )
        data = await projector.get_property(POWER)
        print(data)
    #    await projector.send_command(PWR_ON)
        # data = await projector.send_request("EEMP0100À¨E")
        # print(data)


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
    args = parser.parse_args()

    asyncio.run(main_web(args))
