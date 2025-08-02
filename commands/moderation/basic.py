import discord
from discord.ext import commands

from ...lib.cases.case_manager import GuildModCaseManager
from ...lib.duration import DurationConverter
from ...lib.embeds.dm_notifs import (
    banned_dm,
    jump_button,
    kicked_dm,
    muted_dm,
    warned_dm,
)
from ...lib.embeds.mod_actions import (
    already_punishing,
    banned,
    forbidden,
    http_exception,
    kicked,
    muted,
    not_found,
    not_in_guild,
    warned,
)
from ...lib.hybrid_adapters import defer, reply
from ...main import TitaniumBot


class Misc(commands.Cog):
    def __init__(self, bot: TitaniumBot):
        self.bot = bot

    @commands.hybrid_command(name="warn")
    async def warn(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        reason: str,
    ) -> None:
        await defer(ctx)

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await reply(embed=not_in_guild(member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(embed=already_punishing(member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        # Create case
        case = await GuildModCaseManager.create_case(
            type="warn", guild_id=ctx.guild.id, user_id=member.id, reason=reason
        )

        # Send DM
        dm_success = True
        dm_error = ""

        try:
            await member.send(embed=warned_dm(ctx, case), view=jump_button(ctx))
        except discord.Forbidden:
            dm_success = False
            dm_error = "User has DMs disabled."
        except discord.HTTPException:
            dm_success = False
            dm_error = "Failed to send DM."

        # Send confirmation message
        await reply(
            embed=warned(
                user=member,
                creator=ctx.author,
                case=case,
                dm_success=dm_success,
                dm_error=dm_error,
            )
        )

    @commands.hybrid_command(name="mute")
    async def mute(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        duration: DurationConverter,
        reason: str,
    ) -> None:
        await defer(ctx)

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await reply(embed=not_in_guild(member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(embed=already_punishing(member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        # Time out user
        try:
            await member.timeout(until=duration, reason=reason)
        except discord.Forbidden:
            return await reply(embed=forbidden(member))
        except discord.HTTPException:
            return await reply(embed=http_exception(member))
        except discord.NotFound:
            return await reply(embed=not_found(member))

        # Create case
        case = await GuildModCaseManager.create_case(
            type="mute",
            guild_id=ctx.guild.id,
            user_id=member.id,
            reason=reason,
            duration=duration,
        )

        # Send DM
        dm_success = True
        dm_error = ""

        try:
            await member.send(embed=muted_dm(ctx, case), view=jump_button(ctx))
        except discord.Forbidden:
            dm_success = False
            dm_error = "User has DMs disabled."
        except discord.HTTPException:
            dm_success = False
            dm_error = "Failed to send DM."

        # Send confirmation message
        await reply(
            embed=muted(
                user=member,
                creator=ctx.author,
                case=case,
                dm_success=dm_success,
                dm_error=dm_error,
            )
        )

    @commands.hybrid_command(name="kick")
    async def kick(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        duration: DurationConverter,
        reason: str,
    ) -> None:
        await defer(ctx)

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await reply(embed=not_in_guild(member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(embed=already_punishing(member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        # Kick user
        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            return await reply(embed=forbidden(member))
        except discord.HTTPException:
            return await reply(embed=http_exception(member))
        except discord.NotFound:
            return await reply(embed=not_found(member))

        # Create case
        case = await GuildModCaseManager.create_case(
            type="kick",
            guild_id=ctx.guild.id,
            user_id=member.id,
            reason=reason,
            duration=duration,
        )

        # Send DM
        dm_success = True
        dm_error = ""

        try:
            await member.send(embed=kicked_dm(ctx, case), view=jump_button(ctx))
        except discord.Forbidden:
            dm_success = False
            dm_error = "User has DMs disabled."
        except discord.HTTPException:
            dm_success = False
            dm_error = "Failed to send DM."

        # Send confirmation message
        await reply(
            embed=kicked(
                user=member,
                creator=ctx.author,
                case=case,
                dm_success=dm_success,
                dm_error=dm_error,
            )
        )

    @commands.hybrid_command(name="ban")
    async def ban(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        duration: DurationConverter,
        reason: str,
        delete_message_days: int = 0,
    ) -> None:
        await defer(ctx)

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await reply(embed=not_in_guild(member))

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(embed=already_punishing(member))

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        # Ban user
        try:
            await member.ban(reason=reason, delete_message_days=delete_message_days)
        except discord.Forbidden:
            return await reply(embed=forbidden(member))
        except discord.HTTPException:
            return await reply(embed=http_exception(member))
        except discord.NotFound:
            return await reply(embed=not_found(member))

        # Create case
        case = await GuildModCaseManager.create_case(
            type="ban",
            guild_id=ctx.guild.id,
            user_id=member.id,
            reason=reason,
            duration=duration,
        )

        # Send DM
        dm_success = True
        dm_error = ""

        try:
            await member.send(embed=banned_dm(ctx, case), view=jump_button(ctx))
        except discord.Forbidden:
            dm_success = False
            dm_error = "User has DMs disabled."
        except discord.HTTPException:
            dm_success = False
            dm_error = "Failed to send DM."

        # Send confirmation message
        await reply(
            embed=banned(
                user=member,
                creator=ctx.author,
                case=case,
                dm_success=dm_success,
                dm_error=dm_error,
            )
        )
