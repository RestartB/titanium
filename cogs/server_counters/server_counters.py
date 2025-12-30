from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from sqlalchemy import select

from lib.helpers.log_error import log_error
from lib.helpers.resolve_counter import resolve_counter
from lib.sql.sql import ServerCounterChannel, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ServerCountersCog(commands.Cog):
    """Automatic task to update server counter channel names"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

        # Start tasks
        self.channel_update.start()

    def cog_unload(self) -> None:
        # Stop tasks on unload
        self.channel_update.cancel()

    # Channel update task
    @tasks.loop(minutes=15)
    async def channel_update(self) -> None:
        await self.bot.wait_until_ready()

        async with get_session() as session:
            results = await session.execute(select(ServerCounterChannel))
            channels = results.scalars().all()

        for count_channel in channels:
            guild = self.bot.get_guild(count_channel.guild_id)
            if not guild:
                continue

            guild_settings = await self.bot.fetch_guild_config(guild.id)
            if not guild_settings or not guild_settings.server_counters_enabled:
                continue

            discord_channel = guild.get_channel(count_channel.id)
            if not discord_channel or not isinstance(discord_channel, discord.VoiceChannel):
                continue

            new_name = await resolve_counter(guild, count_channel.count_type, count_channel.name)

            if discord_channel.name == new_name:
                continue

            try:
                await discord_channel.edit(name=new_name, reason="Automated server counter update")
            except discord.Forbidden as e:
                await log_error(
                    bot=self.bot,
                    module="Server Counters",
                    guild_id=guild.id,
                    error=f"Titanium was not allowed to update counter channel {discord_channel.name} ({discord_channel.id})",
                    details=e.text,
                )
            except discord.HTTPException as e:
                await log_error(
                    bot=self.bot,
                    module="Server Counters",
                    guild_id=guild.id,
                    error=f"Unknown Discord error while updating counter channel {discord_channel.name} ({discord_channel.id})",
                    details=e.text,
                )


async def setup(bot: TitaniumBot):
    await bot.add_cog(ServerCountersCog(bot))
