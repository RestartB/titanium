import discord
from discord.ext import commands

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

        # Create case logic here

        # Send confirmation message
        embed = warned(member, reason, duration)
        await reply(embed=embed)

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

        # Create case logic here

        # Send confirmation message
        embed = muted(member, reason, duration)
        await reply(embed=embed)

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

        # Create case logic here

        # Send confirmation message
        embed = kicked(member, reason)
        await reply(embed=embed)

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

        try:
            await member.ban(reason=reason, delete_message_days=delete_message_days)
        except discord.Forbidden:
            return await reply(embed=forbidden(member))
        except discord.HTTPException:
            return await reply(embed=http_exception(member))
        except discord.NotFound:
            return await reply(embed=not_found(member))

        # Send DM
        dm_success = True
        dm_error = ""

        try:
            dm_embed = banned_dm(ctx, member, duration)
            await member.send(embed=dm_embed, view=jump_button(ctx))
        except discord.Forbidden:
            dm_success = False
            dm_error = "User has DMs disabled."
        except discord.HTTPException:
            dm_success = False
            dm_error = "Failed to send DM."

        # Send confirmation message
        embed = banned(member, reason, duration, dm_success, dm_error)
        await reply(embed=embed)
