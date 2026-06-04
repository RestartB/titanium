import logging
import math
import random
import re
from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from lib.embeds.leaderboard import generate_lb_embeds
from lib.enums.leaderboard import LeaderboardCalcType
from lib.helpers.global_alias import add_global_aliases, global_alias, remove_global_aliases
from lib.helpers.hybrid import handle_group_command_not_found
from lib.helpers.log_error import log_error
from lib.sql.sql import LeaderboardUserStats, get_session
from lib.views.pagination import LeaderboardReloadPageView

if TYPE_CHECKING:
    from main import TitaniumBot

POSTGRES_MAX_INT = 9223372036854775807
POSTGRES_MIN_INT = -9223372036854775808


class LeaderboardCog(commands.Cog):
    """Monitors messages and processes leaderboard"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("leaderboard")
        self.member_last_trigger: dict[int, dict[int, datetime]] = {}

        self.take_daily_snapshots.start()
        add_global_aliases(self, bot)

    async def cog_unload(self) -> None:
        self.take_daily_snapshots.cancel()
        remove_global_aliases(self, self.bot)

    # Snapshot task
    @tasks.loop(hours=24)
    async def take_daily_snapshots(self) -> None:
        guild_ids = []
        for guild in self.bot.guilds:
            config = await self.bot.fetch_guild_config(guild.id, create_config=False)
            if not config or not config.leaderboard_enabled:
                continue
            guild_ids.append(guild.id)

        for guild_id in guild_ids:
            async with get_session() as session:
                stmt = (
                    select(LeaderboardUserStats)
                    .where(LeaderboardUserStats.guild_id == guild_id)
                    .order_by(LeaderboardUserStats.xp.desc())
                )
                result = await session.execute(stmt)
                all_stats = result.scalars().all()

                for i, user_stat in enumerate(all_stats, start=1):
                    snapshots = user_stat.daily_snapshots or []
                    snapshots.append(i)

                    user_stat.daily_snapshots = snapshots[-30:]

    # Message event
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot or message.is_system():
            return

        if message.author.id in self.bot.opt_out:
            self.logger.debug(f"User has opted out: {message.author.id}")
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

        if message.channel.id in lb_settings.ignored_channels:
            self.logger.debug(f"Message in ignored channel: {message.channel.id}")
            return

        if (
            any(role.id in lb_settings.ignored_roles for role in message.author.roles)
            if isinstance(message.author, discord.Member)
            else False
        ):
            self.logger.debug(f"Message from member with ignored role: {message.author.id}")
            return

        mode = lb_settings.mode
        xp = lb_settings.base_xp
        min_xp = lb_settings.min_xp
        max_xp = lb_settings.max_xp
        xp_mult = lb_settings.xp_mult
        cooldown = lb_settings.cooldown

        length = len(message.content)
        word_count = len(message.content.split())
        attachment_count = len(message.attachments)

        content_lower = message.content.lower()
        explicit_count = sum(
            len(re.findall(r"\b" + re.escape(phrase) + r"\b", content_lower))
            for phrase in self.bot.explicit_phrases
        )

        async with get_session() as session:
            stmt = insert(LeaderboardUserStats).values(
                guild_id=message.guild.id,
                user_id=message.author.id,
                xp=0,
                message_count=1,
                word_count=word_count,
                attachment_count=attachment_count,
                explicit_count=explicit_count,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["guild_id", "user_id"],
                set_={
                    "message_count": LeaderboardUserStats.message_count + 1,
                    "word_count": LeaderboardUserStats.word_count + len(message.content.split()),
                    "attachment_count": LeaderboardUserStats.attachment_count
                    + len(message.attachments),
                    "explicit_count": LeaderboardUserStats.explicit_count + explicit_count,
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
                to_assign = int(max(min(xp_mult * math.sqrt(length), max_xp), min_xp))

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

            try:
                if lb_settings.notification_channel:
                    channel = message.guild.get_channel(lb_settings.notification_channel)

                    if not channel:
                        self.logger.debug(
                            f"Notification channel not found for guild {message.guild.id}"
                        )
                        return

                    if not isinstance(channel, discord.abc.Messageable):
                        self.logger.debug(
                            f"Notification channel not messageable in guild {message.guild.id}"
                        )
                        return

                    await channel.send(
                        content=message.author.mention if lb_settings.notification_ping else "",
                        embed=discord.Embed(
                            description=f"🎉 {message.author.mention} has leveled up to **level {user_stats.level}!**",
                            colour=discord.Colour.green(),
                        ),
                    )
                else:
                    await message.reply(
                        embed=discord.Embed(
                            description=f"🎉 {message.author.mention} has leveled up to **level {user_stats.level}!**",
                            colour=discord.Colour.green(),
                        ),
                        mention_author=lb_settings.notification_ping,
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

    # Leaderboard command
    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top"])
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    @commands.cooldown(1, 5)
    async def leaderboard_command(self, ctx: commands.Context["TitaniumBot"]):
        """Gets the leaderboard for the server."""
        if not ctx.guild:
            return

        await ctx.defer()

        if ctx.author.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="You have opted out of optional data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
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
            await ctx.reply(embed=embed)
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
                await ctx.reply(embed=embed)
                return

            pages = generate_lb_embeds(
                guild=ctx.guild,
                author=ctx.author,
                top_users=top_users,
                title="Leaderboard",
                attr="xp",
            )
            pages[0].set_footer(
                text=f"Controlling: @{ctx.author.name}"
                if len(pages) > 1
                else f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            view = LeaderboardReloadPageView(
                embeds=pages,
                timeout=240,
                title="Leaderboard",
                error_description="No users have recorded XP or levels yet.",
                sort_type=LeaderboardUserStats.xp,
                reload_type="xp",
                error_emoji=str(self.bot.error_emoji),
            )

            if len(pages) > 1:
                await ctx.reply(embed=pages[0], view=view)
            else:
                await ctx.reply(embed=pages[0])

    # Level command
    @commands.hybrid_command(name="level", aliases=["lvl"])
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    @app_commands.describe(
        member="Optional: the user to get the XP info from. Defaults to yourself."
    )
    @commands.cooldown(1, 3)
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
                description="This user has opted out of optional data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
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
            await ctx.reply(embed=embed)
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
                await ctx.reply(embed=embed)
                return

            blocked_roles: list[str] = []
            if isinstance(user, discord.Member):
                for role in user.roles:
                    if role.id not in guild_settings.leaderboard_settings.ignored_roles:
                        continue

                    blocked_roles.append(role.mention)

            embed = discord.Embed(
                title="Level Info",
                description=f"{self.bot.warn_emoji} You can't gain new XP as one or more of your roles are ignored: {', '.join(blocked_roles)}"
                if blocked_roles
                else "",
                colour=discord.Colour.light_grey(),
            )

            if guild_settings.leaderboard_settings.levels:
                embed.add_field(name="Level", value=f"{user_stats.level:,}", inline=True)

            embed.add_field(name="XP", value=f"{user_stats.xp:,}", inline=True)

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

            await ctx.reply(embed=embed)

    @commands.hybrid_group(name="xp", description="Set, add and remove XP from users.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def xp_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        handle_group_command_not_found(ctx)

    @xp_group.command(name="set", description="Set the XP of a user.")
    @global_alias("setxp")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3)
    async def set_xp(
        self, ctx: commands.Context["TitaniumBot"], user: discord.Member, xp: int
    ) -> None:
        if not ctx.guild:
            return

        await ctx.defer()

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
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
            await ctx.reply(embed=embed)
            return

        async with get_session() as session:
            stmt = select(LeaderboardUserStats).where(
                LeaderboardUserStats.guild_id == ctx.guild.id,
                LeaderboardUserStats.user_id == ctx.author.id,
            )
            user_stats = (await session.execute(stmt)).scalar_one_or_none()

            if not user_stats:
                user_stats = LeaderboardUserStats(
                    guild_id=ctx.guild.id,
                    user_id=ctx.author.id,
                    xp=max(min(xp, POSTGRES_MAX_INT), POSTGRES_MIN_INT),
                )
                session.add(user_stats)
            else:
                user_stats.xp = max(min(xp, POSTGRES_MAX_INT), POSTGRES_MIN_INT)

        embed = discord.Embed(
            title=f"{self.bot.success_emoji} Done",
            description=f"Set {user.mention}'s XP to `{user_stats.xp:,}`.",
            colour=discord.Colour.green(),
        )
        await ctx.reply(embed=embed)

    @xp_group.command(name="add", description="Add XP to a user.")
    @global_alias("addxp")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3)
    async def add_xp(
        self, ctx: commands.Context["TitaniumBot"], user: discord.Member, xp: int
    ) -> None:
        if not ctx.guild:
            return

        await ctx.defer()

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
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

            await ctx.reply(embed=embed)
            return

        async with get_session() as session:
            stmt = select(LeaderboardUserStats).where(
                LeaderboardUserStats.guild_id == ctx.guild.id,
                LeaderboardUserStats.user_id == ctx.author.id,
            )
            user_stats = (await session.execute(stmt)).scalar_one_or_none()

            if not user_stats:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description=f"**{user.display_name}** has no recorded XP or level.",
                    colour=discord.Colour.red(),
                )

                await ctx.reply(embed=embed)
                return

            old_xp = user_stats.xp
            user_stats.xp = min(user_stats.xp + xp, POSTGRES_MAX_INT)

        embed = discord.Embed(
            title=f"{self.bot.success_emoji} Done",
            description=f"Added `{(user_stats.xp - old_xp):,}` XP to {user.mention}.",
            colour=discord.Colour.green(),
        )
        await ctx.reply(embed=embed)

    @xp_group.command(name="remove", aliases=["deduct"], description="Remove XP from a user.")
    @global_alias("removexp")
    @global_alias("deductxp")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3)
    async def remove_xp(
        self, ctx: commands.Context["TitaniumBot"], user: discord.Member, xp: int
    ) -> None:
        if not ctx.guild:
            return

        await ctx.defer()

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed)
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

            await ctx.reply(embed=embed)
            return

        async with get_session() as session:
            stmt = select(LeaderboardUserStats).where(
                LeaderboardUserStats.guild_id == ctx.guild.id,
                LeaderboardUserStats.user_id == ctx.author.id,
            )
            user_stats = (await session.execute(stmt)).scalar_one_or_none()

            if not user_stats:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description=f"**{user.display_name}** has no recorded XP or level.",
                    colour=discord.Colour.red(),
                )

                await ctx.reply(embed=embed)
                return

            old_xp = user_stats.xp
            user_stats.xp = max(user_stats.xp - xp, POSTGRES_MIN_INT)

        embed = discord.Embed(
            title=f"{self.bot.success_emoji} Done",
            description=f"Removed `{(old_xp - user_stats.xp):,}` XP from {user.mention}.",
            colour=discord.Colour.green(),
        )
        await ctx.reply(embed=embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
