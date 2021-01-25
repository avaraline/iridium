import argparse
import asyncio
import sys

import toml

from .server import Server


def default_config():
    return {
        "irc": {
            "name": "Iridium",
            "bind": "0.0.0.0",
            "port": 6667,
            "password": "",
            "automap": True,
        },
        "discord": {
            "token": "",
            "guild_id": 0,
        },
        "channels": {
            "general": {
                "default": True,
                "log": True,
                "webhook": "IRC",
            },
        },
        "commands": {
            "weather": {
                "appid": "",
            },
            "issue": {
                "user": "",
                "token": "",
                "repo": "",
                "labels": [],
            },
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config", default="iridium.toml", help="The configuration file to load."
    )
    args = parser.parse_args()
    try:
        config = toml.load(args.config)
    except FileNotFoundError:
        print(f"Could not load configuration from {args.config}", file=sys.stderr, flush=True)
        return 1
    server = Server(config)
    loop = asyncio.get_event_loop()
    try:
        loop.create_task(server.start())
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(server.stop())
        loop.run_until_complete(loop.shutdown_asyncgens())
        # loop.run_until_complete(loop.shutdown_default_executor())
    finally:
        loop.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
