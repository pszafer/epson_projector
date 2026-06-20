"""Behavioral tests for Projector with TCP backend.

A lightweight fake asyncio server speaks the projector's raw ESC/VP.net wire
protocol. Tests go through the public Projector facade; no mocks are used.
"""
import asyncio
from typing import AsyncGenerator

import pytest

from epson_projector.const import BUSY, POWER
from epson_projector.imevent import AlarmType, ProjectorStatus, WarningType
from epson_projector.projector import Projector
from epson_projector.projector_tcp import ProjectorTcp

# Valid 16-byte Connect response: 
# bytes[0:10] == "ESC/VP.net"
# bytes[10] == 0x10 == Protocol version 1.0
# bytes[11] == 0x01 == Type CONNECT
# bytes[14] == 0x20 == Status OK
_CONNECT_RESPONSE = b"ESC/VP.net\x10\x01\x00\x00\x20\x00"

class _FakeTcpProjector:
    """Fake projector TCP server that speaks the raw ESC/VP.net CONNECT handshake and
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
            await reader.read(16)           # consume message from client
            writer.write(_CONNECT_RESPONSE)
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


@pytest.fixture
async def projector(fake_projector_tcp: _FakeTcpProjector) -> AsyncGenerator[Projector, None]:
    connection = ProjectorTcp(fake_projector_tcp.host, port=fake_projector_tcp.port)
    p = Projector(connection=connection)
    try:
        yield p
    finally:
        await p.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_tcp_get_power_reports_on_state(fake_projector_tcp, projector):
    fake_projector_tcp.queue(b"PWR=01\r:")

    assert await projector.get_power() == "01"


async def test_tcp_get_power_preserves_cached_value_on_error_response(fake_projector_tcp, projector):
    """When the projector replies with ERR, the cached power value is returned."""
    fake_projector_tcp.queue(b"PWR=01\r:")
    fake_projector_tcp.queue(b"ERR\r:")

    first = await projector.get_power()
    second = await projector.get_power()

    assert first == "01"
    assert second == "01"


async def test_tcp_get_property_returns_value(fake_projector_tcp, projector):
    fake_projector_tcp.queue(b"PWR=01\r:")

    assert await projector.get_property(POWER) == "01"


async def test_tcp_get_property_returns_busy_after_send_command(fake_projector_tcp, projector):
    """send_command acquires a timed lock; subsequent get_property returns BUSY."""
    fake_projector_tcp.queue(b":")

    await projector.send_command("PWR ON")
    result = await projector.get_property(POWER)

    assert result == BUSY


async def test_tcp_send_command_rejected_while_locked(fake_projector_tcp, projector):
    """A second send_command returns False when a lock is already active."""
    fake_projector_tcp.queue(b":")

    await projector.send_command("PWR ON")
    assert await projector.send_command("SOURCE") is False


async def test_tcp_get_serial_number_returns_value(
    fake_projector_tcp, projector, fake_serial_number_server, monkeypatch
):
    fake_projector_tcp.queue(b"PWR=01\r:")

    monkeypatch.setattr(
        "epson_projector.easymp.EASYMP_PORT",
        fake_serial_number_server.port,
    )

    assert await projector.get_serial_number() == fake_serial_number_server.serial_number


async def test_tcp_on_imevent_callback_triggered(fake_projector_tcp):
    received = []

    def on_imevent(event):
        received.append(event)

    projector_tcp = ProjectorTcp(
        host=fake_projector_tcp.host,
        port=fake_projector_tcp.port,
        on_imevent=on_imevent,
    )

    fake_projector_tcp.queue(
        b"IMEVENT=0001 03 00000002 00000000 T1 F1\r:PWR=01\r:"
    )

    try:
        assert await projector_tcp.get_property(POWER, timeout=1) == "01"
        assert len(received) == 1
        assert received[0].event_code == 1
        assert received[0].power_status == ProjectorStatus.NORMAL
        assert received[0].warning_type == WarningType.NO_SIGNAL
        assert received[0].alarm_type == AlarmType(0)
    finally:
        await projector_tcp.close()
