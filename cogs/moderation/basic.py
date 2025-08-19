from datetime import timedelta
from typing import TYPE_CHECKING, Annotated

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View

from lib.cases.case_manager import GuildModCaseManager
from lib.duration import DurationConverter
from lib.embeds.dm_notifs import (
    banned_dm,
    jump_button,
    kicked_dm,
    muted_dm,
    unbanned_dm,
    unmuted_dm,
    warned_dm,
)
from lib.embeds.general import not_in_guild
from lib.embeds.mod_actions import (
    already_banned,
    already_muted,
    already_punishing,
    already_unmuted,
    banned,
    forbidden,
    http_exception,
    kicked,
    muted,
    unbanned,
    unmuted,
    warned,
)
from lib.hybrid_adapters import defer, stop_loading
from lib.sql import get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ModerationBasicCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="warn", description="Warn a member for a specified reason."
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        member="The member to warn.", reason="The reason for the warning."
    )
    async def warn(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        *,
        reason: str = "",
    ) -> None:
        await defer(self.bot, ctx)

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await ctx.reply(embed=not_in_guild(self.bot, member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await ctx.reply(embed=already_punishing(self.bot, member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        try:
            # Create case
            async with get_session() as session:
                manager = GuildModCaseManager(ctx.guild, session)

                case = await manager.create_case(
                    type="warn",
                    user_id=member.id,
                    creator_user_id=ctx.author.id,
                    reason=reason,
                )

            # Send DM
            dm_success = True
            dm_error = ""

            try:
                await member.send(
                    embed=warned_dm(self.bot, ctx, case),
                    view=View().add_item(jump_button(ctx)),
                )
            except discord.Forbidden:
                dm_success = False
                dm_error = "User has DMs disabled."
            except discord.HTTPException:
                dm_success = False
                dm_error = "Failed to send DM."

            # Send confirmation message
            await ctx.reply(
                embed=warned(
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
            if ctx.guild.id in self.bot.punishing:
                self.bot.punishing[ctx.guild.id].remove(member.id)

            await stop_loading(self.bot, ctx)

    @commands.hybrid_command(
        name="mute",
        alias=["timeout"],
        description="Mute a member for a specified duration.",
    )
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member to mute.",
        duration="The duration of the mute (e.g., 10m, 1h, 2h30m).",
        reason="The reason for the mute.",
    )
    async def mute(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        duration: Annotated[timedelta, DurationConverter],
        *,
        reason: str = "",
    ) -> None:
        await defer(self.bot, ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await ctx.reply(embed=not_in_guild(self.bot, member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await ctx.reply(embed=already_punishing(self.bot, member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        try:
            if ctx.interaction:
                processed_reason = reason
                processed_duration = duration
            else:
                # Process duration
                try:
                    processed_duration = await DurationConverter().convert(
                        ctx, duration
                    )
                except commands.BadArgument:
                    processed_duration = timedelta(seconds=0)
                    processed_reason = duration + " " + reason if reason else duration

            # Check if user is already timed out
            if member.is_timed_out():
                return await ctx.reply(embed=already_muted(self.bot, member))

            # Time out user
            try:
                await member.timeout(
                    processed_duration, reason=f"@{ctx.author.name}: {processed_reason}"
                )
            except discord.Forbidden:
                return await ctx.reply(embed=forbidden(self.bot, member))
            except discord.HTTPException:
                return await ctx.reply(embed=http_exception(self.bot, member))

            # Create case
            async with get_session() as session:
                manager = GuildModCaseManager(ctx.guild, session)

                case = await manager.create_case(
                    type="mute",
                    user_id=member.id,
                    creator_user_id=ctx.author.id,
                    reason=processed_reason,
                    duration=processed_duration,
                )

            # Send DM
            dm_success = True
            dm_error = ""

            try:
                await member.send(
                    embed=muted_dm(self.bot, ctx, case),
                    view=View().add_item(jump_button(ctx)),
                )
            except discord.Forbidden:
                dm_success = False
                dm_error = "User has DMs disabled."
            except discord.HTTPException:
                dm_success = False
                dm_error = "Failed to send DM."

            # Send confirmation message
            await ctx.reply(
                embed=muted(
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
            if ctx.guild.id in self.bot.punishing:
                self.bot.punishing[ctx.guild.id].remove(member.id)

            await stop_loading(self.bot, ctx)

    @commands.hybrid_command(
        name="unmute", alias=["untimeout"], description="Unmute a member."
    )
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="The member to unmute.")
    async def unmute(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
    ) -> None:
        await defer(self.bot, ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await ctx.reply(embed=not_in_guild(self.bot, member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await ctx.reply(embed=already_punishing(self.bot, member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        try:
            # Check if user is not muted
            if not member.is_timed_out():
                return await ctx.reply(embed=already_unmuted(self.bot, member))

            # Unmute user
            try:
                await member.timeout(None, reason=f"Unmuted by @{ctx.author.name}")
            except discord.Forbidden:
                return await ctx.reply(embed=forbidden(self.bot, member))
            except discord.HTTPException:
                return await ctx.reply(embed=http_exception(self.bot, member))

            # Get last ummute case
            async with get_session() as session:
                manager = GuildModCaseManager(ctx.guild, session)
                cases = await manager.get_cases_by_user(member.id)

                case = next((c for c in cases if str(c.type) == "mute"), None)

                if not case:
                    return

                # Close case
                case = await manager.close_case(case.id)

            # Send DM
            dm_success = True
            dm_error = ""

            try:
                await member.send(
                    embed=unmuted_dm(self.bot, ctx, case),
                    view=View().add_item(jump_button(ctx)),
                )
            except discord.Forbidden:
                dm_success = False
                dm_error = "User has DMs disabled."
            except discord.HTTPException:
                dm_success = False
                dm_error = "Failed to send DM."

            # Send confirmation message
            await ctx.reply(
                embed=unmuted(
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
            if ctx.guild.id in self.bot.punishing:
                self.bot.punishing[ctx.guild.id].remove(member.id)

            await stop_loading(self.bot, ctx)

    @commands.hybrid_command(name="kick", description="Kick a member from the server.")
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @app_commands.default_permissions(kick_members=True)
    @app_commands.describe(
        member="The member to kick.", reason="The reason for the kick."
    )
    async def kick(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        *,
        reason: str = "",
    ) -> None:
        await defer(self.bot, ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await ctx.reply(embed=not_in_guild(self.bot, member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await ctx.reply(embed=already_punishing(self.bot, member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        try:
            # Kick user
            try:
                await member.kick(reason=f"@{ctx.author.name}: {reason}")
            except discord.Forbidden:
                return await ctx.reply(embed=forbidden(self.bot, member))
            except discord.HTTPException:
                return await ctx.reply(embed=http_exception(self.bot, member))

            # Create case
            async with get_session() as session:
                manager = GuildModCaseManager(ctx.guild, session)

                case = await manager.create_case(
                    type="kick",
                    user_id=member.id,
                    creator_user_id=ctx.author.id,
                    reason=reason,
                )

            # Send DM
            dm_success = True
            dm_error = ""

            try:
                await member.send(
                    embed=kicked_dm(self.bot, ctx, case),
                    view=View().add_item(jump_button(ctx)),
                )
            except discord.Forbidden:
                dm_success = False
                dm_error = "User has DMs disabled."
            except discord.HTTPException:
                dm_success = False
                dm_error = "Failed to send DM."

            # Send confirmation message
            await ctx.reply(
                embed=kicked(
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
            if ctx.guild.id in self.bot.punishing:
                self.bot.punishing[ctx.guild.id].remove(member.id)

            await stop_loading(self.bot, ctx)

    @commands.hybrid_command(name="ban", description="Ban a user from the server.")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(
        user="The user to ban.",
        duration="The duration of the ban (e.g., 10m, 1h, 2h30m).",
        reason="The reason for the ban.",
    )
    async def ban(
        self,
        ctx: commands.Context[commands.Bot],
        user: discord.User,
        duration: str,
        *,
        reason: str = "",
    ) -> None:
        await defer(self.bot, ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and user.id in self.bot.punishing[ctx.guild.id]
        ):
            return await ctx.reply(embed=already_punishing(self.bot, user))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(user.id)

        try:
            if ctx.interaction:
                processed_reason = reason
                processed_duration = duration
            else:
                # Process duration
                try:
                    processed_duration = await DurationConverter().convert(
                        ctx, duration
                    )
                except commands.BadArgument:
                    processed_duration = timedelta(seconds=0)
                    processed_reason = duration + " " + reason if reason else duration

            # Check if user is already banned
            try:
                await ctx.guild.fetch_ban(user)
                return await ctx.reply(embed=already_banned(self.bot, user))
            except discord.NotFound:
                pass

            # Ban user
            try:
                await ctx.guild.ban(
                    user=user,
                    reason=f"@{ctx.author.name}: {processed_reason}",
                )
            except discord.Forbidden:
                return await ctx.reply(embed=forbidden(self.bot, user))
            except discord.HTTPException:
                return await ctx.reply(embed=http_exception(self.bot, user))

            # Create case
            async with get_session() as session:
                manager = GuildModCaseManager(ctx.guild, session)

                case = await manager.create_case(
                    type="ban",
                    user_id=user.id,
                    creator_user_id=ctx.author.id,
                    reason=processed_reason,
                    duration=processed_duration,
                )

            # Send DM
            dm_success = True
            dm_error = ""

            try:
                await user.send(
                    embed=banned_dm(self.bot, ctx, case),
                    view=View().add_item(jump_button(ctx)),
                )
            except discord.Forbidden:
                dm_success = False
                dm_error = "User has DMs disabled."
            except discord.HTTPException:
                dm_success = False
                dm_error = "Failed to send DM."

            # Send confirmation message
            await ctx.reply(
                embed=banned(
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
            if ctx.guild.id in self.bot.punishing:
                self.bot.punishing[ctx.guild.id].remove(user.id)

            await stop_loading(self.bot, ctx)

    @commands.hybrid_command(
        name="unban", description="Unban a member from the server."
    )
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(user="The user to unban.")
    async def unban(
        self,
        ctx: commands.Context[commands.Bot],
        user: discord.User,
    ) -> None:
        await defer(self.bot, ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if user is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and user.id in self.bot.punishing[ctx.guild.id]
        ):
            return await ctx.reply(embed=already_punishing(self.bot, user))

        # Add user to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(user.id)

        try:
            # Check if user is not banned
            try:
                await ctx.guild.fetch_ban(user)
            except discord.NotFound:
                return await ctx.reply(embed=already_banned(self.bot, user))

            # Unban user
            try:
                await ctx.guild.unban(user, reason=f"Unbanned by @{ctx.author.name}")
            except discord.Forbidden:
                return await ctx.reply(embed=forbidden(self.bot, user))
            except discord.HTTPException:
                return await ctx.reply(embed=http_exception(self.bot, user))

            # Get last ban case
            async with get_session() as session:
                manager = GuildModCaseManager(ctx.guild, session)
                cases = await manager.get_cases_by_user(user.id)

                case = next((c for c in cases if str(c.type) == "ban"), None)

                if not case:
                    return

                # Close case
                case = await manager.close_case(case.id)

            # Send DM
            dm_success = True
            dm_error = ""

            try:
                await user.send(
                    embed=unbanned_dm(self.bot, ctx, case),
                    view=View().add_item(jump_button(ctx)),
                )
            except discord.Forbidden:
                dm_success = False
                dm_error = "User has DMs disabled."
            except discord.HTTPException:
                dm_success = False
                dm_error = "Failed to send DM."

            # Send confirmation message
            await ctx.reply(
                embed=unbanned(
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
            if ctx.guild.id in self.bot.punishing:
                self.bot.punishing[ctx.guild.id].remove(user.id)

            await stop_loading(self.bot, ctx)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(ModerationBasicCog(bot))
