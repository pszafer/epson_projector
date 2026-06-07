"""Behavioral tests for Projector with Serial backend.

The fake serial reader/writer replicate the async stream API that serialx
exposes. Tests go through the public Projector facade.
"""
import asyncio
from collections import deque
from unittest.mock import patch

import pytest

from epson_projector.const import BUSY, POWER, SERIAL, SNO
from epson_projector.projector import Projector


# ---------------------------------------------------------------------------
# Fake serial stream infrastructure
# ---------------------------------------------------------------------------

class _FakeSerialReader:
    """Queues raw byte payloads to hand back on each readuntil() call."""

    def __init__(self, *responses: bytes):
        self._queue = deque(responses)

    async def readuntil(self, separator: bytes) -> bytes:
        if not self._queue:
            raise asyncio.IncompleteReadError(b"", 0)
        return self._queue.popleft()


class _FakeSerialWriter:
    def __init__(self):
        self.written: list[bytes] = []
        self._closing = False

    def write(self, data: bytes) -> None:
        self.written.append(data)

    async def drain(self) -> None:
        pass

    def is_closing(self) -> bool:
        return self._closing

    def close(self) -> None:
        self._closing = True

    async def wait_closed(self) -> None:
        pass


def _make_projector_with_open_serial(*responses: bytes) -> tuple[Projector, _FakeSerialWriter]:
    """Return a Projector whose serial backend is already initialised with
    a fake stream pre-loaded with *responses*."""
    reader = _FakeSerialReader(*responses)
    writer = _FakeSerialWriter()

    projector = Projector("/dev/ttyUSB0", type=SERIAL)
    projector._projector._reader = reader
    projector._projector._writer = writer
    projector._projector._isOpen = True
    return projector, writer


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_serial_get_power_reports_on_state():
    projector, _ = _make_projector_with_open_serial(b"PWR=01\r:")
    assert await projector.get_power() == "01"


async def test_serial_get_power_reports_off_state():
    projector, _ = _make_projector_with_open_serial(b"PWR=04\r:")
    assert await projector.get_power() == "04"


async def test_serial_get_power_preserves_cached_value_on_error_response():
    """When the projector replies with ERR, the previously cached state is kept."""
    projector, _ = _make_projector_with_open_serial(b"PWR=01\r:", b"ERR\r:")

    first = await projector.get_power()
    second = await projector.get_power()

    assert first == "01"
    assert second == "01"


async def test_serial_get_property_returns_power_state():
    projector, _ = _make_projector_with_open_serial(b"PWR=01\r:")
    assert await projector.get_property(POWER) == "01"


async def test_serial_connection_is_established_when_not_open(monkeypatch):
    """When the backend is not yet open, async_init is called transparently."""
    reader = _FakeSerialReader(b":", b"PWR=01\r:")    # hello + query
    writer = _FakeSerialWriter()

    async def fake_open_serial_connection(*, url, baudrate):
        return reader, writer

    with patch("serialx.open_serial_connection", new=fake_open_serial_connection):
        projector = Projector("/dev/ttyUSB0", type=SERIAL)
        # _isOpen is False by default; first call triggers async_init
        value = await projector.get_property(POWER)

    assert value == "01"


async def test_serial_get_property_returns_busy_after_send_command():
    """send_command acquires a timed lock; subsequent get_property returns BUSY."""
    projector, _ = _make_projector_with_open_serial(b":")

    await projector.send_command("PWR ON")
    assert await projector.get_property(POWER) == BUSY


async def test_serial_send_command_rejected_while_locked():
    """A second send_command returns False when a lock is already active."""
    projector, _ = _make_projector_with_open_serial(b":")

    await projector.send_command("PWR ON")
    assert await projector.send_command("SOURCE") is False


async def test_serial_get_serial_number_returns_value():
    """get_serial_number delegates to the SNO property query over serial."""
    projector, _ = _make_projector_with_open_serial(b"SNO=XY12345678\r:")
    assert await projector.get_serial_number() == "XY12345678"
