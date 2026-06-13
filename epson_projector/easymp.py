"""This module gets the serial number of the projector using the same protocol as used by iProjection and EasyMP apps."""

import logging

import asyncio

from .base_connection import BaseProjectorConnection

from .const import (
    POWER,
    EPSON_CODES,
    EASYMP_PORT,
    SERIAL_BYTE,
)
from .error import ProjectorUnavailableError
from .timeout import get_timeout

_LOGGER = logging.getLogger(__name__)


async def get_serial_number(projector_connection: BaseProjectorConnection, host: str) -> str | None:
    """Request for serial number to Epson."""
    try:
        async with asyncio.timeout(10):
            power_on = await projector_connection.get_property(POWER, get_timeout(POWER))
            if power_on == EPSON_CODES[POWER]:
                reader, writer = await asyncio.open_connection(
                    host=host,
                    port=EASYMP_PORT,
                )
                _LOGGER.debug("Asking for serial number.")
                try:
                    writer.write(SERIAL_BYTE)
                    await writer.drain()
                    response = await reader.read(32)
                    serial_number = response[24:].decode()
                    return serial_number
                finally:
                    writer.close()
                    await writer.wait_closed()
            else:
                _LOGGER.error("Is projector turned on?")
    except ProjectorUnavailableError:
        _LOGGER.error(
            "Projector unavailable. Is projector connected and turned on?"
        )
    except asyncio.TimeoutError:
        _LOGGER.error(
            "Timeout error receiving SERIAL of projector. Is projector turned on?"
        )

    return None
