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
    asyncio.run(Server(config).start())
    return 0


if __name__ == "__main__":
    sys.exit(main())
