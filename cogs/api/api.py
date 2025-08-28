import asyncio
import logging
import os
from typing import TYPE_CHECKING

from aiohttp import web
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


class APICog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
        self.app = None
        self.runner = None
        self.site = None

        # Get host and port from env with defaults
        self.host = os.getenv("BOT_API_HOST", "127.0.0.1")
        self.port = int(os.getenv("BOT_API_PORT", 5000))

        logging.info(f"[API] Starting API server on {self.host}:{self.port}")
        self.server_task = asyncio.create_task(self.start_server())

    async def start_server(self):
        try:
            self.app = web.Application()
            self.register_routes()

            self.runner = web.AppRunner(self.app, access_log=None)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()

            logging.info(
                f"[API] API server started successfully on {self.host}:{self.port}"
            )
        except Exception as e:
            logging.error(f"[API] Failed to start API server: {e}")
            exit(1)

    def register_routes(self):
        if self.app is None:
            return

        self.app.router.add_get("/", self.index)
        self.app.router.add_get("/info", self.info)
        self.app.router.add_get("/ping", self.ping)
        self.app.router.add_get("/status", self.status)
        self.app.router.add_get("/stats", self.stats)

    async def index(self, request: web.Request) -> web.Response:
        return web.json_response({"version": "Titanium API v2"})

    async def ping(self, request: web.Request) -> web.Response:
        return web.json_response({"ping": "pong"})

    async def info(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "username": self.bot.user.name if self.bot.user else None,
                "discriminator": self.bot.user.discriminator if self.bot.user else None,
                "pfp": self.bot.user.display_avatar.url if self.bot.user else None,
            }
        )

    async def status(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "ready": self.bot.is_ready(),
                "connected": getattr(self.bot, "connected", False),
                "latency": round(self.bot.latency * 1000, 2),
                "initial_connect": self.bot.connect_time.timestamp()
                if self.bot.connect_time
                else None,
                "last_disconnect": self.bot.last_disconnect.timestamp()
                if self.bot.last_disconnect
                else None,
                "last_resume": self.bot.last_resume.timestamp()
                if self.bot.last_resume
                else None,
            }
        )

    async def stats(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "server_count": self.bot.guild_installs,
                "server_member_count": self.bot.guild_member_count,
                "user_count": self.bot.user_installs,
            }
        )

    async def cog_unload(self):
        if self.server_task:
            self.server_task.cancel()

        if self.site:
            await self.site.stop()

        if self.runner:
            await self.runner.cleanup()


async def setup(bot: "TitaniumBot"):
    await bot.add_cog(APICog(bot))
