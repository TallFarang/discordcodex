from __future__ import annotations

import argparse
import asyncio
import logging

from .bot import run_bot
from .config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run DiscordCodex.")
    parser.add_argument("--config", help="Path to projects JSON config")
    args = parser.parse_args(argv)

    try:
        settings = load_settings(config_path=args.config)
    except ValueError as exc:
        parser.error(str(exc))

    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_bot(settings))
    return 0
