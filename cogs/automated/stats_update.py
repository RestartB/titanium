from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from main import TitaniumBot


class StatsUpdateCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

        # Start tasks
        self.info_update.start()

    def cog_unload(self) -> None:
        # Stop tasks on unload
        self.info_update.cancel()

    # Info update task
    @tasks.loop(hours=1)
    async def info_update(self) -> None:
        await self.bot.wait_until_ready()

        # Count members
        server_members: int = sum(guild.member_count or 0 for guild in self.bot.guilds)

        # Get app data
        app_data: discord.AppInfo = await self.bot.application_info()

        # Set variables
        self.bot.user_installs = (
            app_data.approximate_user_install_count
            if app_data.approximate_user_install_count
            else 0
        )
        self.bot.guild_installs = app_data.approximate_guild_count
        self.bot.guild_member_count = server_members


async def setup(bot: "TitaniumBot"):
    await bot.add_cog(StatsUpdateCog(bot))
