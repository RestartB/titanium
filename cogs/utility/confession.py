import re
from typing import TYPE_CHECKING

from discord import Colour, Embed, app_commands
from discord.ext import commands

from lib.sql import GuildConfessionSettings
from lib.views.confession import ConfessionSettings, ConfessionSettingsLayout

if TYPE_CHECKING:
    from main import TitaniumBot


class ConfessionCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot: "TitaniumBot" = bot

    async def cog_check(self, ctx: commands.Context["TitaniumBot"]) -> bool:
        if not ctx.guild:
            raise commands.errors.NoPrivateMessage(
                message="Confession commands onyl works on server."
            )
        return True

    @commands.hybrid_group(name="confession", description="Anonymous message commands.")
    @app_commands.guild_only()
    async def confession(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.send_help(ctx)

    @confession.command(name="message", description="Share an anonymous message")
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

        guild_settings = self.bot.guild_configs.get(ctx.guild.id)
        if not guild_settings or not guild_settings.confession_enabled:
            e = Embed(
                color=Colour.red(),
                title="Confession Disabled",
                description=f"The confession seettings is disabled for the {ctx.guild.name} server. Ask a server admin to turn it on using `/confession settings` command.",
            )
            return await ctx.reply(embed=e)
        channel = self.bot.get_channel(
            guild_settings.confession_settings.confession_channel_id
        )
        if not channel:
            embed = Embed(
                color=Colour.red(),
                title="Confession Channel Not Found",
                description=(
                    "The confession channel is not set or could not be found. Ask a server admin to configure it using `/confession settings` command."
                ),
            )
            return await ctx.reply(embed=embed)

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
            log_embed = Embed(
                title="Confession Log",
                description=message,
                color=Colour.orange(),
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

    def safe_message(self, message: str) -> None:
        safe_msg = re.sub(r"@everyone", "@\u200beveryone", message)
        safe_msg = re.sub(r"@here", "@\u200bhere", safe_msg)
        return safe_msg

    @confession.command(name="settings", description="Customize confession settings.")
    @commands.has_permissions(administrator=True)
    async def confession_settings(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        guild_settings = self.bot.guild_configs.get(ctx.guild.id)
        conf_settings = GuildConfessionSettings(guild_id=ctx.guild.id)

        if not guild_settings:
            guild_settings = await self.bot.init_guild(ctx.guild.id)

        if guild_settings.confession_settings:
            conf_settings = guild_settings.confession_settings

        await ctx.reply(
            view=ConfessionSettingsLayout(
                settings=ConfessionSettings(
                    user_id=ctx.author.id,
                    is_conf_enable=guild_settings.confession_enabled,
                    guild_settings=conf_settings,
                )
            )
        )


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(ConfessionCog(bot))
