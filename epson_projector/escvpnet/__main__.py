from __future__ import annotations

import argparse
import asyncio
import getpass
import logging


from .error import EscVpNetForbiddenStatus, EscVpNetUnauthorizedStatus
from .escvpnet import EscVpNet

ESCVPNET_COMMAND_EXTENSIONS = [
    "NWTRAPIP1?",
    "NWTRAPIP2?",
    "NWONAME?",
    "NWCNAME?",
    "NWMAC?",
    "NWSMTPTO1?",
    "NWSMTPTO2?",
    "NWSMTPTO3?",
    "NWSMTPSVR?",
    "NWSMTPPORT?",
    "NWSMTPEVT1?",
    "NWSMTPEVT2?",
    "NWSMTPEVT3?",
    "NWSMTPACT?",
    "NWCNF?",
    "NWWLCNF?",
    "NWWINS?",
    "NWDNS?",
    "NWDNSDMN?",
    "NWIF?",
    "NWWLCNFS?",
    "NWESSID2?",
    "NWESSID3?",
    "NWWLSEC?",
    "NWWEP?",
    "NWWEP1?",
    "NWWEP2?",
    "NWWEP3?",
    "NWWEP4?",
    "NWPRIMIF?",
    "NWSECUSER?",
    "NWSECPASSWD?",
    "NWSECPSK?",
]

class EscVp21CommandError(Exception):
    """Raised when there is a command error during ESC/VP21 communication."""

class EscVp21Communication:
    """Helper class for ESC/VP21 communication.

    Provides generic `get` command and `set` command methods next to the option to send raw commands.
    Raises EscVp21CommandError if the projector responds with an ERR status for a command.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer

    async def raw_command(self, command: str) -> str:
        """Send a raw command and return the response string. Raises local exceptions on connection errors."""
        command += "\r"
        try:
            payload = command.encode("ascii")
            logging.debug("Send: %s", payload)
            self._writer.write(payload)
            await self._writer.drain()

            raw_response = await self._reader.readuntil(b":")
            logging.debug("Recv: %s", raw_response.strip())

            response = raw_response[:-1].decode("ascii")  # remove trailing colon
            return response.rstrip("\r")
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as e:
            raise Exception("Connection lost or protocol error during read") from e
        except (
            ConnectionResetError,
            BrokenPipeError,
            ConnectionAbortedError,
            OSError,
        ) as e:
            raise Exception("Connection error during communication") from e

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
            logging.debug("Closing ESC/VP21 connection")
            self._writer.close()


def _add_projector_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("host", help="IP address of the projector")
    parser.add_argument(
        "--port",
        type=int,
        default=3629,
        help="Override the ESC/VP.net TCP port",
    )


async def _connect_with_password_prompt(args: argparse.Namespace) -> EscVp21Communication:
    password = None

    while True:
        try:
            escvpnet = EscVpNet(host=args.host, port=args.port, password=password)
            reader, writer = await escvpnet.connect()
            return EscVp21Communication(reader=reader, writer=writer)
        except EscVpNetUnauthorizedStatus:
            password = getpass.getpass("Password required: ")
        except EscVpNetForbiddenStatus:
            password = getpass.getpass("Wrong password, try again: ")


async def _command_discover(_args: argparse.Namespace) -> None:
    responses = await EscVpNet.discover()
    print(responses)


async def _command_read_basic(args: argparse.Namespace) -> None:
    escvp21 = await _connect_with_password_prompt(args)

    try:
        for command in ("PWR", "SNO", "LAMP"):
            response = await escvp21.get(command)
            print(f"{command}: {response}")
    finally:
        escvp21.close()


async def _command_confirm_password(args: argparse.Namespace) -> None:
    password = getpass.getpass("Password: ")
    escvpnet = EscVpNet(host=args.host, port=args.port, password=password)
    ok = await escvpnet.confirm_password()
    print(f"Password correct: {ok}")


async def _command_change_password(args: argparse.Namespace) -> None:
    old_password = getpass.getpass("Old password: ")
    new_password = getpass.getpass("New password: ")
    escvpnet = EscVpNet(host=args.host, port=args.port, password=old_password)
    await escvpnet.change_password(new_password=new_password)
    print("Password changed")


async def _command_send_commands(args: argparse.Namespace) -> None:
    escvp21 = await _connect_with_password_prompt(args)

    try:
        commands = " ".join(args.commands).split(":")
        for command in commands:
            try:
                if command.endswith("?"):
                    response = await escvp21.get(command.rstrip("?"))
                    print(f"{command} -> {response}")
                else:
                    parts = command.split(" ", 1)
                    await escvp21.set(parts[0], parts[1])
                    print(f"{command}, Acked")
            except EscVp21CommandError as e:
                print(f"{command} -> Error: {e}")
    finally:
        escvp21.close()


async def _command_read_escvpnet_extensions(args: argparse.Namespace) -> None:
    escvp21 = await _connect_with_password_prompt(args)

    try:
        for command in ESCVPNET_COMMAND_EXTENSIONS:
            try:
                response = await escvp21.get(command.rstrip("?"))
                print(f"{command} -> {response}")
            except EscVp21CommandError as e:
                print(f"{command} -> Error: {e}")
    finally:
        escvp21.close()


async def main(args):
    if args.command == "discover":
        responses = await EscVpNet.discover()
        print(responses)
        return

    if args.command == "read_basic":
        await _command_read_basic(args)
        return

    if args.command == "confirm_password":
        await _command_confirm_password(args)
        return

    if args.command == "change_password":
        await _command_change_password(args)
        return

    if args.command == "send_commands":
        await _command_send_commands(args)
        return

    if args.command == "read_escvpnet_extensions":
        await _command_read_escvpnet_extensions(args)
        return

    raise ValueError(f"Unknown command: {args.command}")


def parse_args():
    parser = argparse.ArgumentParser(description="Test ESC/VP.net connection")
    parser.add_argument(
        "--loglevel",
        help="Set the logging level. Default is INFO.",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser(
        "discover",
        help="Discover projectors in the network using the HELLO message",
    )
    discover_parser.set_defaults(handler=_command_discover)

    read_basic_parser = subparsers.add_parser(
        "read_basic",
        help="Read PWR, SNO and LAMP values",
    )
    _add_projector_arguments(read_basic_parser)

    confirm_password_parser = subparsers.add_parser(
        "confirm_password",
        help="Check if a password can be used to connect to the projector",
    )
    _add_projector_arguments(confirm_password_parser)

    change_password_parser = subparsers.add_parser(
        "change_password",
        help="Change the password of the projector",
    )
    _add_projector_arguments(change_password_parser)

    send_commands_parser = subparsers.add_parser(
        "send_commands",
        help="Send one or more ESC/VP21 commands to the projector. Separate multiple commands with : e.g. 'PWR ON:SOURCE A0:LAMP?'.",
    )
    _add_projector_arguments(send_commands_parser)
    send_commands_parser.add_argument(
        "commands",
        nargs="+",
        help="Commands to send. Use 'PWR?' for a read or quote a write like 'PWR ON'.",
    )

    read_escvpnet_extensions_parser = subparsers.add_parser(
        "read_escvpnet_extensions",
        help="Read all known ESC/VP.net extension commands from the projector.",
    )
    _add_projector_arguments(read_escvpnet_extensions_parser)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(level=args.loglevel)
    asyncio.run(main(args))
