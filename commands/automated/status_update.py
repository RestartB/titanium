from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from main import TitaniumBot


class StatusUpdate(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

        self.user_installs = 0
        self.guild_installs = 0
        self.server_members = 0

        # Set to true to start with website status
        self.showing_info = True

        # Start tasks
        self.info_update.start()
        self.status_update.start()

    def cog_unload(self) -> None:
        # Stop tasks on unload
        self.info_update.cancel()
        self.status_update.cancel()

    # Info update task
    @tasks.loop(hours=1)
    async def info_update(self) -> None:
        await self.bot.wait_until_ready()

        # Count members
        server_members: int = sum(
            guild.approximate_member_count for guild in self.bot.guilds
        )

        # Get app data
        app_data: discord.AppInfo = await self.bot.application_info()

        # Set variables
        self.user_installs = app_data.approximate_user_install_count
        self.guild_installs = app_data.approximate_guild_count
        self.server_members = server_members

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
                    name="custom",
                    state="🌐 titaniumbot.me - use /",
                )
            )
        else:
            # Show info status
            await self.bot.change_presence(
                activity=discord.Activity(
                    status=discord.Status.online,
                    type=discord.ActivityType.custom,
                    name="custom",
                    state=f"{self.user_installs} users, {self.guild_installs} servers with {self.server_members} members - use /",
                )
            )

        self.showing_info = not self.showing_info


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(StatusUpdate(bot))
