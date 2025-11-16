from typing import TYPE_CHECKING

import discord
from discord import Colour, Embed, app_commands
from discord.ext import commands
from discord.ui import Button, View

from lib.helpers.hybrid_adapters import SlashCommandOnly

if TYPE_CHECKING:
    from main import TitaniumBot


class ConfessionCog(commands.Cog, name="Confession", description="Anonymous message commands."):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

    @commands.command(
        name="confession", description="Please use the slash command version instead."
    )
    async def confession_prefix(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise SlashCommandOnly

    @app_commands.command(name="confession", description="Send an anonymous confession.")
    @app_commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.describe(
        message="Your message to include in the confession.",
    )
    async def confession(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        message: str,
    ) -> None:
        await interaction.response.defer()

        if interaction.guild is None:
            return

        if not isinstance(interaction.channel, discord.abc.Messageable):
            await interaction.followup.send(
                embed=Embed(
                    color=Colour.red(),
                    title=f"{self.bot.error_emoji} Invalid Channel",
                    description="Confessions cannot be sent from this channel type. Please use a different channel.",
                ),
                ephemeral=True,
            )
            return

        guild_settings = self.bot.guild_configs.get(interaction.guild.id)
        if not guild_settings or not guild_settings.confession_enabled:
            await interaction.followup.send(
                embed=Embed(
                    color=Colour.red(),
                    title=f"{self.bot.error_emoji} Confessions Disabled",
                    description="The confession module is disabled. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                )
            )
            return

        channel = self.bot.get_channel(guild_settings.confession_settings.confession_channel_id)
        if not channel:
            await interaction.followup.send(
                embed=Embed(
                    color=Colour.red(),
                    title=f"{self.bot.error_emoji} Channel Not Found",
                    description=(
                        "The confession channel is not set or could not be found. Ask a server admin to configure it using the Titanium Dashboard."
                    ),
                )
            )
            return

        if not isinstance(channel, discord.abc.Messageable):
            await interaction.followup.send(
                embed=Embed(
                    color=Colour.red(),
                    title=f"{self.bot.error_emoji} Invalid Channel",
                    description="Titanium can't send to the configured confession channel. Please ask a server admin to set a valid channel using the Titanium Dashboard.",
                ),
                ephemeral=True,
            )
            return

        conf_msg = await channel.send(
            embed=Embed(
                title="Anonymous Confession",
                description=message,
                color=Colour.random(),
                timestamp=interaction.created_at,
            )
        )

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
                    value=f"{interaction.user.mention}",
                )
                log_embed.add_field(
                    name="Jump To Confession",
                    value=f"[Click Here]({conf_msg.jump_url})",
                )
                await log_channel.send(embed=log_embed)

        await interaction.followup.send(
            embed=Embed(
                title=f"{self.bot.success_emoji} Sent",
                description="Your confession has been sent.",
                color=Colour.green(),
            ),
            view=View().add_item(
                Button(
                    label="View Confession",
                    url=conf_msg.jump_url,
                    style=discord.ButtonStyle.url,
                )
            ),
            ephemeral=True,
        )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ConfessionCog(bot))
