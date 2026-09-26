from textwrap import shorten
from typing import TYPE_CHECKING

import discord
from discord import Colour, Interaction, app_commands
from discord.ext import commands
from discord.ui import View

from lib.views.feedback_modal import FeedbackModal

if TYPE_CHECKING:
    from main import TitaniumBot


class UtilityCog(commands.Cog, name="Utility", description="General utility commands."):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

    @app_commands.command(
        name="feedback",
        description="Provide feedback, share suggestions, or report bugs and other issues.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.checks.cooldown(1, 60)
    async def feedback(self, interaction: Interaction["TitaniumBot"]) -> None:
        modal = FeedbackModal()
        await interaction.response.send_modal(modal)

    # First Message command
    @app_commands.command(
        name="first-message",
        description="Get the first message in a chsannel, uses current channel by default.",
    )
    @app_commands.describe(
        channel="Optional: the target channel. Defaults to the current channel.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to true.",
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.checks.cooldown(1, 5)
    async def first_message(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        channel: discord.abc.GuildChannel | None = None,
        ephemeral: bool = True,
    ) -> None:
        if not interaction.guild:
            raise ValueError("No guild available")

        await interaction.response.defer(ephemeral=ephemeral)

        if isinstance(interaction.user, discord.User):
            raise TypeError("Author is a discord.User")

        if not channel:
            if not isinstance(interaction.channel, discord.abc.GuildChannel):
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Error",
                    description="The current channel is not supported.",
                    colour=Colour.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return

            channel = interaction.channel

        if not isinstance(channel, discord.abc.Messageable):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="The selected channel does not support messages.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        user_perms = channel.permissions_for(interaction.user)
        bot_perms = channel.permissions_for(interaction.guild.me)

        if not user_perms.read_messages or not user_perms.read_message_history:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Not Allowed",
                description="You do not have permissions to read the message history of the selected channel.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        if not bot_perms.read_messages or not bot_perms.read_message_history:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Not Allowed",
                description="Titanium does not have permission to read the message history of the selected channel.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        message = None
        try:
            async for msg in channel.history(limit=1, oldest_first=True):
                message = msg
        except discord.errors.Forbidden:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Forbidden",
                description="Titanium may not have permissions to read the message history of the selected channel.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

        if not message:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Messages",
                description="Titanium couldn't find any messages in the selected channel.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        embed = discord.Embed(
            title="First Message",
            description=f"{message.content if message.content else 'No content.'}",
            timestamp=message.created_at,
        )
        embed.set_author(name=f"#{shorten(channel.name, width=255)}")
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        if msg.author is not None and not msg.is_system():
            embed.set_author(
                name=msg.author.display_name,
                icon_url=msg.author.display_avatar.url,
            )

        view = View()
        view.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.url,
                url=msg.jump_url,
                label="Jump to Message",
            )
        )

        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(UtilityCog(bot))
