from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass, field
from typing import AsyncGenerator

import pytest

from epson_projector.escvpnet.error import (
    EscVpNetBadRequestStatus,
    EscVpNetConnectionError,
    EscVpNetForbiddenStatus,
    EscVpNetProtocolVersionNotSupportedStatus,
    EscVpNetRequestNotAllowedStatus,
    EscVpNetServiceUnavailableStatus,
    EscVpNetUnauthorizedStatus,
    EscVpNetUnknownStatus,
)
from epson_projector.escvpnet.escvpnet import EscVpNet
from epson_projector.escvpnet.headers import (
    CommandType,
    ImTypeHeader,
    PasswordHeader,
    ProjectorCommandTypeHeader,
    ProjectorNameHeader,
)
from epson_projector.escvpnet.message import Message, MessageStatus, MessageType


@dataclass
class _PlannedResponse:
    status: MessageStatus | None = None
    payload: bytes | None = None
    keep_open: bool = False


@dataclass
class _FakeEscVpNetServer:
    host: str
    port: int
    _server: asyncio.AbstractServer
    requests: list[Message] = field(default_factory=list)
    _planned_responses: asyncio.Queue[_PlannedResponse] = field(
        default_factory=asyncio.Queue
    )

    def queue_status(self, status: MessageStatus, *, keep_open: bool = False) -> None:
        self._planned_responses.put_nowait(
            _PlannedResponse(status=status, keep_open=keep_open)
        )

    def queue_payload(self, payload: bytes) -> None:
        self._planned_responses.put_nowait(_PlannedResponse(payload=payload))

    async def close(self) -> None:
        self._server.close()
        await self._server.wait_closed()


async def _start_fake_server() -> _FakeEscVpNetServer:
    requests: list[Message] = []
    planned_responses: asyncio.Queue[_PlannedResponse] = asyncio.Queue()

    async def _handler(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request = await Message.from_stream(reader)
            requests.append(request)

            response = await planned_responses.get()
            if response.payload is not None:
                writer.write(response.payload)
                await writer.drain()
                return

            assert response.status is not None
            reply = Message(
                type_id=request.type_id,
                status=response.status,
            )
            writer.write(reply.to_bytes())
            await writer.drain()

            if response.keep_open:
                await reader.read(1)
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(_handler, host="127.0.0.1", port=0)
    sock = server.sockets[0]
    host, port = sock.getsockname()[0:2]

    return _FakeEscVpNetServer(
        host=host,
        port=port,
        _server=server,
        requests=requests,
        _planned_responses=planned_responses,
    )


@pytest.fixture
async def fake_tcp_server() -> AsyncGenerator[_FakeEscVpNetServer, None]:
    server = await _start_fake_server()
    try:
        yield server
    finally:
        await server.close()


class _FakeDiscoverTransport:
    def __init__(self, responses: list[tuple[str, bytes]], protocol) -> None:
        self._responses = responses
        self._protocol = protocol
        self.closed = False

    def sendto(self, data: bytes, _addr: tuple[str, int]) -> None:
        # EscVpNet.discover() should ignore the echoed request because status is REQUEST.
        self._protocol.datagram_received(data, ("127.0.0.1", 3629))

        for ip, payload in self._responses:
            self._protocol.datagram_received(payload, (ip, 3629))

    def close(self) -> None:
        self.closed = True


class _FakeDiscoverLoop:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        responses: list[tuple[str, bytes]],
    ) -> None:
        self._loop = loop
        self._responses = responses
        self.transport: _FakeDiscoverTransport | None = None

    def create_future(self) -> asyncio.Future:
        return self._loop.create_future()

    async def create_datagram_endpoint(
        self,
        protocol_factory,
        local_addr,
        reuse_port,
        allow_broadcast,
    ):
        assert local_addr == ("0.0.0.0", 3629)
        assert reuse_port is True
        assert allow_broadcast is True

        protocol = protocol_factory()
        transport = _FakeDiscoverTransport(self._responses, protocol)
        self.transport = transport
        protocol.connection_made(transport)
        return (transport, protocol)


async def test_connect_success_keeps_connection_open(
    fake_tcp_server: _FakeEscVpNetServer,
):
    fake_tcp_server.queue_status(MessageStatus.OK, keep_open=True)

    client = EscVpNet(host=fake_tcp_server.host, port=fake_tcp_server.port)
    reader, writer = await client.connect()

    assert reader is not None
    assert writer.is_closing() is False
    assert len(fake_tcp_server.requests) == 1
    assert fake_tcp_server.requests[0].type_id == MessageType.CONNECT
    assert fake_tcp_server.requests[0].headers == []

    writer.close()
    await writer.wait_closed()


