from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord import Message, app_commands
from discord.ext import commands

import lib.embeds.mod_actions as mod_embeds
from lib.classes.case_manager import GuildModCaseManager
from lib.duration import DurationConverter
from lib.embeds.general import not_in_guild
from lib.enums.moderation import CaseType
from lib.helpers.hybrid_adapters import _defer, _stop_loading, defer
from lib.helpers.log_error import log_error
from lib.sql.sql import get_session

if TYPE_CHECKING:
    from main import TitaniumBot


@commands.guild_only()
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.default_permissions(moderate_members=True)
class ModerationBasicCog(
    commands.GroupCog, group_name="mod", description="Moderate server members."
):
    """Basic moderation commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context["TitaniumBot"]) -> bool:
        await _defer(ctx, ephemeral=True)

        if not ctx.guild:
            return False

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        if not config or not config.moderation_enabled:
            await ctx.reply(
                embed=discord.Embed(
                    colour=discord.Colour.red(),
                    title=f"{self.bot.error_emoji} Moderation Disabled",
                    description="The moderation module is disabled. Ask a server admin to turn it on using the `/settings overview` command or the Titanium Dashboard.",
                ),
                ephemeral=True,
            )
            await _stop_loading(ctx)
            return False

        return True

    def _purge_check(
        self, message: discord.Message, source: int, target: discord.User | None
    ) -> bool:
        if message.id == source:
            return False

        if target:
            return message.author.id == target.id

        return True

    def _hierarchy_check(
        self,
        target: discord.Member,
        moderator: discord.Member,
        ctx: commands.Context["TitaniumBot"],
    ) -> bool:
        if not ctx.guild:
            return False

        if self.bot.user and target.id == self.bot.user.id:
            return False

        if target.id == ctx.guild.owner_id:
            return False

        if target.top_role.position >= moderator.top_role.position:
            return False

        return True

    @commands.hybrid_command(name="warn", description="Warn a member for a specified reason.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        member="The member to warn.", reason="Optional: the reason for the warning."
    )
    async def warn(
        self,
        ctx: commands.Context["TitaniumBot"],
        member: discord.Member,
        *,
        reason: str = "",
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        async with defer(ctx, stop_only=True):
            try:
                # Check if member is in guild
                if member.guild.id != ctx.guild.id:
                    return await ctx.reply(ephemeral=True, embed=not_in_guild(self.bot, member))

                # Check if moderating self
                if member.id == ctx.author.id:
                    return await ctx.reply(ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot))

                # Check if target doesn't have higher role
                if not self._hierarchy_check(member, ctx.author, ctx):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.not_allowed(self.bot, member)
                    )

                # Check if member is already being punished
                if (
                    ctx.guild.id in self.bot.punishing
                    and member.id in self.bot.punishing[ctx.guild.id]
                ):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.already_punishing(self.bot, member)
                    )

                # Add member to punishing list
                self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

                # Create case
                async with get_session() as session:
                    manager = GuildModCaseManager(self.bot, ctx.guild, session)

                    case, dm_success, dm_error = await manager.create_case(
                        action=CaseType.WARN,
                        user=member,
                        creator_user=ctx.author,
                        reason=reason,
                    )

                # Send confirmation message
                await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.warned(
                        self.bot,
                        user=member,
                        creator=ctx.author,
                        case=case,
                        dm_success=dm_success,
                        dm_error=dm_error,
                    ),
                )
            finally:
                # Remove member from punishing list
                if (
                    ctx.guild.id in self.bot.punishing
                    and member.id in self.bot.punishing[ctx.guild.id]
                ):
                    self.bot.punishing[ctx.guild.id].remove(member.id)

    @commands.hybrid_command(
        name="mute",
        aliases=["timeout"],
        description="Mute a member for a specified duration.",
    )
    @commands.has_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member to mute.",
        duration="Optional: the duration of the mute (e.g., 10m, 1h, 2h30m).",
        reason="Optional: the reason for the mute.",
    )
    async def mute(
        self,
        ctx: commands.Context["TitaniumBot"],
        member: discord.Member,
        duration: str = "",
        *,
        reason: str = "",
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        async with defer(ctx, stop_only=True):
            try:
                # Check if guild for type checking
                if not ctx.guild:
                    return

                # Check if member is in guild
                if member.guild.id != ctx.guild.id:
                    return await ctx.reply(ephemeral=True, embed=not_in_guild(self.bot, member))

                # Check if moderating self
                if member.id == ctx.author.id:
                    return await ctx.reply(ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot))

                # Check if target doesn't have higher role
                if not self._hierarchy_check(member, ctx.author, ctx):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.not_allowed(self.bot, member)
                    )

                # Check if user is already timed out
                if member.is_timed_out():
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.already_muted(self.bot, member)
                    )

                # Check if member is already being punished
                if (
                    ctx.guild.id in self.bot.punishing
                    and member.id in self.bot.punishing[ctx.guild.id]
                ):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.already_punishing(self.bot, member)
                    )

                # Add member to punishing list
                self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

                # Process duration
                processed_duration = await DurationConverter().convert(ctx, duration)
                processed_reason = reason

                if not ctx.interaction and processed_duration is None:
                    processed_reason = duration + " " + reason if reason else duration

                # Time out user
                try:
                    await member.timeout(
                        (
                            processed_duration
                            if processed_duration and processed_duration.total_seconds() <= 2419200
                            else timedelta(seconds=2419200)
                        ),
                        reason=f"@{ctx.author.name}: {reason}",
                    )
                except discord.Forbidden as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=member.guild.id,
                        error=f"Titanium was not allowed to mute @{member.name} ({member.id})",
                        details=e.text,
                    )

                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.forbidden(self.bot, member)
                    )
                except discord.HTTPException as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=member.guild.id,
                        error=f"Unknown Discord error while muting @{member.name} ({member.id})",
                        details=e.text,
                    )

                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.http_exception(self.bot, member)
                    )

                # Create case
                async with get_session() as session:
                    manager = GuildModCaseManager(self.bot, ctx.guild, session)

                    case, dm_success, dm_error = await manager.create_case(
                        action=CaseType.MUTE,
                        user=member,
                        creator_user=ctx.author,
                        reason=processed_reason,
                        duration=processed_duration,
                    )

                # Send confirmation message
                await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.muted(
                        self.bot,
                        user=member,
                        creator=ctx.author,
                        case=case,
                        dm_success=dm_success,
                        dm_error=dm_error,
                    ),
                )
            finally:
                # Remove member from punishing list
                if (
                    ctx.guild.id in self.bot.punishing
                    and member.id in self.bot.punishing[ctx.guild.id]
                ):
                    self.bot.punishing[ctx.guild.id].remove(member.id)

    @commands.hybrid_command(
        name="unmute",
        aliases=["untimeout"],
        description="Unmute a member.",
    )
    @commands.has_permissions(moderate_members=True)
    @app_commands.describe(member="The member to unmute.")
    async def unmute(
        self,
        ctx: commands.Context["TitaniumBot"],
        member: discord.Member,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        async with defer(ctx, stop_only=True):
            try:
                # Check if guild for type checking
                if not ctx.guild:
                    return

                # Check if member is in guild
                if member.guild.id != ctx.guild.id:
                    return await ctx.reply(ephemeral=True, embed=not_in_guild(self.bot, member))

                # Check if moderating self
                if member.id == ctx.author.id:
                    return await ctx.reply(ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot))

                # Check if target doesn't have higher role
                if not self._hierarchy_check(member, ctx.author, ctx):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.not_allowed(self.bot, member)
                    )

                # Check if user is not muted
                if not member.is_timed_out():
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.already_unmuted(self.bot, member)
                    )

                # Check if member is already being punished
                if (
                    ctx.guild.id in self.bot.punishing
                    and member.id in self.bot.punishing[ctx.guild.id]
                ):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.already_punishing(self.bot, member)
                    )

                # Add member to punishing list
                self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

                # Unmute user
                try:
                    await member.timeout(None, reason=f"Unmuted by @{ctx.author.name}")
                except discord.Forbidden as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=member.guild.id,
                        error=f"Titanium was not allowed to unmute @{member.name} ({member.id})",
                        details=e.text,
                    )

                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.forbidden(self.bot, member)
                    )
                except discord.HTTPException as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=member.guild.id,
                        error=f"Unknown Discord error while unmuting @{member.name} ({member.id})",
                        details=e.text,
                    )

                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.http_exception(self.bot, member)
                    )

                # Get last ummute case
                async with get_session() as session:
                    manager = GuildModCaseManager(self.bot, ctx.guild, session)
                    cases = await manager.get_cases_by_user(member.id)

                    case = next((c for c in cases if c.type == CaseType.MUTE), None)

                    if case:
                        # Close case
                        case, dm_success, dm_error = await manager.close_case(case.id)

                # Send confirmation message
                await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.unmuted(
                        self.bot,
                        user=member,
                        creator=ctx.author,
                        case=case,
                        dm_success=dm_success,
                        dm_error=dm_error,
                    ),
                )
            finally:
                # Remove member from punishing list
                if (
                    ctx.guild.id in self.bot.punishing
                    and member.id in self.bot.punishing[ctx.guild.id]
                ):
                    self.bot.punishing[ctx.guild.id].remove(member.id)

    @commands.hybrid_command(name="kick", description="Kick a member from the server.")
    @commands.has_permissions(kick_members=True)
    @app_commands.describe(
        member="The member to kick.", reason="Optional: the reason for the kick."
    )
    async def kick(
        self,
        ctx: commands.Context["TitaniumBot"],
        member: discord.Member,
        *,
        reason: str = "",
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        async with defer(ctx, stop_only=True):
            try:
                # Check if guild for type checking
                if not ctx.guild:
                    return

                # Check if member is in guild
                if member.guild.id != ctx.guild.id:
                    return await ctx.reply(ephemeral=True, embed=not_in_guild(self.bot, member))

                # Check if moderating self
                if member.id == ctx.author.id:
                    return await ctx.reply(ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot))

                # Check if target doesn't have higher role
                if not self._hierarchy_check(member, ctx.author, ctx):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.not_allowed(self.bot, member)
                    )

                # Check if member is already being punished
                if (
                    ctx.guild.id in self.bot.punishing
                    and member.id in self.bot.punishing[ctx.guild.id]
                ):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.already_punishing(self.bot, member)
                    )

                # Add member to punishing list
                self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

                # Kick user
                try:
                    await member.kick(reason=f"@{ctx.author.name}: {reason}")
                except discord.Forbidden as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=member.guild.id,
                        error=f"Titanium was not allowed to kick @{member.name} ({member.id})",
                        details=e.text,
                    )

                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.forbidden(self.bot, member)
                    )
                except discord.HTTPException as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=member.guild.id,
                        error=f"Unknown Discord error while kicking @{member.name} ({member.id})",
                        details=e.text,
                    )

                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.http_exception(self.bot, member)
                    )

                # Create case
                async with get_session() as session:
                    manager = GuildModCaseManager(self.bot, ctx.guild, session)

                    case, dm_success, dm_error = await manager.create_case(
                        action=CaseType.KICK,
                        user=member,
                        creator_user=ctx.author,
                        reason=reason,
                    )

                # Send confirmation message
                await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.kicked(
                        self.bot,
                        user=member,
                        creator=ctx.author,
                        case=case,
                        dm_success=dm_success,
                        dm_error=dm_error,
                    ),
                )
            finally:
                # Remove member from punishing list
                if (
                    ctx.guild.id in self.bot.punishing
                    and member.id in self.bot.punishing[ctx.guild.id]
                ):
                    self.bot.punishing[ctx.guild.id].remove(member.id)

    @commands.hybrid_command(name="ban", description="Ban a user from the server.")
    @commands.has_permissions(ban_members=True)
    @app_commands.describe(
        user="The user to ban.",
        duration="Optional: the duration of the ban (e.g., 10m, 1h, 2h30m).",
        reason="Optional: the reason for the ban.",
    )
    async def ban(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: discord.User,
        duration: str = "",
        *,
        reason: str = "",
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        async with defer(ctx, stop_only=True):
            try:
                # Check if guild for type checking
                if not ctx.guild:
                    return

                # Check if moderating self
                if user.id == ctx.author.id:
                    return await ctx.reply(ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot))

                # Try to get member from guild
                member = ctx.guild.get_member(user.id)
                if not member:
                    try:
                        member = await ctx.guild.fetch_member(user.id)
                    except discord.NotFound:
                        member = None

                # Check if target doesn't have higher role
                if isinstance(member, discord.Member) and not self._hierarchy_check(
                    member, ctx.author, ctx
                ):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.not_allowed(self.bot, user)
                    )

                # Check if member is already being punished
                if (
                    ctx.guild.id in self.bot.punishing
                    and user.id in self.bot.punishing[ctx.guild.id]
                ):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.already_punishing(self.bot, user)
                    )

                # Add member to punishing list
                self.bot.punishing.setdefault(ctx.guild.id, []).append(user.id)

                # Check if user is already banned
                try:
                    await ctx.guild.fetch_ban(user)
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.already_banned(self.bot, user)
                    )
                except discord.NotFound:
                    pass

                # Process duration
                processed_duration = await DurationConverter().convert(ctx, duration)
                processed_reason = reason

                if not ctx.interaction and processed_duration is None:
                    processed_reason = duration + " " + reason if reason else duration

                # Get config
                config = await self.bot.fetch_guild_config(ctx.guild.id)

                # Ban user
                try:
                    await ctx.guild.ban(
                        user=user,
                        reason=f"@{ctx.author.name}: {processed_reason}",
                        delete_message_seconds=config.moderation_settings.ban_days * 86400
                        if config
                        else 0,
                    )
                except discord.Forbidden as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=ctx.guild.id,
                        error=f"Titanium was not allowed to ban @{user.name} ({user.id})",
                        details=e.text,
                    )

                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.forbidden(self.bot, user)
                    )
                except discord.HTTPException as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=ctx.guild.id,
                        error=f"Unknown Discord error while banning @{user.name} ({user.id})",
                        details=e.text,
                    )

                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.http_exception(self.bot, user)
                    )

                # Create case
                async with get_session() as session:
                    manager = GuildModCaseManager(self.bot, ctx.guild, session)

                    case, dm_success, dm_error = await manager.create_case(
                        action=CaseType.BAN,
                        user=user,
                        creator_user=ctx.author,
                        reason=processed_reason,
                        duration=processed_duration,
                    )

                # Send confirmation message
                await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.banned(
                        self.bot,
                        user=user,
                        creator=ctx.author,
                        case=case,
                        dm_success=dm_success,
                        dm_error=dm_error,
                    ),
                )
            finally:
                # Remove member from punishing list
                if (
                    ctx.guild.id in self.bot.punishing
                    and user.id in self.bot.punishing[ctx.guild.id]
                ):
                    self.bot.punishing[ctx.guild.id].remove(user.id)

    @commands.hybrid_command(name="unban", description="Unban a member from the server.")
    @commands.has_permissions(ban_members=True)
    @app_commands.describe(user="The user to unban.")
    async def unban(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: discord.User,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        async with defer(ctx, stop_only=True):
            try:
                # Check if guild for type checking
                if not ctx.guild:
                    return

                # Check if moderating self
                if user.id == ctx.author.id:
                    return await ctx.reply(ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot))

                # Check if user is already being punished
                if (
                    ctx.guild.id in self.bot.punishing
                    and user.id in self.bot.punishing[ctx.guild.id]
                ):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.already_punishing(self.bot, user)
                    )

                # Add user to punishing list
                self.bot.punishing.setdefault(ctx.guild.id, []).append(user.id)

                # Check if user is not banned
                try:
                    await ctx.guild.fetch_ban(user)
                except discord.NotFound:
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.already_unbanned(self.bot, user)
                    )

                # Unban user
                try:
                    await ctx.guild.unban(user, reason=f"Unbanned by @{ctx.author.name}")
                except discord.Forbidden as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=ctx.guild.id,
                        error=f"Titanium was not allowed to unban @{user.name} ({user.id})",
                        details=e.text,
                    )

                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.forbidden(self.bot, user)
                    )
                except discord.HTTPException as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=ctx.guild.id,
                        error=f"Unknown Discord error while unbanning @{user.name} ({user.id})",
                        details=e.text,
                    )

                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.http_exception(self.bot, user)
                    )

                # Get last ban case
                async with get_session() as session:
                    manager = GuildModCaseManager(self.bot, ctx.guild, session)
                    cases = await manager.get_cases_by_user(user.id)

                    case = next((c for c in cases if c.type == CaseType.BAN), None)

                    if case:
                        # Close case
                        case, dm_success, dm_error = await manager.close_case(case.id)

                # Send confirmation message
                await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.unbanned(
                        self.bot,
                        user=user,
                        creator=ctx.author,
                        case=case,
                        dm_success=dm_success,
                        dm_error=dm_error,
                    ),
                )
            finally:
                # Remove user from punishing list
                if (
                    ctx.guild.id in self.bot.punishing
                    and user.id in self.bot.punishing[ctx.guild.id]
                ):
                    self.bot.punishing[ctx.guild.id].remove(user.id)

    @commands.hybrid_command(
        name="purge",
        description="Purge up to 100 messages up to 14 days old from a channel.",
        aliases=["clear", "clean", "scrub"],
    )
    @commands.has_permissions(manage_messages=True)
    @app_commands.describe(
        amount="The number of messages to purge (max 100).",
        user="Optional: the user whose messages should be purged.",
    )
    async def purge(
        self,
        ctx: commands.Context["TitaniumBot"],
        amount: commands.Range[int, 1, 100],
        user: discord.User | None = None,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        async with defer(ctx, stop_only=True):
            try:
                if isinstance(
                    ctx.channel,
                    (discord.PartialMessageable, discord.DMChannel, discord.GroupChannel),
                ):
                    await ctx.reply(ephemeral=True, embed=mod_embeds.cannot_purge(self.bot))
                    return

                limit = amount if ctx.interaction else amount + 1

                deleted = await ctx.channel.purge(
                    limit=limit,
                    bulk=True,
                    reason=f"Purged by @{ctx.author.name}",
                    check=lambda m: self._purge_check(m, ctx.message.id, user),
                )

                await ctx.reply(
                    ephemeral=True, embed=mod_embeds.purged(self.bot, ctx.author, len(deleted))
                )
            except discord.Forbidden as e:
                if not isinstance(
                    ctx.channel,
                    (discord.PartialMessageable, discord.DMChannel, discord.GroupChannel),
                ):
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=ctx.guild.id,
                        error=f"Titanium was not allowed to purge messages in #{ctx.channel.name} ({ctx.channel.id})",
                        details=e.text,
                    )

                return await ctx.reply(
                    ephemeral=True, embed=mod_embeds.forbidden(self.bot, ctx.author)
                )
            except discord.HTTPException as e:
                if not isinstance(
                    ctx.channel,
                    (discord.PartialMessageable, discord.DMChannel, discord.GroupChannel),
                ):
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=ctx.guild.id,
                        error=f"Unknown Discord error while purging messages in #{ctx.channel.name} ({ctx.channel.id})",
                        details=e.text,
                    )

                return await ctx.reply(
                    ephemeral=True, embed=mod_embeds.http_exception(self.bot, ctx.author)
                )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ModerationBasicCog(bot))
