
import asyncio
import logging

COLON = b":"

_LOGGER = logging.getLogger(__name__)
    
class EscVp21Communication:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer

    async def raw_send(self, payload: str) -> str:
        if self._writer and not self._writer.is_closing():
            self._writer.write(payload.encode("ascii"))
            await self._writer.drain()
            response = await self._reader.readuntil(COLON)
            return response[:-1].decode("ascii")  # remove trailing colon

        raise RuntimeError("ESC/VP.net session is not connected")

    async def get(self, command: str) -> str:
        response = await self.raw_send(command + "?\r")
        if response == "ERR":
            raise RuntimeError(f"Error response to command {command}")
        return response

    async def set(self, command: str, value: str) -> None:
        response = await self.raw_send(f"{command} {value}\r")
        if response == "ERR":
            raise RuntimeError(
                f"Error response to command {command} with value {value}"
            )

    def close(self):
        if self._writer and not self._writer.is_closing():
            _LOGGER.debug("Closing ESC/VP.net session")
            self._writer.close()

    @property
    def is_connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

