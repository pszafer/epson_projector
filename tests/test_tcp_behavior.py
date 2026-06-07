"""Behavioral tests for Projector with TCP backend.

A lightweight fake asyncio server speaks the projector's raw ESC/VP.net wire
protocol. Tests go through the public Projector facade; no mocks are used.
"""
import asyncio
from typing import AsyncGenerator

import pytest

from epson_projector.const import BUSY, POWER, TCP
from epson_projector.projector import Projector

# Valid 16-byte hello response: bytes[0:10] == "ESC/VP.net", bytes[14] == 32 (space)
_HELLO_RESPONSE = b"ESC/VP.net\x00\x00\x00\x00\x20\x00"


class _FakeTcpProjector:
    """Fake projector TCP server that speaks the raw ESC/VP.net handshake and
    then answers queued command/query responses one-by-one."""

    def __init__(self, host: str, port: int, _server: asyncio.AbstractServer):
        self.host = host
        self.port = port
        self._server = _server
        self._responses: asyncio.Queue[bytes] = asyncio.Queue()

    def queue(self, response: bytes) -> None:
        self._responses.put_nowait(response)

    async def close(self) -> None:
        self._server.close()
        await self._server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.read(16)           # consume hello from client
            writer.write(_HELLO_RESPONSE)
            await writer.drain()

            while True:
                data = await reader.read(64)
                if not data:
                    break
                reply = await self._responses.get()
                writer.write(reply)
                await writer.drain()
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            writer.close()


class _FakeSerialNumberServer:
    def __init__(self, host: str, port: int, serial_number: str, server):
        self.host = host
        self.port = port
        self.serial_number = serial_number
        self._server = server

    async def close(self) -> None:
        self._server.close()
        await self._server.wait_closed()


@pytest.fixture
async def fake_projector_tcp() -> AsyncGenerator[_FakeTcpProjector, None]:
    server_obj: list[_FakeTcpProjector] = []

    async def factory(reader, writer):
        await server_obj[0]._handle(reader, writer)

    server = await asyncio.start_server(factory, host="127.0.0.1", port=0)
    host, port = server.sockets[0].getsockname()[:2]
    fake = _FakeTcpProjector(host, port, server)
    server_obj.append(fake)
    try:
        yield fake
    finally:
        await fake.close()


@pytest.fixture
async def fake_serial_number_server() -> AsyncGenerator[_FakeSerialNumberServer, None]:
    serial_number = "TCSN9876"

    async def handler(reader, writer):
        try:
            await reader.read(32)
            writer.write((b"X" * 24) + serial_number.encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handler, host="127.0.0.1", port=0)
    host, port = server.sockets[0].getsockname()[:2]
    fake = _FakeSerialNumberServer(host, port, serial_number, server)
    try:
        yield fake
    finally:
        await fake.close()


def _projector(fake: _FakeTcpProjector) -> Projector:
    p = Projector(fake.host, type=TCP)
    p._projector._port = fake.port   # override default 3629 with the ephemeral port
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_tcp_get_power_reports_on_state(fake_projector_tcp):
    fake_projector_tcp.queue(b"PWR=01\r:")
    projector = _projector(fake_projector_tcp)

    assert await projector.get_power() == "01"


async def test_tcp_get_power_preserves_cached_value_on_error_response(fake_projector_tcp):
    """When the projector replies with ERR, the cached power value is returned."""
    fake_projector_tcp.queue(b"PWR=01\r:")
    fake_projector_tcp.queue(b"ERR\r:")
    projector = _projector(fake_projector_tcp)

    first = await projector.get_power()
    second = await projector.get_power()

    assert first == "01"
    assert second == "01"


async def test_tcp_get_property_returns_value(fake_projector_tcp):
    fake_projector_tcp.queue(b"PWR=01\r:")
    projector = _projector(fake_projector_tcp)

    assert await projector.get_property(POWER) == "01"


async def test_tcp_get_property_returns_busy_after_send_command(fake_projector_tcp):
    """send_command acquires a timed lock; subsequent get_property returns BUSY."""
    fake_projector_tcp.queue(b":")
    projector = _projector(fake_projector_tcp)

    await projector.send_command("PWR ON")
    result = await projector.get_property(POWER)

    assert result == BUSY


async def test_tcp_send_command_rejected_while_locked(fake_projector_tcp):
    """A second send_command returns False when a lock is already active."""
    fake_projector_tcp.queue(b":")
    projector = _projector(fake_projector_tcp)

    await projector.send_command("PWR ON")
    assert await projector.send_command("SOURCE") is False


async def test_tcp_get_serial_number_returns_value(
    fake_projector_tcp, fake_serial_number_server, monkeypatch
):
    fake_projector_tcp.queue(b"PWR=01\r:")
    projector = _projector(fake_projector_tcp)

    monkeypatch.setattr(
        "epson_projector.projector_tcp.TCP_SERIAL_PORT",
        fake_serial_number_server.port,
    )

    assert await projector.get_serial_number() == fake_serial_number_server.serial_number
