import logging
import math
import random
from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from lib.enums.leaderboard import LeaderboardCalcType
from lib.helpers.log_error import log_error
from lib.sql.sql import LeaderboardUserStats, get_session
from lib.views.pagination import PaginationView

if TYPE_CHECKING:
    from main import TitaniumBot

POSTGRES_MAX_INT = 9223372036854775807


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

        if message.author.id in self.bot.opt_out:
            return

        guild_settings = await self.bot.fetch_guild_config(message.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            self.logger.debug(f"Leaderboard disabled for guild {message.guild.id}")
            return

        lb_settings = guild_settings.leaderboard_settings

        mode = lb_settings.mode
        xp = lb_settings.base_xp
        min_xp = lb_settings.min_xp
        max_xp = lb_settings.max_xp
        xp_mult = lb_settings.xp_mult
        cooldown = lb_settings.cooldown

        length = len(message.content)
        word_count = len(message.content.split())
        attachment_count = len(message.attachments)

        async with get_session() as session:
            stmt = insert(LeaderboardUserStats).values(
                guild_id=message.guild.id,
                user_id=message.author.id,
                xp=0,
                message_count=1,
                word_count=word_count,
                attachment_count=attachment_count,
                level=0,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["guild_id", "user_id"],
                set_={
                    "message_count": LeaderboardUserStats.message_count + 1,
                    "word_count": LeaderboardUserStats.word_count + len(message.content.split()),
                    "attachment_count": LeaderboardUserStats.attachment_count
                    + len(message.attachments),
                },
            ).returning(LeaderboardUserStats)

            result = await session.execute(stmt)
            user_stats = result.scalar_one()

            if cooldown > 0:
                created_at = message.created_at
                user_cooldowns = self.member_last_trigger.setdefault(message.guild.id, {})
                last_trigger = user_cooldowns.get(message.author.id)

                if last_trigger and (created_at - last_trigger).total_seconds() < cooldown:
                    self.logger.debug(
                        f"User {message.author.id} in guild {message.guild.id} is on cooldown"
                    )
                    return

                user_cooldowns[message.author.id] = created_at

            to_assign = 0

            if mode == LeaderboardCalcType.FIXED and xp:
                to_assign = xp
            elif mode == LeaderboardCalcType.RANDOM and min_xp and max_xp:
                to_assign = random.randint(min_xp, max_xp)
            elif mode == LeaderboardCalcType.LENGTH and xp and xp_mult and max_xp and min_xp:
                to_assign = int(max(min(10 + (xp_mult * math.sqrt(length)), max_xp), min_xp))

            levels = guild_settings.leaderboard_settings.levels
            levels.sort(key=lambda level: level.xp)

            user_stats.xp = min(user_stats.xp + to_assign, POSTGRES_MAX_INT)

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
                self.logger.debug(f"Notification channel not found for guild {message.guild.id}")
                return

            if not isinstance(channel, discord.abc.Messageable):
                self.logger.debug(
                    f"Notification channel not messageable in guild {message.guild.id}"
                )
                return

            try:
                await channel.send(
                    content=message.author.mention,
                    embed=discord.Embed(
                        description=f"🎉 {message.author.mention} has leveled up to **level {user_stats.level}!**",
                        colour=discord.Colour.green(),
                    ),
                )
            except discord.Forbidden as e:
                await log_error(
                    bot=self.bot,
                    module="Leaderboard",
                    guild_id=message.guild.id,
                    error=f"Titanium was not allowed to send leaderboard notification in #{message.channel.name if not isinstance(message.channel, (discord.PartialMessageable, discord.DMChannel)) else 'Unknown'} ({message.channel.id})",
                    details=str(e.text),
                    exc=e,
                )
            except discord.HTTPException as e:
                await log_error(
                    bot=self.bot,
                    module="Leaderboard",
                    guild_id=message.guild.id,
                    error=f"Unknown Discord error while sending leaderboard notification in #{message.channel.name if not isinstance(message.channel, (discord.PartialMessageable, discord.DMChannel)) else 'Unknown'} ({message.channel.id})",
                    details=str(e.text),
                    exc=e,
                )

    # Member leave event
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guild_settings = await self.bot.fetch_guild_config(member.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_settings.delete_leavers
            or member.id in self.bot.opt_out
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

        if ctx.author.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.send(embed=embed)
            return

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is not enabled in this server.",
                colour=discord.Colour.red(),
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
                    colour=discord.Colour.red(),
                )
                await ctx.send(embed=embed)
                return

            embed = discord.Embed(
                title="Leaderboard",
                colour=discord.Colour.random(),
            )
            embed.set_author(
                name=ctx.guild.name,
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
            )

            pages: list[discord.Embed] = []
            page_size = 15

            for i, user_stats in enumerate(top_users, start=1):
                member = ctx.guild.get_member(user_stats.user_id)

                if embed.description:
                    embed.description += f"\n{i}. {member.mention if member else f'`{user_stats.user_id}`'} - {user_stats.xp}XP{f', Level {user_stats.level}' if len(guild_settings.leaderboard_settings.levels) > 1 else ''}"
                else:
                    embed.description = f"{i}. {member.mention if member else f'`{user_stats.user_id}`'} - {user_stats.xp}XP{f', Level {user_stats.level}' if len(guild_settings.leaderboard_settings.levels) > 1 else ''}"

                if i % page_size == 0:
                    pages.append(embed)

                    embed = discord.Embed(
                        title="Leaderboard",
                        colour=discord.Colour.random(),
                    )
                    embed.set_author(
                        name=ctx.guild.name,
                        icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
                    )

            if embed.description:
                pages.append(embed)

            pages[0].set_footer(
                text=f"Controlling: @{ctx.author.name}"
                if len(pages) > 1
                else f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

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

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.send(embed=embed)
            return

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is not enabled in this server.",
                colour=discord.Colour.red(),
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
                    colour=discord.Colour.red(),
                )
                await ctx.send(embed=embed)
                return

            embed = discord.Embed(
                title="Level Info",
                colour=discord.Colour.blue(),
            )
            embed.add_field(name="Level", value=str(user_stats.level), inline=True)
            embed.add_field(name="XP", value=str(user_stats.xp), inline=True)

            embed.set_author(
                name=f"@{user.name}",
                icon_url=user.display_avatar.url,
            )
            embed.set_footer(
                text=f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )
            embed.set_thumbnail(
                url=user.display_avatar.url,
            )

            await ctx.send(embed=embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
