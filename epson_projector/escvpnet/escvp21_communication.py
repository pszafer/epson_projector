import asyncio
import logging

COLON = b":"

_LOGGER = logging.getLogger(__name__)


class EscVp21Exception(Exception):
    """Base exception for ESC/VP21 communication errors."""


class EscVp21CommandError(EscVp21Exception):
    """Raised when there is a command error during ESC/VP21 communication."""


class EscVp21ConnectionError(EscVp21Exception):
    """Raised when there is a connection error during ESC/VP21 communication."""


class EscVp21Communication:
    """Class for ESC/VP21 communication.

    Provides generic Get command and Set command methods following the naming in the ESC/VP21 spec.
    Raises EscVp21CommandError if the projector responds with an error status for a command, and EscVp21ConnectionError for connection issues.
    Timeouts need to be handled by the caller.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer

    async def raw_command(self, command: str) -> str:
        """Send a raw command and return the response string. Raises local exceptions on connection errors."""
        command += "\r"
        try:
            payload = command.encode("ascii")
            _LOGGER.debug("Send: %s", payload)
            self._writer.write(payload)
            await self._writer.drain()

            raw_response = await self._reader.readuntil(COLON)
            _LOGGER.debug("Recv: %s", raw_response.strip())

            response = raw_response[:-1].decode("ascii")  # remove trailing colon
            return response.rstrip("\r")
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as e:
            raise EscVp21ConnectionError(
                "Connection lost or protocol error during read"
            ) from e
        except (
            ConnectionResetError,
            BrokenPipeError,
            ConnectionAbortedError,
            OSError,
        ) as e:
            raise EscVp21ConnectionError("Connection error during communication") from e

    async def get(self, command: str) -> str:
        """Get property value from projector."""
        response = await self.raw_command(command + "?")

        # Extract the value part of the response, e.g. "01" for "PWR? -> PWR=01"
        if (parts := response.split("=", 1)) and len(parts) == 2:
            return parts[1]

        raise EscVp21CommandError(
            f"Command '{command}' failed with response: {response}"
        )

    async def set(self, command: str, value: str) -> None:
        """Set property value on projector and return the raw response."""
        response = await self.raw_command(f"{command} {value}")
        if response:
            raise EscVp21CommandError(
                f"Command '{command}={value}' failed with response: {response}"
            )

    def close(self):
        """Close the underlying connection."""
        if self._writer:
            _LOGGER.debug("Closing ESC/VP.net session")
            self._writer.close()

    @property
    def is_connected(self) -> bool:
        """Deprecated: Only for integration/backward compatibility.

        It is not really an indicator if connection is still alive, just that is it not closed/closing.
        """
        return self._writer is not None and not self._writer.is_closing()
