import logging
import time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from discord.http import Route

if TYPE_CHECKING:
    from main import TitaniumBot


class StatsUpdateCog(commands.Cog):
    """Automatic task to update bot stats for server count, member count and user install count"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.current_status: int = -1

    async def cog_load(self) -> None:
        # Start tasks
        self.info_update.start()
        self.status_update.start()
        self.measure_api_latency.start()

    async def cog_unload(self) -> None:
        # Stop tasks on unload
        self.info_update.cancel()
        self.status_update.cancel()
        self.measure_api_latency.cancel()

    # Info update task
    @tasks.loop(minutes=10)
    async def info_update(self) -> None:
        await self.bot.wait_until_ready()

        # Count members
        guild_members: int = sum(guild.member_count or 0 for guild in self.bot.guilds)

        # Get app data
        app_data: discord.AppInfo = await self.bot.application_info()

        # Set variables
        self.bot.user_installs = (
            app_data.approximate_user_install_count
            if app_data.approximate_user_install_count
            else 0
        )
        self.bot.guild_installs = len(self.bot.guilds)
        self.bot.guild_member_count = guild_members

    # Status update task
    @tasks.loop(minutes=10)
    async def status_update(self) -> None:
        await self.bot.wait_until_ready()

        if self.current_status == -1 or self.current_status == 2:
            self.current_status = 0
            # Show website status
            await self.bot.change_presence(
                activity=discord.Activity(
                    status=discord.Status.online,
                    type=discord.ActivityType.custom,
                    name="titanium",
                    state="🌐 titanium.fyi",
                )
            )
        elif self.current_status == 0:
            self.current_status = 1
            # Show dashboard status
            await self.bot.change_presence(
                activity=discord.Activity(
                    status=discord.Status.online,
                    type=discord.ActivityType.custom,
                    name="titanium",
                    state="🔧 dash.titanium.fyi",
                )
            )
        elif self.current_status == 1:
            self.current_status = 2
            # Show stats status
            await self.bot.change_presence(
                activity=discord.Activity(
                    status=discord.Status.online,
                    type=discord.ActivityType.custom,
                    name="titanium",
                    state=f"{self.bot.user_installs} users, {self.bot.guild_installs} servers with {self.bot.guild_member_count:,} members",
                )
            )

    # Measure API latency task
    @tasks.loop(minutes=1)
    async def measure_api_latency(self) -> None:
        try:
            start = time.perf_counter()
            r = Route("GET", "/users/@me")

            await self.bot.http.request(r)
            delta = time.perf_counter() - start

            self.bot.api_latency = delta
        except Exception as e:
            self.bot.api_latency = 0
            logging.error("Failed to measure API latency", exc_info=e)


async def setup(bot: TitaniumBot):
    await bot.add_cog(StatsUpdateCog(bot))
