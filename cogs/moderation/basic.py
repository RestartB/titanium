from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

import discord
from discord import Message, app_commands
from discord.ext import commands

import lib.embeds.mod_actions as mod_embeds
from lib.classes.case_manager import GuildModCaseManager
from lib.embeds.dm_notifs import unmuted_dm
from lib.embeds.general import not_in_guild
from lib.enums.moderation import CaseType
from lib.helpers.cache import get_or_fetch_member
from lib.helpers.dm import send_dm
from lib.helpers.duration import DurationConverter
from lib.helpers.hybrid import _defer, _stop_loading, defer
from lib.helpers.log_error import log_error
from lib.sql.sql import ModCase, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class PunishmentResult(Enum):
    SUCCESS = 1
    NOT_IN_GUILD = 2
    CANT_MOD_SELF = 3
    NOT_ALLOWED = 4
    BOT_NOT_ALLOWED = 5
    ALREADY_PUNISHING = 6
    ALREADY_PUNISHED = 7
    FORBIDDEN = 8
    UNKNOWN = 9


@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@commands.guild_only()
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
                    description="The moderation module is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                ),
                ephemeral=True,
            )
            await _stop_loading(ctx)
            return False

        return True

    def _purge_check(
        self, message: discord.Message, source: int, target: discord.User | None, bot_only: bool
    ) -> bool:
        # don't delete the user's command message
        if message.id == source:
            return False

        # we can only bulk delete messages 14 days old or newer
        if discord.utils.utcnow() - message.created_at > timedelta(days=14):
            return False

        if bot_only:
            return message.author.bot

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

        if moderator.id == ctx.guild.owner_id:
            return True

        if target.id == ctx.guild.owner_id:
            return False

        if target.top_role >= moderator.top_role:
            return False

        return True

    def _bot_perms_check(
        self,
        target: discord.Member,
        ctx: commands.Context["TitaniumBot"],
    ):
        if not ctx.guild:
            return False

        if target.top_role >= ctx.guild.me.top_role:
            return False

        return True

    async def _warn_member(
        self, ctx: commands.Context["TitaniumBot"], member: discord.Member, reason: str
    ) -> tuple[PunishmentResult, Optional[ModCase], Optional[bool], Optional[str]]:
        # Check if member is in guild
        if not ctx.guild or member.guild.id != ctx.guild.id:
            return PunishmentResult.NOT_IN_GUILD, None, None, None

        try:
            # Check if moderating self
            if member.id == ctx.author.id:
                return PunishmentResult.CANT_MOD_SELF, None, None, None

            # Check if target doesn't have higher role
            if not isinstance(ctx.author, discord.Member) or not self._hierarchy_check(
                member, ctx.author, ctx
            ):
                return PunishmentResult.NOT_ALLOWED, None, None, None

            # Check if member is already being punished
            if ctx.guild.id in self.bot.punishing and member.id in self.bot.punishing[ctx.guild.id]:
                return PunishmentResult.ALREADY_PUNISHING, None, None, None

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

            return PunishmentResult.SUCCESS, case, dm_success, dm_error
        finally:
            # Remove member from punishing list
            if ctx.guild.id in self.bot.punishing and member.id in self.bot.punishing[ctx.guild.id]:
                self.bot.punishing[ctx.guild.id].remove(member.id)

    async def _mute_member(
        self,
        ctx: commands.Context["TitaniumBot"],
        member: discord.Member,
        duration: str,
        reason: str,
    ) -> tuple[PunishmentResult, Optional[ModCase], Optional[bool], Optional[str]]:
        # Check if member is in guild
        if not ctx.guild or member.guild.id != ctx.guild.id:
            return PunishmentResult.NOT_IN_GUILD, None, None, None

        try:
            # Check if moderating self
            if member.id == ctx.author.id:
                return PunishmentResult.CANT_MOD_SELF, None, None, None

            # Check if target doesn't have higher role
            if not isinstance(ctx.author, discord.Member) or not self._hierarchy_check(
                member, ctx.author, ctx
            ):
                return PunishmentResult.NOT_ALLOWED, None, None, None

            # Check if Titanium can punish target
            if not self._bot_perms_check(member, ctx):
                return PunishmentResult.BOT_NOT_ALLOWED, None, None, None

            # Check if user is already timed out
            if member.is_timed_out():
                return PunishmentResult.ALREADY_PUNISHED, None, None, None

            # Check if member is already being punished
            if ctx.guild.id in self.bot.punishing and member.id in self.bot.punishing[ctx.guild.id]:
                return PunishmentResult.ALREADY_PUNISHING, None, None, None

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
                return PunishmentResult.FORBIDDEN, None, None, None
            except discord.HTTPException as e:
                await log_error(
                    bot=self.bot,
                    module="Moderation",
                    guild_id=member.guild.id,
                    error=f"Unknown Discord error while muting @{member.name} ({member.id})",
                    details=e.text,
                )
                return PunishmentResult.UNKNOWN, None, None, None

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

            return PunishmentResult.SUCCESS, case, dm_success, dm_error
        finally:
            # Remove member from punishing list
            if ctx.guild.id in self.bot.punishing and member.id in self.bot.punishing[ctx.guild.id]:
                self.bot.punishing[ctx.guild.id].remove(member.id)

    async def _kick_member(
        self, ctx: commands.Context["TitaniumBot"], member: discord.Member, reason: str
    ) -> tuple[PunishmentResult, Optional[ModCase], Optional[bool], Optional[str]]:
        # Check if member is in guild
        if not ctx.guild or member.guild.id != ctx.guild.id:
            return PunishmentResult.NOT_IN_GUILD, None, None, None

        try:
            # Check if moderating self
            if member.id == ctx.author.id:
                return PunishmentResult.CANT_MOD_SELF, None, None, None

            # Check if target doesn't have higher role
            if not isinstance(ctx.author, discord.Member) or not self._hierarchy_check(
                member, ctx.author, ctx
            ):
                return PunishmentResult.NOT_ALLOWED, None, None, None

            # Check if Titanium can punish target
            if not self._bot_perms_check(member, ctx):
                return PunishmentResult.BOT_NOT_ALLOWED, None, None, None

            # Check if member is already being punished
            if ctx.guild.id in self.bot.punishing and member.id in self.bot.punishing[ctx.guild.id]:
                return PunishmentResult.ALREADY_PUNISHING, None, None, None

            # Add member to punishing list
            self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

            # Create case
            async with get_session() as session:
                manager = GuildModCaseManager(self.bot, ctx.guild, session)

                case, dm_success, dm_error = await manager.create_case(
                    action=CaseType.KICK,
                    user=member,
                    creator_user=ctx.author,
                    reason=reason,
                )

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
                    await manager.delete_case(case.id, raise_not_found=False)
                    return PunishmentResult.FORBIDDEN, None, None, None
                except discord.HTTPException as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=member.guild.id,
                        error=f"Unknown Discord error while kicking @{member.name} ({member.id})",
                        details=e.text,
                    )
                    await manager.delete_case(case.id, raise_not_found=False)
                    return PunishmentResult.UNKNOWN, None, None, None
                except Exception as e:
                    await manager.delete_case(case.id, raise_not_found=False)
                    raise e

            return PunishmentResult.SUCCESS, case, dm_success, dm_error
        finally:
            # Remove member from punishing list
            if ctx.guild.id in self.bot.punishing and member.id in self.bot.punishing[ctx.guild.id]:
                self.bot.punishing[ctx.guild.id].remove(member.id)

    async def _ban_member(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: discord.User | discord.Member,
        duration: str,
        reason: str,
    ) -> tuple[PunishmentResult, Optional[ModCase], Optional[bool], Optional[str]]:
        # Check if member is in guild
        if not ctx.guild:
            raise RuntimeError("No guild when there should be one")

        try:
            # Check if moderating self
            if user.id == ctx.author.id:
                return PunishmentResult.CANT_MOD_SELF, None, None, None

            # Try to get member from guild
            member = await get_or_fetch_member(self.bot, ctx.guild, user.id)

            # Check if target doesn't have higher role
            if not isinstance(ctx.author, discord.Member) or (
                isinstance(member, discord.Member)
                and not self._hierarchy_check(member, ctx.author, ctx)
            ):
                return PunishmentResult.NOT_ALLOWED, None, None, None

            # Check if Titanium can punish target
            if isinstance(member, discord.Member) and not self._bot_perms_check(member, ctx):
                return PunishmentResult.BOT_NOT_ALLOWED, None, None, None

            # Check if member is already being punished
            if ctx.guild.id in self.bot.punishing and user.id in self.bot.punishing[ctx.guild.id]:
                return PunishmentResult.ALREADY_PUNISHING, None, None, None

            # Add member to punishing list
            self.bot.punishing.setdefault(ctx.guild.id, []).append(user.id)

            # Check if user is already banned
            try:
                await ctx.guild.fetch_ban(user)
                return PunishmentResult.ALREADY_PUNISHED, None, None, None
            except discord.NotFound:
                pass

            # Process duration
            processed_duration = await DurationConverter().convert(ctx, duration)
            processed_reason = reason

            if not ctx.interaction and processed_duration is None:
                processed_reason = duration + " " + reason if reason else duration

            # Get config
            config = await self.bot.fetch_guild_config(ctx.guild.id)

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
                    await manager.delete_case(case.id, raise_not_found=False)
                    return PunishmentResult.FORBIDDEN, None, None, None
                except discord.HTTPException as e:
                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=ctx.guild.id,
                        error=f"Unknown Discord error while banning @{user.name} ({user.id})",
                        details=e.text,
                    )
                    await manager.delete_case(case.id, raise_not_found=False)
                    return PunishmentResult.UNKNOWN, None, None, None
                except Exception as e:
                    await manager.delete_case(case.id, raise_not_found=False)
                    raise e

            return PunishmentResult.SUCCESS, case, dm_success, dm_error
        finally:
            # Remove member from punishing list
            if ctx.guild.id in self.bot.punishing and user.id in self.bot.punishing[ctx.guild.id]:
                self.bot.punishing[ctx.guild.id].remove(user.id)

    @commands.hybrid_command(name="warn", description="Warn a member for a specified reason.")
    @commands.check_any(
        commands.has_permissions(kick_members=True),
        commands.has_permissions(ban_members=True),
        commands.has_permissions(moderate_members=True),
    )
    @app_commands.describe(
        member="The member to warn.", reason="Optional: the reason for the warning."
    )
    @commands.cooldown(1, 5)
    async def warn(
        self,
        ctx: commands.Context["TitaniumBot"],
        member: discord.Member,
        *,
        reason: str = "",
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        del_kwargs: dict[str, Any] = (
            {"delete_after": 5.0}
            if config and config.moderation_settings.delete_confirmation
            else {}
        )

        async with defer(ctx, stop_only=True):
            result, case, dm_success, dm_error = await self._warn_member(ctx, member, reason)

            if (
                result == PunishmentResult.SUCCESS
                and (dm_success is not None)
                and (dm_error is not None)
            ):
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
                    **del_kwargs,
                )
            elif result == PunishmentResult.NOT_IN_GUILD:
                await ctx.reply(ephemeral=True, embed=not_in_guild(self.bot, member), **del_kwargs)
            elif result == PunishmentResult.CANT_MOD_SELF:
                await ctx.reply(
                    ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot), **del_kwargs
                )
            elif result == PunishmentResult.NOT_ALLOWED:
                return await ctx.reply(
                    ephemeral=True, embed=mod_embeds.not_allowed(self.bot, member), **del_kwargs
                )
            elif result == PunishmentResult.ALREADY_PUNISHING:
                return await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.already_punishing(self.bot, member),
                    **del_kwargs,
                )

    @commands.hybrid_command(
        name="mute",
        aliases=["timeout"],
        description="Mute a member for a specified duration.",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member to mute.",
        duration="Optional: the duration of the mute (e.g., 10m, 1h, 2h30m).",
        reason="Optional: the reason for the mute.",
    )
    @commands.cooldown(1, 5)
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

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        del_kwargs: dict[str, Any] = (
            {"delete_after": 5.0}
            if config and config.moderation_settings.delete_confirmation
            else {}
        )

        async with defer(ctx, stop_only=True):
            result, case, dm_success, dm_error = await self._mute_member(
                ctx, member, duration, reason
            )

            if (
                result == PunishmentResult.SUCCESS
                and (dm_success is not None)
                and (dm_error is not None)
            ):
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
                    **del_kwargs,
                )
            elif result == PunishmentResult.NOT_IN_GUILD:
                await ctx.reply(ephemeral=True, embed=not_in_guild(self.bot, member), **del_kwargs)
            elif result == PunishmentResult.CANT_MOD_SELF:
                await ctx.reply(
                    ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot), **del_kwargs
                )
            elif result == PunishmentResult.NOT_ALLOWED:
                return await ctx.reply(
                    ephemeral=True, embed=mod_embeds.not_allowed(self.bot, member), **del_kwargs
                )
            elif result == PunishmentResult.BOT_NOT_ALLOWED:
                return await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.titanium_not_allowed(self.bot, member),
                    **del_kwargs,
                )
            elif result == PunishmentResult.ALREADY_PUNISHED:
                return await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.already_muted(self.bot, member),
                    **del_kwargs,
                )
            elif result == PunishmentResult.ALREADY_PUNISHING:
                return await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.already_punishing(self.bot, member),
                    **del_kwargs,
                )
            elif result == PunishmentResult.FORBIDDEN:
                return await ctx.reply(
                    ephemeral=True, embed=mod_embeds.forbidden(self.bot, member), **del_kwargs
                )
            elif result == PunishmentResult.UNKNOWN:
                return await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.http_exception(self.bot, member),
                    **del_kwargs,
                )

    @commands.hybrid_command(
        name="unmute",
        aliases=["untimeout"],
        description="Unmute a member.",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.describe(member="The member to unmute.")
    @commands.cooldown(1, 5)
    async def unmute(
        self,
        ctx: commands.Context["TitaniumBot"],
        member: discord.Member,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        del_kwargs: dict[str, Any] = (
            {"delete_after": 5.0}
            if config and config.moderation_settings.delete_confirmation
            else {}
        )

        async with defer(ctx, stop_only=True):
            try:
                # Check if guild for type checking
                if not ctx.guild:
                    return

                # Check if member is in guild
                if member.guild.id != ctx.guild.id:
                    return await ctx.reply(
                        ephemeral=True, embed=not_in_guild(self.bot, member), **del_kwargs
                    )

                # Check if moderating self
                if member.id == ctx.author.id:
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot), **del_kwargs
                    )

                # Check if target doesn't have higher role
                if not self._hierarchy_check(member, ctx.author, ctx):
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.not_allowed(self.bot, member), **del_kwargs
                    )

                # Check if Titanium can punish target
                if not self._bot_perms_check(member, ctx):
                    return await ctx.reply(
                        ephemeral=True,
                        embed=mod_embeds.titanium_not_allowed(self.bot, member),
                        **del_kwargs,
                    )

                # Check if user is not muted
                if not member.is_timed_out():
                    return await ctx.reply(
                        ephemeral=True,
                        embed=mod_embeds.already_unmuted(self.bot, member),
                        **del_kwargs,
                    )

                # Check if member is already being punished
                if (
                    ctx.guild.id in self.bot.punishing
                    and member.id in self.bot.punishing[ctx.guild.id]
                ):
                    return await ctx.reply(
                        ephemeral=True,
                        embed=mod_embeds.already_punishing(self.bot, member),
                        **del_kwargs,
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
                        ephemeral=True, embed=mod_embeds.forbidden(self.bot, member), **del_kwargs
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
                        ephemeral=True,
                        embed=mod_embeds.http_exception(self.bot, member),
                        **del_kwargs,
                    )

                # Get last ummute case
                async with get_session() as session:
                    manager = GuildModCaseManager(self.bot, ctx.guild, session)
                    cases = await manager.get_cases_by_user(member.id)

                    case = next((c for c in cases if c.type == CaseType.MUTE), None)

                    if case:
                        # Close case
                        case, dm_success, dm_error = await manager.close_case(case.id)
                    else:
                        # Just send DM
                        embed = unmuted_dm(self.bot, member)
                        dm_success, dm_error = await send_dm(
                            bot=self.bot,
                            embed=embed,
                            user=member,
                            source_guild=ctx.guild,
                            module="Moderation",
                        )

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
                    **del_kwargs,
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
    @commands.bot_has_permissions(kick_members=True)
    @app_commands.describe(
        member="The member to kick.", reason="Optional: the reason for the kick."
    )
    @commands.cooldown(1, 5)
    async def kick(
        self,
        ctx: commands.Context["TitaniumBot"],
        member: discord.Member,
        *,
        reason: str = "",
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        del_kwargs: dict[str, Any] = (
            {"delete_after": 5.0}
            if config and config.moderation_settings.delete_confirmation
            else {}
        )

        async with defer(ctx, stop_only=True):
            result, case, dm_success, dm_error = await self._kick_member(ctx, member, reason)

            if (
                result == PunishmentResult.SUCCESS
                and (dm_success is not None)
                and (dm_error is not None)
            ):
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
                    **del_kwargs,
                )
            elif result == PunishmentResult.NOT_IN_GUILD:
                await ctx.reply(ephemeral=True, embed=not_in_guild(self.bot, member), **del_kwargs)
            elif result == PunishmentResult.CANT_MOD_SELF:
                await ctx.reply(
                    ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot), **del_kwargs
                )
            elif result == PunishmentResult.NOT_ALLOWED:
                await ctx.reply(
                    ephemeral=True, embed=mod_embeds.not_allowed(self.bot, member), **del_kwargs
                )
            elif result == PunishmentResult.BOT_NOT_ALLOWED:
                await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.titanium_not_allowed(self.bot, member),
                    **del_kwargs,
                )
            elif result == PunishmentResult.ALREADY_PUNISHING:
                await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.already_punishing(self.bot, member),
                    **del_kwargs,
                )
            elif result == PunishmentResult.FORBIDDEN:
                await ctx.reply(
                    ephemeral=True, embed=mod_embeds.forbidden(self.bot, member), **del_kwargs
                )
            elif result == PunishmentResult.UNKNOWN:
                await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.http_exception(self.bot, member),
                    **del_kwargs,
                )

    @commands.hybrid_command(name="ban", description="Ban a user from the server.")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(
        user="The user to ban.",
        duration="Optional: the duration of the ban (e.g., 10m, 1h, 2h30m).",
        reason="Optional: the reason for the ban.",
    )
    @commands.cooldown(1, 5)
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

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        del_kwargs: dict[str, Any] = (
            {"delete_after": 5.0}
            if config and config.moderation_settings.delete_confirmation
            else {}
        )

        async with defer(ctx, stop_only=True):
            result, case, dm_success, dm_error = await self._ban_member(ctx, user, duration, reason)

            if (
                result == PunishmentResult.SUCCESS
                and (dm_success is not None)
                and (dm_error is not None)
            ):
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
                    **del_kwargs,
                )
            elif result == PunishmentResult.NOT_IN_GUILD:
                await ctx.reply(ephemeral=True, embed=not_in_guild(self.bot, user), **del_kwargs)
            elif result == PunishmentResult.CANT_MOD_SELF:
                await ctx.reply(
                    ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot), **del_kwargs
                )
            elif result == PunishmentResult.NOT_ALLOWED:
                return await ctx.reply(
                    ephemeral=True, embed=mod_embeds.not_allowed(self.bot, user), **del_kwargs
                )
            elif result == PunishmentResult.BOT_NOT_ALLOWED:
                return await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.titanium_not_allowed(self.bot, user),
                    **del_kwargs,
                )
            elif result == PunishmentResult.ALREADY_PUNISHED:
                return await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.already_muted(self.bot, user),
                    **del_kwargs,
                )
            elif result == PunishmentResult.ALREADY_PUNISHING:
                return await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.already_punishing(self.bot, user),
                    **del_kwargs,
                )
            elif result == PunishmentResult.FORBIDDEN:
                return await ctx.reply(
                    ephemeral=True, embed=mod_embeds.forbidden(self.bot, user), **del_kwargs
                )
            elif result == PunishmentResult.UNKNOWN:
                return await ctx.reply(
                    ephemeral=True,
                    embed=mod_embeds.http_exception(self.bot, user),
                    **del_kwargs,
                )

    @commands.hybrid_command(name="unban", description="Unban a user from the server.")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(user="The user to unban.")
    @commands.cooldown(1, 5)
    async def unban(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: discord.User,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        del_kwargs: dict[str, Any] = (
            {"delete_after": 5.0}
            if config and config.moderation_settings.delete_confirmation
            else {}
        )

        async with defer(ctx, stop_only=True):
            try:
                # Check if guild for type checking
                if not ctx.guild:
                    return

                # Check if moderating self
                if user.id == ctx.author.id:
                    return await ctx.reply(
                        ephemeral=True, embed=mod_embeds.cant_mod_self(self.bot), **del_kwargs
                    )

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
                        ephemeral=True,
                        embed=mod_embeds.already_unbanned(self.bot, user),
                        **del_kwargs,
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
                        ephemeral=True, embed=mod_embeds.forbidden(self.bot, user), **del_kwargs
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
                        ephemeral=True,
                        embed=mod_embeds.http_exception(self.bot, user),
                        **del_kwargs,
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
                    ),
                    **del_kwargs,
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
        description="Purge up to 300 messages up to 14 days old from a channel.",
        aliases=["clear", "clean", "scrub"],
    )
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @app_commands.describe(
        amount="The number of messages to purge (max 300).",
        user="Optional: the user whose messages should be purged.",
        bot_only="Optional: whether to delete messages from bots only. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def purge(
        self,
        ctx: commands.Context["TitaniumBot"],
        amount: commands.Range[int, 1, 300],
        user: discord.User | None = None,
        bot_only: bool = False,
    ) -> None | Message:
        if not ctx.guild or not self.bot.user:
            return

        config = await self.bot.fetch_guild_config(ctx.guild.id)
        del_kwargs: dict[str, Any] = (
            {"delete_after": 5.0}
            if config and config.moderation_settings.delete_confirmation
            else {}
        )

        async with defer(ctx, stop_only=True):
            try:
                if isinstance(
                    ctx.channel,
                    (discord.PartialMessageable, discord.DMChannel, discord.GroupChannel),
                ):
                    await ctx.reply(
                        ephemeral=True, embed=mod_embeds.cannot_purge(self.bot), **del_kwargs
                    )
                    return

                limit = amount if ctx.interaction else amount + 1

                deleted = await ctx.channel.purge(
                    limit=limit,
                    bulk=True,
                    reason=f"Purged by @{ctx.author.name}",
                    check=lambda m: self._purge_check(m, ctx.message.id, user, bot_only),
                )

                if len(deleted) == 0:
                    await ctx.reply(
                        ephemeral=True,
                        embed=mod_embeds.none_to_purge(self.bot, ctx.author),
                        **del_kwargs,
                    )
                else:
                    await ctx.reply(
                        ephemeral=True,
                        embed=mod_embeds.purged(self.bot, ctx.author, len(deleted)),
                        **del_kwargs,
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
                    ephemeral=True, embed=mod_embeds.forbidden(self.bot), **del_kwargs
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
                    ephemeral=True,
                    embed=mod_embeds.http_exception(self.bot),
                    **del_kwargs,
                )

    ### MASS PUNISHMENTS ###
    @commands.hybrid_command(
        name="masswarn",
        aliases=["mass-warn", "bulkwarn", "bulk-warn"],
        description="Warn members for a specified reason.",
    )
    @commands.check_any(
        commands.has_permissions(kick_members=True),
        commands.has_permissions(ban_members=True),
        commands.has_permissions(moderate_members=True),
    )
    @app_commands.describe(
        member1="The first member to warn.",
        member2="The second member to warn.",
        member3="The third member to warn.",
        member4="The fourth member to warn.",
        member5="The fifth member to warn.",
        reason="Optional: the reason for the warning.",
    )
    @commands.cooldown(1, 5)
    async def masswarn(
        self,
        ctx: commands.Context["TitaniumBot"],
        member1: discord.Member,
        member2: discord.Member,
        member3: Optional[discord.Member] = None,
        member4: Optional[discord.Member] = None,
        member5: Optional[discord.Member] = None,
        *,
        reason: str = "",
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        async with defer(ctx, stop_only=True):
            successful_warns: list[tuple[discord.Member, str]] = []
            failed_warns: list[tuple[discord.Member, str]] = []

            raw_users = {u for u in (member1, member2, member3, member4, member5) if u}
            valid_users: set[discord.Member] = set([user for user in raw_users if user is not None])

            config = await self.bot.fetch_guild_config(ctx.guild.id)
            del_kwargs: dict[str, Any] = (
                {"delete_after": 5.0}
                if config and config.moderation_settings.delete_confirmation
                else {}
            )

            if not valid_users:
                embed = mod_embeds.mass_warned(
                    self.bot, successful_warns, failed_warns, ctx.author, reason
                )
                return await ctx.reply(ephemeral=True, embed=embed, **del_kwargs)

            for user in valid_users:
                status, _, dm_success, dm_error = await self._warn_member(
                    ctx=ctx, member=user, reason=reason
                )

                if status == PunishmentResult.SUCCESS:
                    successful_warns.append(
                        (user, dm_error or "DM Error" if not dm_success else "")
                    )
                elif status == PunishmentResult.NOT_IN_GUILD:
                    failed_warns.append((user, "Not in guild"))
                elif status == PunishmentResult.CANT_MOD_SELF:
                    failed_warns.append((user, "Can't moderate yourself"))
                elif status == PunishmentResult.NOT_ALLOWED:
                    failed_warns.append((user, "You aren't allowed to warn this user"))
                elif status == PunishmentResult.BOT_NOT_ALLOWED:
                    failed_warns.append((user, "Titanium isn't allowed to warn this user"))
                elif status == PunishmentResult.ALREADY_PUNISHING:
                    failed_warns.append((user, "User is already being punished"))

            embed = mod_embeds.mass_warned(
                bot=self.bot,
                successful_users=successful_warns,
                failed_users=failed_warns,
                creator=ctx.author,
                reason=reason,
            )
            await ctx.reply(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="massmute",
        aliases=[
            "masstimeout",
            "mass-timeout",
            "bulktimeout",
            "bulk-timeout",
            "bulkmute",
            "bulk-mute",
        ],
        description="Mute members for a specified duration.",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.describe(
        member1="The first member to mute.",
        member2="The second member to mute.",
        member3="The third member to mute.",
        member4="The fourth member to mute.",
        member5="The fifth member to mute.",
        duration="Optional: the duration of the mute (e.g., 10m, 1h, 2h30m).",
        reason="Optional: the reason for the mute.",
    )
    @commands.cooldown(1, 5)
    async def massmute(
        self,
        ctx: commands.Context["TitaniumBot"],
        member1: discord.Member,
        member2: discord.Member,
        member3: Optional[discord.Member] = None,
        member4: Optional[discord.Member] = None,
        member5: Optional[discord.Member] = None,
        duration: str = "",
        *,
        reason: str = "",
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        async with defer(ctx, stop_only=True):
            successful_mutes: list[tuple[discord.Member, str]] = []
            failed_mutes: list[tuple[discord.Member, str]] = []

            raw_users = {u for u in (member1, member2, member3, member4, member5) if u}
            valid_users: set[discord.Member] = set([user for user in raw_users if user is not None])

            config = await self.bot.fetch_guild_config(ctx.guild.id)
            del_kwargs: dict[str, Any] = (
                {"delete_after": 5.0}
                if config and config.moderation_settings.delete_confirmation
                else {}
            )

            # Process duration
            processed_duration = await DurationConverter().convert(ctx, duration)
            processed_reason = reason

            if not ctx.interaction and processed_duration is None:
                processed_reason = duration + " " + reason if reason else duration

            if not valid_users:
                embed = mod_embeds.mass_muted(
                    self.bot,
                    successful_mutes,
                    failed_mutes,
                    ctx.author,
                    processed_reason,
                    processed_duration,
                )
                return await ctx.reply(ephemeral=True, embed=embed, **del_kwargs)

            for user in valid_users:
                status, _, dm_success, dm_error = await self._mute_member(
                    ctx=ctx, member=user, duration=duration, reason=reason
                )

                if status == PunishmentResult.SUCCESS:
                    successful_mutes.append(
                        (user, dm_error or "DM Error" if not dm_success else "")
                    )
                elif status == PunishmentResult.NOT_IN_GUILD:
                    failed_mutes.append((user, "Not in guild"))
                elif status == PunishmentResult.CANT_MOD_SELF:
                    failed_mutes.append((user, "Can't moderate yourself"))
                elif status == PunishmentResult.NOT_ALLOWED:
                    failed_mutes.append((user, "You aren't allowed to mute this user"))
                elif status == PunishmentResult.BOT_NOT_ALLOWED:
                    failed_mutes.append((user, "Titanium isn't allowed to mute this user"))
                elif status == PunishmentResult.ALREADY_PUNISHING:
                    failed_mutes.append((user, "User is already being punished"))
                elif status == PunishmentResult.ALREADY_PUNISHED:
                    failed_mutes.append((user, "User is already muted"))
                elif status == PunishmentResult.FORBIDDEN:
                    failed_mutes.append((user, "Forbidden when trying to mute user"))
                elif status == PunishmentResult.UNKNOWN:
                    failed_mutes.append((user, "Unknown Discord error when trying to mute user"))

            embed = mod_embeds.mass_muted(
                bot=self.bot,
                successful_users=successful_mutes,
                failed_users=failed_mutes,
                creator=ctx.author,
                reason=processed_reason,
                duration=processed_duration,
            )
            await ctx.reply(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="masskick",
        aliases=["mass-kick", "bulkkick", "bulk-kick"],
        description="Kick members from the server.",
    )
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @app_commands.describe(
        member1="The first member to kick.",
        member2="The second member to kick.",
        member3="The third member to kick.",
        member4="The fourth member to kick.",
        member5="The fifth member to kick.",
        reason="Optional: the reason for the kick.",
    )
    @commands.cooldown(1, 5)
    async def masskick(
        self,
        ctx: commands.Context["TitaniumBot"],
        member1: discord.Member,
        member2: discord.Member,
        member3: Optional[discord.Member] = None,
        member4: Optional[discord.Member] = None,
        member5: Optional[discord.Member] = None,
        *,
        reason: str = "",
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        async with defer(ctx, stop_only=True):
            successful_kicks: list[tuple[discord.Member, str]] = []
            failed_kicks: list[tuple[discord.Member, str]] = []

            raw_users = {u for u in (member1, member2, member3, member4, member5) if u}
            valid_users: set[discord.Member] = set([user for user in raw_users if user is not None])

            config = await self.bot.fetch_guild_config(ctx.guild.id)
            del_kwargs: dict[str, Any] = (
                {"delete_after": 5.0}
                if config and config.moderation_settings.delete_confirmation
                else {}
            )

            if not valid_users:
                embed = mod_embeds.mass_kicked(
                    self.bot, successful_kicks, failed_kicks, ctx.author, reason
                )
                return await ctx.reply(ephemeral=True, embed=embed, **del_kwargs)

            for user in valid_users:
                status, _, dm_success, dm_error = await self._kick_member(
                    ctx=ctx, member=user, reason=reason
                )

                if status == PunishmentResult.SUCCESS:
                    successful_kicks.append(
                        (user, dm_error or "DM Error" if not dm_success else "")
                    )
                elif status == PunishmentResult.NOT_IN_GUILD:
                    failed_kicks.append((user, "Not in guild"))
                elif status == PunishmentResult.CANT_MOD_SELF:
                    failed_kicks.append((user, "Can't moderate yourself"))
                elif status == PunishmentResult.NOT_ALLOWED:
                    failed_kicks.append((user, "You aren't allowed to kick this user"))
                elif status == PunishmentResult.BOT_NOT_ALLOWED:
                    failed_kicks.append((user, "Titanium isn't allowed to kick this user"))
                elif status == PunishmentResult.ALREADY_PUNISHING:
                    failed_kicks.append((user, "User is already being punished"))
                elif status == PunishmentResult.FORBIDDEN:
                    failed_kicks.append((user, "Forbidden when trying to kick user"))
                elif status == PunishmentResult.UNKNOWN:
                    failed_kicks.append((user, "Unknown Discord error when trying to kick user"))

            embed = mod_embeds.mass_kicked(
                bot=self.bot,
                successful_users=successful_kicks,
                failed_users=failed_kicks,
                creator=ctx.author,
                reason=reason,
            )
            await ctx.reply(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="massban",
        aliases=["mass-ban", "bulkban", "bulk-ban"],
        description="Ban users from the server.",
    )
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True, manage_guild=True)
    @app_commands.describe(
        duration="Optional: the duration of the ban (e.g., 10m, 1h, 2h30m).",
        reason="Optional: the reason for the ban.",
    )
    @commands.cooldown(1, 5)
    async def massban(
        self,
        ctx: commands.Context["TitaniumBot"],
        user1: discord.User,
        user2: discord.User,
        user3: Optional[discord.User] = None,
        user4: Optional[discord.User] = None,
        user5: Optional[discord.User] = None,
        user6: Optional[discord.User] = None,
        user7: Optional[discord.User] = None,
        user8: Optional[discord.User] = None,
        user9: Optional[discord.User] = None,
        user10: Optional[discord.User] = None,
        user11: Optional[discord.User] = None,
        user12: Optional[discord.User] = None,
        user13: Optional[discord.User] = None,
        user14: Optional[discord.User] = None,
        user15: Optional[discord.User] = None,
        user16: Optional[discord.User] = None,
        user17: Optional[discord.User] = None,
        user18: Optional[discord.User] = None,
        user19: Optional[discord.User] = None,
        user20: Optional[discord.User] = None,
        duration: str = "",
        *,
        reason: str = "",
    ) -> None | Message:
        if not ctx.guild or not self.bot.user or not isinstance(ctx.author, discord.Member):
            return

        async with defer(ctx, stop_only=True):
            # Check if guild for type checking
            if not ctx.guild:
                return

            successful_bans: list[tuple[discord.User | discord.Member | discord.Object, str]] = []
            failed_bans: list[tuple[discord.User | discord.Member | discord.Object, str]] = []

            # fmt: off
            raw_users = {
                u for u in (user1, user2, user3, user4, user5, user6, user7, user8, user9, user10, 
                            user11, user12, user13, user14, user15, user16, user17, user18, user19, user20) if u
            }
            # fmt: on

            valid_users: set[discord.User] = set()
            for user in raw_users:
                if user.id == ctx.author.id:
                    failed_bans.append((user, "Can't moderate yourself"))
                    continue

                member = await get_or_fetch_member(self.bot, ctx.guild, user.id)

                if isinstance(member, discord.Member):
                    if not self._hierarchy_check(member, ctx.author, ctx):
                        failed_bans.append((user, "You cannot ban this user"))
                        continue
                    if not self._bot_perms_check(member, ctx):
                        failed_bans.append((user, "Titanium cannot ban this user"))
                        continue

                valid_users.add(user)

            config = await self.bot.fetch_guild_config(ctx.guild.id)
            del_kwargs: dict[str, Any] = (
                {"delete_after": 5.0}
                if config and config.moderation_settings.delete_confirmation
                else {}
            )

            # Process duration
            processed_duration = await DurationConverter().convert(ctx, duration)
            processed_reason = reason

            if not ctx.interaction and processed_duration is None:
                processed_reason = duration + " " + reason if reason else duration

            if not valid_users:
                embed = mod_embeds.mass_banned(
                    self.bot,
                    successful_bans,
                    failed_bans,
                    ctx.author,
                    processed_reason,
                    processed_duration,
                )
                return await ctx.reply(ephemeral=True, embed=embed, **del_kwargs)

            cases: dict[int, tuple[ModCase, bool, str]] = {}
            async with get_session() as session:
                manager = GuildModCaseManager(self.bot, ctx.guild, session)

                try:
                    for user in valid_users:
                        case, dm_success, dm_error = await manager.create_case(
                            action=CaseType.BAN,
                            user=user,
                            creator_user=ctx.author,
                            reason=processed_reason,
                            duration=processed_duration,
                        )
                        cases[user.id] = (case, dm_success, dm_error)

                    ban_result = await ctx.guild.bulk_ban(
                        users=valid_users,
                        reason=f"@{ctx.author.name}: {processed_reason}",
                        delete_message_seconds=config.moderation_settings.ban_days * 86400
                        if config
                        else 0,
                    )

                    for fail in ban_result.failed:
                        failed_bans.append(
                            (
                                next((user for user in valid_users if user.id == fail.id), fail),
                                "Failed to ban user",
                            )
                        )
                        if fail.id in cases:
                            await manager.delete_case(cases[fail.id][0].id, raise_not_found=False)

                    for success in ban_result.banned:
                        successful_bans.append(
                            (
                                next(
                                    (user for user in valid_users if user.id == success.id),
                                    success,
                                ),
                                (cases[success.id][2] or "DM Error")
                                if success.id in cases and not cases[success.id][1]
                                else "",
                            )
                        )

                    embed = mod_embeds.mass_banned(
                        self.bot,
                        successful_bans,
                        failed_bans,
                        ctx.author,
                        processed_reason,
                        processed_duration,
                    )
                    return await ctx.reply(ephemeral=True, embed=embed, **del_kwargs)
                except (discord.Forbidden, discord.HTTPException) as e:
                    error_msg = (
                        "Titanium was not allowed to massban members"
                        if isinstance(e, discord.Forbidden)
                        else "Unknown Discord error while massbanning members"
                    )

                    await log_error(
                        bot=self.bot,
                        module="Moderation",
                        guild_id=ctx.guild.id,
                        error=error_msg,
                        details=e.text,
                    )

                    for case, _, _ in cases.values():
                        await manager.delete_case(case.id, raise_not_found=False)

                    embed = (
                        mod_embeds.forbidden(self.bot)
                        if isinstance(e, discord.Forbidden)
                        else mod_embeds.http_exception(self.bot)
                    )
                    return await ctx.reply(ephemeral=True, embed=embed, **del_kwargs)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ModerationBasicCog(bot))
