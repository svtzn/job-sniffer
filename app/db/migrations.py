"""Применение миграций Alembic из кода (при старте бота)."""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.attributes["configure_logger"] = False
    return config


def upgrade_to_head() -> None:
    command.upgrade(_alembic_config(), "head")


async def upgrade_to_head_async() -> None:
    # env.py сам запускает asyncio.run — поэтому в отдельном потоке без event loop
    await asyncio.to_thread(upgrade_to_head)
