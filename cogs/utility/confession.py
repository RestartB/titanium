import re
from typing import TYPE_CHECKING

import discord
from discord import Colour, Embed, app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


class ConfessionCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot: "TitaniumBot" = bot

    async def cog_check(self, ctx: commands.Context["TitaniumBot"]) -> bool:
        if not ctx.guild:
            raise commands.errors.NoPrivateMessage(
                message="Confession commands only work in servers."
            )
        return True

    @commands.hybrid_group(name="confession", description="Anonymous message commands.")
    @app_commands.guild_only()
    async def confession(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.send_help(ctx)

    @confession.command(name="message", description="Share an anonymous message")
    @commands.guild_only()
    @app_commands.describe(
        message="Message of the confession.",
        anonymous="Whether it should be anonymous or not.",
    )
    async def confession_message(
        self,
        ctx: commands.Context["TitaniumBot"],
        *,
        message: str,
        anonymous: bool = True,
    ) -> None:
        await ctx.defer()

        if ctx.guild is None:
            return

        if isinstance(
            ctx.channel,
            (
                discord.ForumChannel,
                discord.abc.PrivateChannel,
                discord.CategoryChannel,
            ),
        ):
            await ctx.reply(
                embed=Embed(
                    color=Colour.red(),
                    title="Invalid Channel",
                    description="Confessions cannot be sent from this channel type. Please use a different channel.",
                ),
                ephemeral=True,
            )
            return

        guild_settings = self.bot.guild_configs.get(ctx.guild.id)
        if not guild_settings or not guild_settings.confession_enabled:
            e = Embed(
                color=Colour.red(),
                title="Confession Disabled",
                description=f"The confession seettings is disabled for the {ctx.guild.name} server. Ask a server admin to turn it on using `/settings confession` command.",
            )
            await ctx.reply(embed=e)
            return

        channel = self.bot.get_channel(
            guild_settings.confession_settings.confession_channel_id
        )
        if not channel:
            embed = Embed(
                color=Colour.red(),
                title="Confession Channel Not Found",
                description=(
                    "The confession channel is not set or could not be found. Ask a server admin to configure it using `/settings confession` command."
                ),
            )
            await ctx.reply(embed=embed)
            return

        if isinstance(
            channel,
            (
                discord.ForumChannel,
                discord.abc.PrivateChannel,
                discord.CategoryChannel,
            ),
        ):
            await ctx.reply(
                embed=Embed(
                    color=Colour.red(),
                    title="Invalid Channel",
                    description="Titanium can't send to the configured confession channel. Please ask a server admin to set a valid channel using `/settings confession` command.",
                ),
                ephemeral=True,
            )
            return

        author_text = "Anonymous" if anonymous else f"{ctx.author.display_name}"
        confession_embed = Embed(
            title="New Confession",
            description=message,
            color=Colour.blue(),
        )
        confession_embed.set_footer(
            text=f"Sent by {author_text}",
            icon_url=None if anonymous else ctx.author.display_avatar,
        )
        conf_msg = await channel.send(embed=confession_embed)

        log_channel = self.bot.get_channel(
            guild_settings.confession_settings.confession_log_channel_id
        )

        if log_channel:
            if not isinstance(
                log_channel,
                (
                    discord.ForumChannel,
                    discord.abc.PrivateChannel,
                    discord.CategoryChannel,
                ),
            ):
                log_embed = Embed(
                    title="New Confession",
                    description=message,
                    color=Colour.green(),
                )
                log_embed.add_field(
                    name="Author",
                    value=f"{ctx.author.mention}",
                )
                log_embed.add_field(
                    name="Jump To Confession",
                    value=f"[Click Here]({conf_msg.jump_url})",
                )
                await log_channel.send(embed=log_embed)

        await ctx.reply(
            "Your confession has been sent!",
            ephemeral=True,
        )

    def safe_message(self, message: str) -> str:
        safe_msg = re.sub(r"@everyone", "@\u200beveryone", message)
        safe_msg = re.sub(r"@here", "@\u200bhere", safe_msg)
        return safe_msg


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(ConfessionCog(bot))
