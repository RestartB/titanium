import logging
import random
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from lib.enums.leaderboard import CalcType
from lib.sql.sql import LeaderboardUserStats, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class LeaderboardCog(commands.Cog):
    """Monitors messages and processes leaderboard"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("leaderboard")

        self.take_daily_snapshots.start()

    def cog_unload(self) -> None:
        # Stop tasks on unload
        self.take_daily_snapshots.cancel()

    # Snapshot task
    @tasks.loop(hours=24)
    async def take_daily_snapshots(self) -> None:
        async with get_session() as session:
            stmt = select(LeaderboardUserStats)
            result = await session.execute(stmt)
            all_stats = result.scalars().all()

            for user_stat in all_stats:
                snapshots = user_stat.daily_snapshots or []
                snapshots.append(user_stat.level)

                user_stat.daily_snapshots = snapshots[-30:]

            await session.commit()

    # Message event
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        guild_settings = self.bot.guild_configs.get(message.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            return

        lb_settings = guild_settings.leaderboard_settings

        mode = lb_settings.mode
        xp = lb_settings.base_xp
        min_xp = lb_settings.min_xp
        max_xp = lb_settings.max_xp
        length = len(message.content)

        to_assign = 0

        if mode == CalcType.FIXED:
            to_assign = xp
        elif mode == CalcType.RANDOM:
            to_assign = random.randint(min_xp, max_xp)
        elif mode == CalcType.LENGTH:
            to_assign = min(int(length / 100) * xp, max_xp)

        async with get_session() as session:
            levels = guild_settings.leaderboard_settings.levels
            levels.sort(key=lambda level: level.xp)

            stmt = insert(LeaderboardUserStats).values(
                guild_id=message.guild.id,
                user_id=message.author.id,
                xp=to_assign,
                level=0,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["guild_id", "user_id"],
                set_={"xp": LeaderboardUserStats.xp + to_assign},
            ).returning(LeaderboardUserStats)

            result = await session.execute(stmt)
            user_stats = result.scalar_one()

            old_level = user_stats.level
            new_level = 0
            for level in levels:
                if user_stats.xp >= level.xp:
                    new_level += 1
                else:
                    break

            if new_level != old_level:
                user_stats.level = new_level

        if lb_settings.levelup_notifications and new_level > old_level:
            channel = message.channel

            if lb_settings.notification_channel:
                channel = message.guild.get_channel(lb_settings.notification_channel)

            if not channel:
                return

            if not isinstance(channel, discord.abc.Messageable):
                return

            await channel.send(
                content=message.author.mention,
                embed=discord.Embed(
                    description=f"🎉 {message.author.mention} has leveled up to **level {user_stats.level}!**",
                    color=discord.Color.green(),
                ),
            )

    # Member leave event
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guild_settings = self.bot.guild_configs.get(member.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_settings.delete_leavers
        ):
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(
                    LeaderboardUserStats.guild_id == member.guild.id,
                    LeaderboardUserStats.user_id == member.id,
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            user_stats = result.scalar_one_or_none()

            if user_stats:
                await session.delete(user_stats)
                await session.commit()


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
