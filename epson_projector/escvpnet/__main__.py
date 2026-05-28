from __future__ import annotations

import argparse
import asyncio
import logging

from .escvpnet import EscVpNet


async def main(args):
    escvpnet = EscVpNet(host=args.host)

    if args.discover:
        responses = await EscVpNet.discover()
        print(responses)
        return

    escvp21 = await escvpnet.connect("new_password")

    if escvp21:
        try:
            response = await escvp21.get("PWR")
            print(f"PWR: {response}")
            response = await escvp21.get("SNO")
            print(f"SNO: {response}")
            response = await escvp21.get("LAMP")
            print(f"LAMP: {response}")
        finally:
            escvp21.close()
    
    can_connect = await escvpnet.password_valid("wrong")
    print(f"Can connect: {can_connect}")

    # try:
    #     await escvpnet.change_password("old_password", "new_password")
    # except Exception as e:
    #     print(f"Error changing password: {e}")
    # else:
    #     print("Password changed")


def parse_args():
    parser = argparse.ArgumentParser(description="Test ESC/VP.net connection")
    parser.add_argument("host", help="IP address of the projector")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Discover projectors in the network using HELLO message and exit",
    )
    parser.add_argument(
        "--loglevel",
        help="Set the logging level. Default is INFO.",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    return parser.parse_args()


def run():
    args = parse_args()
    logging.basicConfig(level=args.loglevel)
    asyncio.run(main(args))


if __name__ == "__main__":
    run()