@pytest.mark.parametrize(
    ("status", "expected_exception"),
    [
        (MessageStatus.BAD_REQUEST, EscVpNetBadRequestStatus),
        (MessageStatus.UNAUTHORIZED, EscVpNetUnauthorizedStatus),
        (MessageStatus.FORBIDDEN, EscVpNetForbiddenStatus),
        (MessageStatus.REQUEST_NOT_ALLOWED, EscVpNetRequestNotAllowedStatus),
        (MessageStatus.SERVICE_UNAVAILABLE, EscVpNetServiceUnavailableStatus),
        (
            MessageStatus.PROTOCOL_VERSION_NOT_SUPPORTED,
            EscVpNetProtocolVersionNotSupportedStatus,
        ),
    ],
)
async def test_connect_raises_mapped_status_exceptions(
    fake_tcp_server: _FakeEscVpNetServer,
    status: MessageStatus,
    expected_exception: type[Exception],
):
    fake_tcp_server.queue_status(status)

    client = EscVpNet(host=fake_tcp_server.host, port=fake_tcp_server.port)
    with pytest.raises(expected_exception):
        await client.connect()


async def test_connect_with_unknown_status_raises_unknown_status(
    fake_tcp_server: _FakeEscVpNetServer,
):
    fake_tcp_server.queue_payload(
        Message(type_id=MessageType.CONNECT, status=MessageStatus.OK)
        .to_bytes()
        .replace(bytes([MessageStatus.OK]), b"\x99", 1)
    )

    client = EscVpNet(host=fake_tcp_server.host, port=fake_tcp_server.port)
    with pytest.raises(EscVpNetUnknownStatus):
        await client.connect()


async def test_connect_includes_password_header_when_password_is_set(
    fake_tcp_server: _FakeEscVpNetServer,
):
    fake_tcp_server.queue_status(MessageStatus.OK, keep_open=True)

    client = EscVpNet(
        host=fake_tcp_server.host, port=fake_tcp_server.port, password="secret"
    )
    _reader, writer = await client.connect()

    headers = fake_tcp_server.requests[0].headers
    assert len(headers) == 1
    assert isinstance(headers[0], PasswordHeader)

    writer.close()
    await writer.wait_closed()


@pytest.mark.parametrize(
    "status",
    [
        MessageStatus.UNAUTHORIZED,
        MessageStatus.FORBIDDEN,
        MessageStatus.SERVICE_UNAVAILABLE,
        MessageStatus.BAD_REQUEST,
        MessageStatus.REQUEST_NOT_ALLOWED,
        MessageStatus.PROTOCOL_VERSION_NOT_SUPPORTED,
    ],
)
async def test_confirm_password_returns_false_for_non_ok_status(
    fake_tcp_server: _FakeEscVpNetServer,
    status: MessageStatus,
):
    fake_tcp_server.queue_status(status)

    client = EscVpNet(
        host=fake_tcp_server.host, port=fake_tcp_server.port, password="pw"
    )
    assert await client.confirm_password() is False


async def test_confirm_password_returns_true_for_ok_status(
    fake_tcp_server: _FakeEscVpNetServer,
):
    fake_tcp_server.queue_status(MessageStatus.OK)

    client = EscVpNet(host=fake_tcp_server.host, port=fake_tcp_server.port)
    assert await client.confirm_password() is True


@pytest.mark.parametrize(
    ("status", "expected_exception"),
    [
        (MessageStatus.BAD_REQUEST, EscVpNetBadRequestStatus),
        (MessageStatus.UNAUTHORIZED, EscVpNetUnauthorizedStatus),
        (MessageStatus.FORBIDDEN, EscVpNetForbiddenStatus),
        (MessageStatus.REQUEST_NOT_ALLOWED, EscVpNetRequestNotAllowedStatus),
        (MessageStatus.SERVICE_UNAVAILABLE, EscVpNetServiceUnavailableStatus),
        (
            MessageStatus.PROTOCOL_VERSION_NOT_SUPPORTED,
            EscVpNetProtocolVersionNotSupportedStatus,
        ),
    ],
)
async def test_change_password_raises_mapped_status_exceptions(
    fake_tcp_server: _FakeEscVpNetServer,
    status: MessageStatus,
    expected_exception: type[Exception],
):
    fake_tcp_server.queue_status(status)

    client = EscVpNet(
        host=fake_tcp_server.host, port=fake_tcp_server.port, password="old"
    )
    with pytest.raises(expected_exception):
        await client.change_password("new")


