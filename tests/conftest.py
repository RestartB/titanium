"""
Shared pytest fixtures for the Titanium test suite.

A minimal bot is configured with dpytest so that every test module gets a
realistic Discord environment (guild, channels, members) without needing a
live connection or a real Discord token.
"""

from __future__ import annotations

import glob
import os
from typing import AsyncGenerator

import discord
import discord.ext.commands as commands
import discord.ext.test as dpytest
import pytest_asyncio
from discord.client import _LoopSentinel


class TestBot(commands.Bot):
    """Minimal bot used in tests.  Mirrors the emoji attributes that TitaniumBot exposes
    so that embed-building helpers don't crash when they reference them."""

    error_emoji = "❌"
    success_emoji = "✅"
    warn_emoji = "⚠️"

    async def setup_hook(self) -> None:
        pass

    async def fetch_guild_config(self, guild_id: int) -> None:  # type: ignore[override]
        """No-op override – individual tests patch this as needed."""
        return None


@pytest_asyncio.fixture
async def bot() -> AsyncGenerator[TestBot, None]:
    """Create a fresh TestBot configured with dpytest for each test."""
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    b = TestBot(command_prefix="!", intents=intents)

    # Initialise the async internals if the event loop hasn't been attached yet
    if isinstance(b.loop, _LoopSentinel):
        await b._async_setup_hook()

    dpytest.configure(b, members=["Alice", "Bob"])
    yield b


@pytest_asyncio.fixture(autouse=True)
async def cleanup() -> AsyncGenerator[None, None]:
    """Drain the dpytest message queue after every test."""
    yield
    await dpytest.empty_queue()


def pytest_sessionfinish() -> None:
    """Remove any attachment temp files that dpytest may have created."""
    for path in glob.glob("./dpytest_*.dat"):
        try:
            os.remove(path)
        except Exception:
            print(f"Could not remove temp file: {path}")
