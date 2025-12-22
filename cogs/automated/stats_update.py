import time
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from main import TitaniumBot


class StatsUpdateCog(commands.Cog):
    """Automatic task to update bot stats for server count, member count and user install count"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.showing_info: bool = True

        # Start tasks
        self.info_update.start()
        self.status_update.start()
        self.measure_api_latency.start()

    def cog_unload(self) -> None:
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
        self.bot.guild_installs = app_data.approximate_guild_count
        self.bot.guild_member_count = guild_members

    # Status update task
    @tasks.loop(minutes=10)
    async def status_update(self) -> None:
        await self.bot.wait_until_ready()

        if self.showing_info:
            # Show website status
            await self.bot.change_presence(
                activity=discord.Activity(
                    status=discord.Status.online,
                    type=discord.ActivityType.custom,
                    name="titanium",
                    state="🌐 titaniumbot.me",
                )
            )
        else:
            # Show info status
            await self.bot.change_presence(
                activity=discord.Activity(
                    status=discord.Status.online,
                    type=discord.ActivityType.custom,
                    name="titanium",
                    state=f"{self.bot.user_installs} users, {self.bot.guild_installs} servers with {self.bot.guild_member_count:,} members",
                )
            )

        self.showing_info = not self.showing_info

    # Measure API latency task
    @tasks.loop(minutes=1)
    async def measure_api_latency(self) -> None:
        async with aiohttp.ClientSession() as session:
            session.headers.update(
                {
                    "Content-Type": "Application/json",
                    "Authorization": "Bot " + self.bot.http.token,  # type: ignore
                }
            )

            start = time.perf_counter()
            async with session.get("https://discord.com/api/v10/users/@me") as request:
                request.raise_for_status()

                delta = time.perf_counter() - start
                self.bot.api_latency = delta


async def setup(bot: TitaniumBot):
    await bot.add_cog(StatsUpdateCog(bot))
