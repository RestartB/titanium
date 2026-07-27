import asyncio
import logging
import math
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import TYPE_CHECKING, Awaitable

import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from lib.embeds.leaderboard import generate_lb_embeds
from lib.enums.leaderboard import LeaderboardCalcType, LeaderboardVcCalcType
from lib.helpers.cache import get_or_fetch_member
from lib.helpers.global_alias import add_global_aliases, global_alias, remove_global_aliases
from lib.helpers.hybrid import handle_group_command_not_found
from lib.helpers.log_error import log_error
from lib.sql.sql import GuildLeaderboardSettings, LeaderboardUserStats, get_session
from lib.views.pagination import LeaderboardReloadPageView

if TYPE_CHECKING:
    from main import TitaniumBot

POSTGRES_MAX_INT = 9223372036854775807
POSTGRES_MIN_INT = -9223372036854775808
DAILY_SNAPSHOT_TIME = time(hour=0, minute=0, tzinfo=UTC)


@dataclass
class UserVoiceTimes:
    start_date: datetime
    last_check: datetime


class LeaderboardCog(commands.Cog):
    """Monitors messages and processes leaderboard"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("leaderboard")
        self.member_last_trigger: dict[int, dict[int, datetime]] = {}
        self.voice_states: dict[int, dict[int, UserVoiceTimes]] = {}
        self.initial_vc_state_task: asyncio.Task[None] | None = None

    async def cog_load(self) -> None:
        self.take_daily_snapshots.start()
        self.check_voice.start()
        add_global_aliases(self, self.bot)

        self.initial_vc_state_task = asyncio.create_task(self.get_initial_vc_state())

    async def cog_unload(self) -> None:
        self.take_daily_snapshots.cancel()
        self.check_voice.cancel()
        remove_global_aliases(self, self.bot)

        if self.initial_vc_state_task:
            self.initial_vc_state_task.cancel()

    async def get_initial_vc_state(self) -> None:
        await self.bot.wait_until_ready()
        self.logger.info("Checking guild VC states...")

        for guild in self.bot.guilds:
            self.logger.debug(f"Checking guild {guild.id}...")
            config = await self.bot.fetch_guild_config(guild.id)
            if not config or not config.leaderboard_enabled:
                self.logger.debug(f"Leaderboard disabled in {guild.id}")
                continue

            now = discord.utils.utcnow()
            for channel in guild.channels:
                if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                    continue

                self.logger.debug(f"Checking channel {channel.name}...")
                for voice_state in channel.voice_states:
                    if voice_state in self.voice_states.setdefault(guild.id, {}):
                        continue
                    self.voice_states.setdefault(guild.id, {})[voice_state] = UserVoiceTimes(
                        start_date=now, last_check=now
                    )

                self.logger.debug(
                    f"{len(self.voice_states.get(guild.id, []))} user VC states being tracked in {guild.id}"
                )

        self.logger.info(f"Done. Tracking {len(self.voice_states)} guilds.")

    # Snapshot task
    @tasks.loop(time=DAILY_SNAPSHOT_TIME)
    async def take_daily_snapshots(self) -> None:
        await self.bot.wait_until_ready()

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

    async def sync_user_level(
        self,
        member: discord.Member,
        user_stats: LeaderboardUserStats,
        lb_settings: GuildLeaderboardSettings,
    ) -> tuple[int, int]:
        levels = lb_settings.levels
        levels.sort(key=lambda level: level.xp)

        old_level = user_stats.level
        new_level = 0
        for level in levels:
            if user_stats.xp >= level.xp:
                new_level += 1
            else:
                break

        if new_level != old_level:
            user_stats.level = new_level

            roles_to_remove = set()
            roles_to_add = set()

            for i, level in enumerate(levels, start=1):
                if not lb_settings.stack_roles:
                    if i == new_level:
                        roles_to_add.update(
                            member.guild.get_role(role_id) for role_id in level.reward_roles
                        )
                    else:
                        roles_to_remove.update(
                            member.guild.get_role(role_id) for role_id in level.reward_roles
                        )
                else:
                    if i <= new_level:
                        roles_to_add.update(
                            member.guild.get_role(role_id) for role_id in level.reward_roles
                        )
                    else:
                        roles_to_remove.update(
                            member.guild.get_role(role_id) for role_id in level.reward_roles
                        )

            roles_to_add = {r for r in roles_to_add if r and r < member.guild.me.top_role}
            roles_to_remove = {
                r for r in roles_to_remove if r and r < member.guild.me.top_role
            } - roles_to_add

            if member.guild.me.guild_permissions.manage_roles:
                try:
                    if roles_to_remove:
                        await member.remove_roles(
                            *roles_to_remove,
                            reason=f"Level changed (level {new_level})",
                            atomic=False,
                        )

                    if roles_to_add:
                        await member.add_roles(
                            *roles_to_add, reason=f"Level changed (level {new_level})", atomic=False
                        )
                except discord.Forbidden as e:
                    await log_error(
                        bot=self.bot,
                        module="Leaderboard",
                        guild_id=member.guild.id,
                        error=f"Titanium was not allowed to add / remove roles for {member.id}",
                        details=str(e.text),
                        exc=e,
                    )
                except discord.HTTPException as e:
                    await log_error(
                        bot=self.bot,
                        module="Leaderboard",
                        guild_id=member.guild.id,
                        error=f"Unknown Discord error while adding / removing roles for {member.id}",
                        details=str(e.text),
                        exc=e,
                    )
            elif roles_to_add or roles_to_remove:
                await log_error(
                    bot=self.bot,
                    module="Leaderboard",
                    guild_id=member.guild.id,
                    error="Titanium does not have permission to add or remove roles",
                    details='Please ensure that Titanium has the "Manage Roles" permission so it can add / remove roles.',
                    send_webhook=False,
                )

        return old_level, new_level

    async def handle_voice_xp(self, member: discord.Member, start_time: datetime) -> None:
        # dropped out of tracking
        if (
            member.guild.id not in self.voice_states
            or member.id not in self.voice_states[member.guild.id]
        ):
            return

        # stop tracking as they have opted out
        if member.id in self.bot.opt_out and member.id in self.voice_states[member.guild.id]:
            self.logger.debug(f"User has opted out: {member.id}")
            del self.voice_states[member.guild.id][member.id]
            return

        # stop tracking as leaderboard is disabled
        guild_settings = await self.bot.fetch_guild_config(member.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            self.logger.debug(f"Leaderboard disabled for guild: {member.guild.id}")
            del self.voice_states[member.guild.id]
            return

        lb_settings = guild_settings.leaderboard_settings

        if member.bot and not lb_settings.bot_vc_tracking:
            self.logger.debug("Bot vc tracking is disabled")
            return

        if any(role.id in lb_settings.ignored_roles for role in member.roles):
            self.logger.debug(f"Tracking from member with ignored role: {member.id}")
            return

        async with get_session() as session:
            stmt = insert(LeaderboardUserStats).values(
                guild_id=member.guild.id, user_id=member.id, vc_minutes=1
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["guild_id", "user_id"],
                set_={
                    "vc_minutes": LeaderboardUserStats.vc_minutes + 1,
                },
            ).returning(LeaderboardUserStats)

            result = await session.execute(stmt)
            user_stats = result.scalar_one()

            if not lb_settings.vc_enabled:
                self.logger.debug(f"VC XP not enabled for guild: {member.guild.id}")
                return

            if member.bot and not lb_settings.bot_vc_xp:
                self.logger.debug("Bot vc xp is disabled")
                return

            if (discord.utils.utcnow() - start_time).total_seconds() < 60 * lb_settings.vc_delay:
                self.logger.debug(f"Delay not met yet: {member.id}")
                return

            to_assign = 0
            if lb_settings.vc_mode == LeaderboardVcCalcType.FIXED and lb_settings.vc_base_xp:
                to_assign = lb_settings.vc_base_xp
            elif (
                lb_settings.vc_mode == LeaderboardVcCalcType.RANDOM
                and lb_settings.vc_min_xp
                and lb_settings.vc_max_xp
            ):
                to_assign = random.randint(lb_settings.vc_min_xp, lb_settings.vc_max_xp)

            user_stats.xp = min(user_stats.xp + to_assign, POSTGRES_MAX_INT)

            old_level, new_level = await self.sync_user_level(member, user_stats, lb_settings)
            user_stats.level = new_level

        if (
            lb_settings.levelup_notifications
            and lb_settings.notification_channel
            and new_level > old_level
        ):
            try:
                channel = member.guild.get_channel(lb_settings.notification_channel)

                if not channel:
                    self.logger.debug(f"Notification channel not found for guild {member.guild.id}")
                    return

                if not isinstance(channel, discord.abc.Messageable):
                    self.logger.debug(
                        f"Notification channel not messageable in guild {member.guild.id}"
                    )
                    return

                if not channel.permissions_for(member.guild.me).send_messages:
                    self.logger.debug(
                        f"Titanium doesn't have perms to send messages in {channel.id}"
                    )
                    return

                await channel.send(
                    content=member.mention if lb_settings.notification_ping else "",
                    embed=discord.Embed(
                        description=f"🎉 {member.mention} has leveled up to **level {user_stats.level}!**",
                        colour=discord.Colour.green(),
                    ),
                )
            except discord.Forbidden as e:
                await log_error(
                    bot=self.bot,
                    module="Leaderboard",
                    guild_id=member.guild.id,
                    error=f"Titanium was not allowed to send leaderboard notification in #{channel.name if channel and not isinstance(channel, (discord.PartialMessageable, discord.DMChannel)) else 'Unknown'} ({channel.id if channel else 'unknown'})",
                    details=str(e.text),
                    exc=e,
                )
            except discord.HTTPException as e:
                await log_error(
                    bot=self.bot,
                    module="Leaderboard",
                    guild_id=member.guild.id,
                    error=f"Unknown Discord error while sending leaderboard notification in #{channel.name if channel and not isinstance(channel, (discord.PartialMessageable, discord.DMChannel)) else 'Unknown'} ({channel.id if channel else 'unknown'})",
                    details=str(e.text),
                    exc=e,
                )

    # Check voice status every second
    @tasks.loop(seconds=1)
    async def check_voice(self) -> None:
        now = discord.utils.utcnow()

        to_run: list[Awaitable[None]] = []
        for guild_id, states in list(self.voice_states.items()):
            guild = self.bot.get_guild(guild_id)
            if not guild:
                self.logger.debug(f"Voice guild not found: {guild_id}")
                del self.voice_states[guild_id]
                continue

            states = self.voice_states[guild_id]

            for user_id, user in list(states.items()):
                if (now - user.last_check).total_seconds() < 60:
                    self.logger.debug(f"60 seconds not passed: {user_id}")
                    continue

                self.voice_states[guild_id][user_id].last_check = now
                member = await get_or_fetch_member(self.bot, guild, user_id)
                if not member:
                    self.logger.debug(f"Voice member not found: {user_id}")
                    del self.voice_states[guild_id][user_id]
                    continue

                to_run.append(self.handle_voice_xp(member, user.start_date))

        self.logger.debug(f"Running {len(to_run)} checks")
        await asyncio.gather(*to_run)

    # Voice change event
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        now = discord.utils.utcnow()

        # opted out
        if member.id in self.bot.opt_out:
            return

        if (
            not before.channel
            and after.channel
            and member.id not in self.voice_states.setdefault(member.guild.id, {})
        ):
            # start tracking
            self.voice_states.setdefault(member.guild.id, {})[member.id] = UserVoiceTimes(
                start_date=now, last_check=now
            )
        elif before.channel and not after.channel and member.guild.id in self.voice_states:
            # stop tracking
            self.voice_states[member.guild.id].pop(member.id, None)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        # guild isn't available, let's not touch it
        # could be a discord outage sending false events
        if guild.unavailable:
            return

        if guild.id in self.voice_states:
            del self.voice_states[guild.id]

    # Message event
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.is_system() or isinstance(message.author, discord.User):
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

        if message.author.bot and not lb_settings.bot_message_tracking:
            self.logger.debug("Bot message tracking is disabled")
            return

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

            if message.author.bot and not lb_settings.bot_message_xp:
                self.logger.debug("Bot message xp is disabled")
                return

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

            user_stats.xp = min(user_stats.xp + to_assign, POSTGRES_MAX_INT)

            old_level, new_level = await self.sync_user_level(
                message.author, user_stats, lb_settings
            )
            user_stats.level = new_level

        if lb_settings.levelup_notifications and new_level > old_level:
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

                    if not channel.permissions_for(message.guild.me).send_messages:
                        self.logger.debug(
                            f"Titanium doesn't have perms to send messages in {channel.id}"
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
                    if not message.channel.permissions_for(message.guild.me).send_messages:
                        self.logger.debug(
                            f"Titanium doesn't have perms to send messages in {message.channel.id}"
                        )
                        return

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
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent) -> None:
        guild_settings = await self.bot.fetch_guild_config(payload.guild_id)
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
                    LeaderboardUserStats.guild_id == payload.guild_id,
                    LeaderboardUserStats.user_id == payload.user.id,
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
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @commands.cooldown(1, 5)
    async def leaderboard_command(
        self, ctx: commands.Context["TitaniumBot"], ephemeral: bool = False
    ):
        """Gets the leaderboard for the server."""
        if not ctx.guild:
            return

        await ctx.defer(ephemeral=ephemeral)

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        async with get_session() as session:
            stmt = (
                select(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == ctx.guild.id, LeaderboardUserStats.xp != 0)
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
                await ctx.reply(embed=embed, ephemeral=ephemeral)
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

            await ctx.reply(embed=pages[0], view=view, ephemeral=ephemeral)

    # Level command
    @commands.hybrid_command(name="level", aliases=["lvl"])
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    @app_commands.describe(
        member="Optional: the user to get the XP info from. Defaults to yourself.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 3)
    async def level_command(
        self,
        ctx: commands.Context["TitaniumBot"],
        member: discord.Member | None = None,
        ephemeral: bool = False,
    ):
        """Check your level and XP or another member's level and XP."""
        if not ctx.guild:
            return

        await ctx.defer(ephemeral=ephemeral)

        user = member or ctx.author

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
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
                await ctx.reply(embed=embed, ephemeral=ephemeral)
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

            await ctx.reply(embed=embed, ephemeral=ephemeral)

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
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @commands.cooldown(1, 3)
    async def set_xp(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: discord.Member,
        xp: int,
        ephemeral: bool = False,
    ) -> None:
        if not ctx.guild:
            return

        await ctx.defer(ephemeral=ephemeral)

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        async with get_session() as session:
            stmt = select(LeaderboardUserStats).where(
                LeaderboardUserStats.guild_id == ctx.guild.id,
                LeaderboardUserStats.user_id == user.id,
            )
            user_stats = (await session.execute(stmt)).scalar_one_or_none()

            if not user_stats:
                user_stats = LeaderboardUserStats(
                    guild_id=ctx.guild.id,
                    user_id=user.id,
                    xp=max(min(xp, POSTGRES_MAX_INT), POSTGRES_MIN_INT),
                )
                session.add(user_stats)
            else:
                user_stats.xp = max(min(xp, POSTGRES_MAX_INT), POSTGRES_MIN_INT)

            _, new_level = await self.sync_user_level(
                user, user_stats, guild_settings.leaderboard_settings
            )
            user_stats.level = new_level

        embed = discord.Embed(
            title=f"{self.bot.success_emoji} Done",
            description=f"Set {user.mention}'s XP to `{user_stats.xp:,}`.",
            colour=discord.Colour.green(),
        )
        await ctx.reply(embed=embed, ephemeral=ephemeral)

    @xp_group.command(name="add", description="Add XP to a user.")
    @global_alias("addxp")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @commands.cooldown(1, 3)
    async def add_xp(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: discord.Member,
        xp: int,
        ephemeral: bool = False,
    ) -> None:
        if not ctx.guild:
            return

        await ctx.defer(ephemeral=ephemeral)

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )

            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        async with get_session() as session:
            stmt = select(LeaderboardUserStats).where(
                LeaderboardUserStats.guild_id == ctx.guild.id,
                LeaderboardUserStats.user_id == user.id,
            )
            user_stats = (await session.execute(stmt)).scalar_one_or_none()

            if not user_stats:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description=f"**{user.display_name}** has no recorded XP or level.",
                    colour=discord.Colour.red(),
                )

                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            old_xp = user_stats.xp
            user_stats.xp = min(user_stats.xp + xp, POSTGRES_MAX_INT)

            _, new_level = await self.sync_user_level(
                user, user_stats, guild_settings.leaderboard_settings
            )
            user_stats.level = new_level

        embed = discord.Embed(
            title=f"{self.bot.success_emoji} Done",
            description=f"Added `{(user_stats.xp - old_xp):,}` XP to {user.mention}.",
            colour=discord.Colour.green(),
        )
        await ctx.reply(embed=embed, ephemeral=ephemeral)

    @xp_group.command(name="remove", aliases=["deduct"], description="Remove XP from a user.")
    @global_alias("removexp")
    @global_alias("deductxp")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @commands.cooldown(1, 3)
    async def remove_xp(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: discord.Member,
        xp: int,
        ephemeral: bool = False,
    ) -> None:
        if not ctx.guild:
            return

        await ctx.defer(ephemeral=ephemeral)

        if user.id in self.bot.opt_out:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use leaderboard features.",
                colour=discord.Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
        if (
            not guild_settings
            or not guild_settings.leaderboard_settings
            or not guild_settings.leaderboard_enabled
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Leaderboard Disabled",
                description="The leaderboard system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=discord.Colour.red(),
            )

            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        async with get_session() as session:
            stmt = select(LeaderboardUserStats).where(
                LeaderboardUserStats.guild_id == ctx.guild.id,
                LeaderboardUserStats.user_id == user.id,
            )
            user_stats = (await session.execute(stmt)).scalar_one_or_none()

            if not user_stats:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Data",
                    description=f"**{user.display_name}** has no recorded XP or level.",
                    colour=discord.Colour.red(),
                )

                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            old_xp = user_stats.xp
            user_stats.xp = max(user_stats.xp - xp, POSTGRES_MIN_INT)

            _, new_level = await self.sync_user_level(
                user, user_stats, guild_settings.leaderboard_settings
            )
            user_stats.level = new_level

        embed = discord.Embed(
            title=f"{self.bot.success_emoji} Done",
            description=f"Removed `{(old_xp - user_stats.xp):,}` XP from {user.mention}.",
            colour=discord.Colour.green(),
        )
        await ctx.reply(embed=embed, ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(LeaderboardCog(bot))
