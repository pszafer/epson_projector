"""Behavioral tests for Projector with HTTP backend.

All tests go through the public Projector facade. The fake session simulates
the projector's HTTP responses without touching real hardware or sockets.
"""
import aiohttp
import asyncio
import pytest

from epson_projector.const import BUSY, HTTP, POWER
from epson_projector.error import ProjectorUnavailableError
from epson_projector.projector import Projector


# ---------------------------------------------------------------------------
# Minimal fake aiohttp session infrastructure
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status=200, json_data=None):
        self.status = status
        self._json_data = json_data

    async def json(self):
        return self._json_data


class _FakeGetCtx:
    """Async context manager wrapping a pre-built response."""
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *args):
        return False


class _FakeSession:
    """Feeds queued responses for each successive websession.get() call."""
    def __init__(self, *responses):
        self._responses = iter(responses)

    def get(self, **kwargs):
        return next(self._responses)


class _NetworkErrorSession:
    """Always raises a network error when .get() is called."""
    def get(self, **kwargs):
        raise aiohttp.ClientConnectionError("projector unreachable")


def _ok(json_data):
    return _FakeGetCtx(_FakeResponse(200, json_data))

def _error_status(status=500):
    return _FakeGetCtx(_FakeResponse(status))


def _query_json(query, reply, error=False):
    return {
        "projector": {
            "feature": {
                "name": "esc/vp21",
                "query": query,
                "reply": reply,
                "error": error,
            }
        }
    }


def _power_on_json():
    return _query_json("PWR?", "01")

def _power_off_json():
    return _query_json("PWR?", "04")

def _cmode_json(code):
    return _query_json("CMODE?", code)


class _FakeSerialNumberServer:
    def __init__(self, host, port, serial_number, server):
        self.host = host
        self.port = port
        self.serial_number = serial_number
        self._server = server

    async def close(self):
        self._server.close()
        await self._server.wait_closed()


@pytest.fixture
async def fake_serial_number_server():
    serial_number = "HTSN1234"

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_get_power_reports_on_state():
    projector = Projector("192.168.1.100", websession=_FakeSession(_ok(_power_on_json())), type=HTTP)
    assert await projector.get_power() == "01"


async def test_get_power_reports_off_state():
    projector = Projector("192.168.1.100", websession=_FakeSession(_ok(_power_off_json())), type=HTTP)
    assert await projector.get_power() == "04"


async def test_get_power_preserves_last_good_value_after_server_error():
    """A 500 response is a soft failure; the cached power state is returned."""
    session = _FakeSession(_ok(_power_on_json()), _error_status(500))
    projector = Projector("192.168.1.100", websession=session, type=HTTP)

    first = await projector.get_power()
    second = await projector.get_power()

    assert first == "01"
    assert second == "01"


async def test_get_property_returns_value_for_arbitrary_command():
    projector = Projector("192.168.1.100", websession=_FakeSession(_ok(_cmode_json("15"))), type=HTTP)
    assert await projector.get_property("CMODE") == "15"


async def test_network_error_raises_projector_unavailable():
    projector = Projector("192.168.1.100", websession=_NetworkErrorSession(), type=HTTP)

    with pytest.raises(ProjectorUnavailableError):
        await projector.get_property(POWER)


async def test_get_property_returns_busy_immediately_after_send_command():
    """send_command acquires a timed lock; the next get_property returns BUSY."""
    session = _FakeSession(_ok({"status": "ok"}))
    projector = Projector("192.168.1.100", websession=session, type=HTTP)

    await projector.send_command("PWR ON")
    assert await projector.get_property(POWER) == BUSY


async def test_send_command_returns_false_when_already_locked():
    """A second command while one is in-flight is rejected with False."""
    session = _FakeSession(_ok({"status": "ok"}))
    projector = Projector("192.168.1.100", websession=session, type=HTTP)

    await projector.send_command("PWR ON")
    assert await projector.send_command("SOURCE") is False


async def test_send_request_returns_busy_while_locked():
    session = _FakeSession(_ok({"status": "ok"}))
    projector = Projector("192.168.1.100", websession=session, type=HTTP)

    await projector.send_command("PWR ON")
    assert await projector.send_request([("jsoncallback", "PWR?")]) == BUSY


async def test_timeout_scale_does_not_break_get_property():
    """A projector configured for slower responses still returns the correct value."""
    session = _FakeSession(_ok(_power_on_json()))
    projector = Projector("192.168.1.100", websession=session, type=HTTP, timeout_scale=2.0)

    assert await projector.get_property(POWER) == "01"


async def test_get_serial_number_returns_value_when_projector_is_on(
    fake_serial_number_server, monkeypatch
):
    session = _FakeSession(_ok(_power_on_json()))
    projector = Projector(
        fake_serial_number_server.host,
        websession=session,
        type=HTTP,
    )

    monkeypatch.setattr(
        "epson_projector.easymp.EASYMP_PORT",
        fake_serial_number_server.port,
    )

    assert await projector.get_serial_number() == fake_serial_number_server.serial_number
