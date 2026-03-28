from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from sqlalchemy import select

from lib.sql.sql import GuildSettings, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class DataRetention(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.left_server_check.start()

    def cog_unload(self) -> None:
        self.left_server_check.cancel()

    # Listen for Titanium rejoining servers
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        async with get_session() as session:
            settings = await session.get(GuildSettings, guild.id)

            if settings and settings.leave_date:
                settings.leave_date = None

    # Listen for Titanium leaving servers
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        config = await self.bot.fetch_guild_config(guild.id, create_config=False)

        if not config:
            return

        if config.delete_after_3_days:
            async with get_session() as session:
                settings = await session.get(GuildSettings, guild.id)

                if not settings:
                    return

                settings.leave_date = datetime.now(timezone.utc)
        else:
            await self.bot.delete_guild_config(guild_id=guild.id)

    # Check for old servers
    @tasks.loop(hours=1)
    async def left_server_check(self) -> None:
        await self.bot.wait_until_ready()

        async with get_session() as session:
            stmt = select(GuildSettings).where(
                GuildSettings.leave_date <= datetime.now(timezone.utc) - timedelta(days=3)
            )
            old_servers = (await session.execute(stmt)).scalars().all()

            for server in old_servers:
                if self.bot.get_guild(server.guild_id):
                    server.leave_date = None
                    continue

                await self.bot.delete_guild_config(guild_id=server.guild_id)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(DataRetention(bot))