async def test_change_password_success(fake_tcp_server: _FakeEscVpNetServer):
    fake_tcp_server.queue_status(MessageStatus.OK)

    client = EscVpNet(
        host=fake_tcp_server.host, port=fake_tcp_server.port, password="old"
    )
    await client.change_password("new")

    sent = fake_tcp_server.requests[0]
    assert sent.type_id == MessageType.PASSWORD
    assert len(sent.headers) == 2
    assert isinstance(sent.headers[0], PasswordHeader)
    assert sent.headers[0].to_bytes()[1] == 1
    assert sent.headers[1].id().name == "NEW_PASSWORD"


async def test_discover_returns_only_valid_hello_responses(
    monkeypatch: pytest.MonkeyPatch,
):
    valid_hello = Message(
        type_id=MessageType.HELLO,
        status=MessageStatus.OK,
        headers=[
            ProjectorNameHeader("EPSON Name"),
            ImTypeHeader(56),
            ProjectorCommandTypeHeader(CommandType.ESC_VP21_V1_0),
        ],
    ).to_bytes()
    wrong_status = Message(
        type_id=MessageType.HELLO,
        status=MessageStatus.REQUEST,
        headers=[],
    ).to_bytes()
    missing_headers = Message(
        type_id=MessageType.HELLO,
        status=MessageStatus.OK,
        headers=[ProjectorNameHeader("NO-IMTYPE")],
    ).to_bytes()

    loop = asyncio.get_running_loop()
    fake_loop = _FakeDiscoverLoop(
        loop,
        responses=[
            ("192.168.1.10", valid_hello),
            ("192.168.1.11", wrong_status),
            ("192.168.1.12", missing_headers),
        ],
    )

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: fake_loop)

    discovered = await EscVpNet.discover(response_wait_time=0)

    assert len(discovered) == 1
    assert discovered[0].ip == "192.168.1.10"
    assert discovered[0].projector_name == "EPSON Name"
    assert discovered[0].im_type == 56
    assert discovered[0].command_type == CommandType.ESC_VP21_V1_0
    assert fake_loop.transport is not None
    assert fake_loop.transport.closed is True


async def test_discover_raises_on_malformed_response(monkeypatch: pytest.MonkeyPatch):
    loop = asyncio.get_running_loop()
    fake_loop = _FakeDiscoverLoop(
        loop,
        responses=[("192.168.1.20", b"broken")],
    )
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: fake_loop)

    with pytest.raises(asyncio.IncompleteReadError):
        await EscVpNet.discover(response_wait_time=0)


async def test_confirm_password_connection_refused_maps_to_connection_error():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()

    client = EscVpNet(host=host, port=port)

    with pytest.raises(EscVpNetConnectionError, match="Connection refused"):
        await client.confirm_password()


async def test_change_password_timeout_maps_to_connection_error(
    monkeypatch: pytest.MonkeyPatch,
):
    async def _slow_open_connection(*_args, **_kwargs):
        await asyncio.sleep(0.01)

    import epson_projector.escvpnet.escvpnet as escvpnet_module

    monkeypatch.setattr(escvpnet_module, "COMMAND_TIMEOUT", 0)
    monkeypatch.setattr(asyncio, "open_connection", _slow_open_connection)

    client = EscVpNet(host="127.0.0.1", port=1)
    with pytest.raises(EscVpNetConnectionError, match="Timeout"):
        await client.change_password("new")


async def test_connect_incomplete_read_maps_to_connection_error(
    fake_tcp_server: _FakeEscVpNetServer,
):
    partial = Message(type_id=MessageType.CONNECT, status=MessageStatus.OK).to_bytes()[
        :8
    ]
    fake_tcp_server.queue_payload(partial)

    client = EscVpNet(host=fake_tcp_server.host, port=fake_tcp_server.port)
    with pytest.raises(EscVpNetConnectionError, match="Connection closed"):
        await client.connect()


async def test_verify_password_validation_failures():
    with pytest.raises(ValueError, match="maximum length"):
        EscVpNet(host="127.0.0.1", password="x" * 17)

    with pytest.raises(ValueError, match="ASCII"):
        EscVpNet(host="127.0.0.1", password="päss")
