from datetime import timedelta
from typing import TYPE_CHECKING, Annotated

import discord
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
    not_in_guild,
    unbanned,
    unmuted,
    warned,
)
from lib.hybrid_adapters import defer, reply
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
    async def warn(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        reason: str,
    ) -> None:
        await defer(ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await reply(ctx, embed=not_in_guild(self.bot, member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(ctx, embed=already_punishing(self.bot, member))

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
            await reply(
                ctx,
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

    @commands.hybrid_command(
        name="mute",
        alias=["timeout", "silence"],
        description="Mute a member for a specified duration.",
    )
    @commands.guild_only()
    async def mute(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        duration: Annotated[timedelta, DurationConverter],
        reason: str,
    ) -> None:
        await defer(ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await reply(ctx, embed=not_in_guild(self.bot, member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(ctx, embed=already_punishing(self.bot, member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        try:
            # Check if user is already timed out
            if member.is_timed_out():
                return await reply(ctx, embed=already_muted(self.bot, member))

            # Time out user
            try:
                await member.timeout(duration, reason=f"@{ctx.author.name}: {reason}")
            except discord.Forbidden:
                return await reply(ctx, embed=forbidden(self.bot, member))
            except discord.HTTPException:
                return await reply(ctx, embed=http_exception(self.bot, member))

            # Create case
            async with get_session() as session:
                manager = GuildModCaseManager(ctx.guild, session)

                case = await manager.create_case(
                    type="mute",
                    user_id=member.id,
                    creator_user_id=ctx.author.id,
                    reason=reason,
                    duration=duration,
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
            await reply(
                ctx,
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

    @commands.hybrid_command(name="unmute", description="Unmute a member.")
    @commands.guild_only()
    async def unmute(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
    ) -> None:
        await defer(ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await reply(ctx, embed=not_in_guild(self.bot, member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(ctx, embed=already_punishing(self.bot, member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        try:
            # Check if user is not muted
            if not member.is_timed_out():
                return await reply(ctx, embed=already_unmuted(self.bot, member))

            # Unmute user
            try:
                await member.timeout(None, reason=f"Unmuted by @{ctx.author.name}")
            except discord.Forbidden:
                return await reply(ctx, embed=forbidden(self.bot, member))
            except discord.HTTPException:
                return await reply(ctx, embed=http_exception(self.bot, member))

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
            await reply(
                ctx,
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

    @commands.hybrid_command(name="kick", description="Kick a member from the server.")
    @commands.guild_only()
    async def kick(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        reason: str,
    ) -> None:
        await defer(ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await reply(ctx, embed=not_in_guild(self.bot, member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(ctx, embed=already_punishing(self.bot, member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        try:
            # Kick user
            try:
                await member.kick(reason=f"@{ctx.author.name}: {reason}")
            except discord.Forbidden:
                return await reply(ctx, embed=forbidden(self.bot, member))
            except discord.HTTPException:
                return await reply(ctx, embed=http_exception(self.bot, member))

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
            await reply(
                ctx,
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

    @commands.hybrid_command(name="ban", description="Ban a member from the server.")
    @commands.guild_only()
    async def ban(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        duration: Annotated[timedelta, DurationConverter],
        reason: str,
        delete_message_days: int = 0,
    ) -> None:
        await defer(ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(ctx, embed=already_punishing(self.bot, member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        try:
            # Check if user is already banned
            try:
                await ctx.guild.fetch_ban(member)
                return await reply(ctx, embed=already_banned(self.bot, member))
            except discord.NotFound:
                pass

            # Ban user
            try:
                await member.ban(
                    reason=f"@{ctx.author.name}: {reason}",
                    delete_message_days=delete_message_days,
                )
            except discord.Forbidden:
                return await reply(ctx, embed=forbidden(self.bot, member))
            except discord.HTTPException:
                return await reply(ctx, embed=http_exception(self.bot, member))

            # Create case
            async with get_session() as session:
                manager = GuildModCaseManager(ctx.guild, session)

                case = await manager.create_case(
                    type="ban",
                    user_id=member.id,
                    creator_user_id=ctx.author.id,
                    reason=reason,
                    duration=duration,
                )

            # Send DM
            dm_success = True
            dm_error = ""

            try:
                await member.send(
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
            await reply(
                ctx,
                embed=banned(
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

    @commands.hybrid_command(
        name="unban", description="Unban a member from the server."
    )
    @commands.guild_only()
    async def unban(
        self,
        ctx: commands.Context[commands.Bot],
        user: discord.User,
    ) -> None:
        await defer(ctx)

        # Check if guild for type checking
        if not ctx.guild:
            return

        # Check if user is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and user.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(ctx, embed=already_punishing(self.bot, user))

        # Add user to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(user.id)

        try:
            # Check if user is not banned
            try:
                await ctx.guild.fetch_ban(user)
            except discord.NotFound:
                return await reply(ctx, embed=already_banned(self.bot, user))

            # Unban user
            try:
                await ctx.guild.unban(user, reason=f"Unbanned by @{ctx.author.name}")
            except discord.Forbidden:
                return await reply(ctx, embed=forbidden(self.bot, user))
            except discord.HTTPException:
                return await reply(ctx, embed=http_exception(self.bot, user))

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
            await reply(
                ctx,
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


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(ModerationBasicCog(bot))
