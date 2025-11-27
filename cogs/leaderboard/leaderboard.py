import logging
import random
from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from lib.enums.leaderboard import LeaderboardCalcType
from lib.sql.sql import LeaderboardUserStats, get_session
from lib.views.pagination import PaginationView

if TYPE_CHECKING:
    from main import TitaniumBot


class LeaderboardCog(commands.Cog):
    """Monitors messages and processes leaderboard"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("leaderboard")
        self.member_last_trigger: dict[int, dict[int, datetime]] = {}

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
        if not guild_settings:
            await self.bot.refresh_guild_config_cache(message.guild.id)
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
        cooldown = lb_settings.cooldown
        length = len(message.content)

        if cooldown > 0:
            created_at = message.created_at
            user_cooldowns = self.member_last_trigger.setdefault(message.guild.id, {})
            last_trigger = user_cooldowns.get(message.author.id)

            if last_trigger and (created_at - last_trigger).total_seconds() < cooldown:
                return

            user_cooldowns[message.author.id] = created_at

        to_assign = 0

        if mode == LeaderboardCalcType.FIXED and xp:
            to_assign = xp
        elif mode == LeaderboardCalcType.RANDOM and min_xp and max_xp:
            to_assign = random.randint(min_xp, max_xp)
        elif mode == LeaderboardCalcType.LENGTH and xp and max_xp:
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
        if not guild_settings:
            await self.bot.refresh_guild_config_cache(member.guild.id)
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

    # Leaderboard command
    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top"])
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=False)
    async def leaderboard_command(self, ctx: commands.Context["TitaniumBot"]):
        """Gets the leaderboard for the server."""
        if not ctx.guild:
            return

        await ctx.defer()

        guild_settings = self.bot.guild_configs.get(ctx.guild.id)
        if not guild_settings:
            await self.bot.refresh_guild_config_cache(ctx.guild.id)
            guild_settings = self.bot.guild_configs.get(ctx.guild.id)

        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is not enabled in this server.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == ctx.guild.id)
                .order_by(LeaderboardUserStats.xp.desc())
                .limit(1000)
            )
            result = await session.execute(stmt)
            top_users = result.scalars().all()

            if not top_users:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description="No users have recorded XP or levels yet.",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed)
                return

            embed = discord.Embed(
                title="Leaderboard",
                color=discord.Color.random(),
            )

            pages = []
            page_size = 20
            for i, user_stats in enumerate(top_users, start=1):
                member = ctx.guild.get_member(user_stats.user_id)
                if not member:
                    continue

                if embed.description:
                    embed.description += (
                        f"\n{i}. {member.mention} - {user_stats.xp}XP, Level {user_stats.level}"
                    )
                else:
                    embed.description = (
                        f"{i}. {member.mention} - {user_stats.xp}XP, Level {user_stats.level}"
                    )

                if i % page_size == 0:
                    pages.append(embed)
                    embed = discord.Embed(
                        title="Leaderboard",
                        color=discord.Color.random(),
                    )

            if embed.description:
                pages.append(embed)

            view = PaginationView(embeds=pages, timeout=240)

            if len(pages) > 1:
                await ctx.send(embed=pages[0], view=view)
            else:
                await ctx.send(embed=pages[0])

    # Level command
    @commands.hybrid_command(name="level", aliases=["lvl"])
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=False)
    async def level_command(
        self, ctx: commands.Context["TitaniumBot"], member: discord.Member | None = None
    ):
        """Check your level and XP or another member's level and XP."""
        if not ctx.guild:
            return

        await ctx.defer()

        user = member or ctx.author

        guild_settings = self.bot.guild_configs.get(ctx.guild.id)
        if not guild_settings:
            await self.bot.refresh_guild_config_cache(ctx.guild.id)
            guild_settings = self.bot.guild_configs.get(ctx.guild.id)

        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is not enabled in this server.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(
                    LeaderboardUserStats.guild_id == ctx.guild.id,
                    LeaderboardUserStats.user_id == user.id,
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            user_stats = result.scalar_one_or_none()

            if not user_stats:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description=f"**{user.display_name}** has no recorded XP or level.",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed)
                return

            embed = discord.Embed(
                title="Level Info",
                color=discord.Color.blue(),
            )
            embed.add_field(name="Level", value=str(user_stats.level), inline=True)
            embed.add_field(name="XP", value=str(user_stats.xp), inline=True)

            embed.set_author(
                name=f"@{user.display_name}",
                icon_url=user.display_avatar.url,
            )
            embed.set_footer(
                text=f"@{ctx.author.display_name}",
                icon_url=ctx.author.display_avatar.url,
            )
            embed.set_thumbnail(
                url=user.display_avatar.url,
            )

            await ctx.send(embed=embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
