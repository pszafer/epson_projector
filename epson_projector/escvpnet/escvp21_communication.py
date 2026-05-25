import asyncio
import logging

COLON = b":"

_LOGGER = logging.getLogger(__name__)


class EscVp21Communication:
    """Class for ESC/VP21 communication.

    Provides generic Get command and Set command methods following the naming in the ESC/VP21 spec.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer

    async def _raw_send(self, payload: str) -> str:
        # TODO: Catch some exceptions and raise more local ones (e.g. connection error)
        self._writer.write(payload.encode("ascii"))
        await self._writer.drain()
        response = await self._reader.readuntil(COLON)
        return response[:-1].decode("ascii")  # remove trailing colon

    async def get(self, command: str) -> str:
        """Get property value from projector."""
        response = await self._raw_send(command + "?\r")
        # TODO: Raise a local exception, not generic RuntimeError
        # if response == "ERR":
        #     raise RuntimeError(f"Error response to command {command}")
        return response

    async def set(self, command: str, value: str) -> None:
        """Set property value on projector."""
        response = await self._raw_send(f"{command} {value}\r")
        # TODO: Raise a local exception, not generic RuntimeError
        # if response == "ERR":
        #     raise RuntimeError(
        #         f"Error response to command {command} with value {value}"
        #     )

    def close(self):
        """Close the underlying connection."""
        if self._writer and not self._writer.is_closing():
            _LOGGER.debug("Closing ESC/VP.net session")
            self._writer.close()

    @property
    def is_connected(self) -> bool:
        """Deprecated: Only for integration/backward compatibility.

        It is not really an indicator if connection is still alive, just that is it not closed/closing.
        """
        return self._writer is not None and not self._writer.is_closing()
