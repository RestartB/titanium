import discord
from discord.ext import commands

from ...lib.duration import DurationConverter
from ...lib.embeds.mod_actions import (
    already_punishing,
    banned,
    kicked,
    muted,
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
            return await reply(embed=not_in_guild(member), ephemeral=True)

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(embed=already_punishing(member), ephemeral=True)

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        # Create case logic here

        # Send confirmation message
        embed = warned(member, reason, duration)
        await reply(embed=embed, ephemeral=True)

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
            return await reply(embed=not_in_guild(member), ephemeral=True)

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(embed=already_punishing(member), ephemeral=True)

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        # Create case logic here

        # Send confirmation message
        embed = muted(member, reason, duration)
        await reply(embed=embed, ephemeral=True)

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
            return await reply(embed=not_in_guild(member), ephemeral=True)

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(embed=already_punishing(member), ephemeral=True)

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        # Create case logic here

        # Send confirmation message
        embed = kicked(member, reason)
        await reply(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="ban")
    async def ban(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        duration: DurationConverter,
        reason: str,
    ) -> None:
        await defer(ctx)

        # Check if member is in guild
        if member.guild.id != ctx.guild.id:
            return await reply(embed=not_in_guild(member), ephemeral=True)

        # Check if member is already being punished
        if (
            ctx.guild.id in self.bot.punishing
            and member.id in self.bot.punishing[ctx.guild.id]
        ):
            return await reply(embed=already_punishing(member), ephemeral=True)

        # Add member to punishing list
        self.bot.punishing.setdefault(ctx.guild.id, []).append(member.id)

        # Create case logic here

        # Send confirmation message
        embed = banned(member, reason, duration)
        await reply(embed=embed, ephemeral=True)
