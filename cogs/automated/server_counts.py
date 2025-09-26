from typing import TYPE_CHECKING

import discord
import humanize
from discord.ext import commands, tasks
from sqlalchemy import select

from lib.sql import ServerCounterChannel, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ServerCounterCog(commands.Cog):
    """Automatic task to update server counter channel names"""

    def __init__(self, bot: "TitaniumBot") -> None:
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

            config = self.bot.guild_configs.get(guild.id)
            if not config or not config.server_counts_enabled:
                continue

            discord_channel = guild.get_channel(count_channel.channel_id)
            if not discord_channel or not isinstance(
                discord_channel, discord.VoiceChannel
            ):
                continue

            if count_channel.count_type == "total_members":
                updated_value = guild.member_count
            elif count_channel.count_type == "users":
                updated_value = 0

                for member in guild.members:
                    if not member.bot:
                        updated_value += 1
            elif count_channel.count_type == "bots":
                updated_value = 0

                for member in guild.members:
                    if member.bot:
                        updated_value += 1
            elif count_channel.count_type == "online_members":
                updated_value = 0

                for member in guild.members:
                    if member.status != discord.Status.offline:
                        updated_value += 1
            elif count_channel.count_type == "members_status_online":
                updated_value = 0

                for member in guild.members:
                    if member.status == discord.Status.online:
                        updated_value += 1
            elif count_channel.count_type == "members_status_idle":
                updated_value = 0

                for member in guild.members:
                    if member.status == discord.Status.idle:
                        updated_value += 1
            elif count_channel.count_type == "members_status_dnd":
                updated_value = 0

                for member in guild.members:
                    if member.status == discord.Status.dnd:
                        updated_value += 1
            elif count_channel.count_type == "members_activity":
                updated_value = 0

                for member in guild.members:
                    if member.activity is not None:
                        for activity in member.activities:
                            if activity.type != discord.ActivityType.custom:
                                updated_value += 1
                                break
            elif count_channel.count_type == "members_custom_status":
                updated_value = 0

                for member in guild.members:
                    if member.activity is not None:
                        for activity in member.activities:
                            if activity.type == discord.ActivityType.custom:
                                updated_value += 1
                                break
            elif count_channel.count_type == "offline_members":
                updated_value = 0

                for member in guild.members:
                    if member.status == discord.Status.offline:
                        updated_value += 1
            elif count_channel.count_type == "channels":
                updated_value = (
                    len(guild.text_channels)
                    + len(guild.voice_channels)
                    + len(guild.stage_channels)
                    + len(guild.forums)
                )

            if not updated_value:
                continue

            new_name = count_channel.name.replace(
                "{count}", humanize.intcomma(updated_value)
            )

            try:
                await discord_channel.edit(
                    name=new_name, reason="Automated server counter update"
                )
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                continue


async def setup(bot: "TitaniumBot"):
    await bot.add_cog(ServerCounterCog(bot))
