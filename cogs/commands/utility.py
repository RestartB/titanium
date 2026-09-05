import asyncio
import base64
import binascii
from textwrap import shorten
from typing import TYPE_CHECKING

import discord
import humanize
from discord import Attachment, Colour, Embed, File, Interaction, app_commands
from discord.ext import commands
from discord.ui import View

from lib.helpers.qrcode import generate_qrcode
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
    @app_commands.checks.cooldown(1, 30)
    async def feedback(self, interaction: Interaction["TitaniumBot"]) -> None:
        modal = FeedbackModal()
        await interaction.response.send_modal(modal)

    base64_group = app_commands.Group(
        name="base64",
        description="Convert text to and from Base64.",
        allowed_contexts=discord.app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        ),
        allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True),
    )

    @base64_group.command(name="encode", description="Convert text to Base64.")
    @app_commands.describe(
        text="Text to convert to Base64.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    async def base64_encode(
        self, interaction: discord.Interaction["TitaniumBot"], *, text: str, ephemeral: bool = False
    ) -> None:
        """
        Encode text to Base64.
        """

        await interaction.response.defer(ephemeral=ephemeral)

        encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")

        if len(encoded) > 4090:
            embed = Embed(
                colour=Colour.red(),
                title=f"{self.bot.error_emoji} Too Long",
                description="The encoded text is too long to display.",
            )
            embed.set_footer(
                text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        embed = Embed(
            colour=Colour.green(),
            title=f"{self.bot.success_emoji} Base64 Encoded",
            description=f"```{encoded}```",
        )
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @base64_group.command(name="decode", description="Convert text from Base64.")
    @app_commands.describe(
        base_64="Base64 to convert to text.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    async def base64_decode(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        *,
        base_64: str,
        ephemeral: bool = False,
    ) -> None:
        """
        Decode Base64 to text.
        """

        await interaction.response.defer(ephemeral=ephemeral)

        try:
            decoded = base64.b64decode(base_64.encode("utf-8")).decode("utf-8")
        except binascii.Error:
            embed = Embed(
                colour=Colour.red(),
                title=f"{self.bot.error_emoji} Invalid Input",
                description="The input is not valid Base64.",
            )
            embed.set_footer(
                text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        if len(decoded) > 4090:
            embed = Embed(
                colour=Colour.red(),
                title=f"{self.bot.error_emoji} Too Long",
                description="The decoded text is too long to display.",
            )
            embed.set_footer(
                text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        embed = Embed(
            colour=Colour.green(),
            title=f"{self.bot.success_emoji} Base64 Decoded",
            description=f"```{decoded}```",
        )
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="qrcode", description="Generate a QR code from a string.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        data="Data to be included in the QR code.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 5)
    async def qrcode(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        *,
        data: app_commands.Range[str, 1, 1000],
        ephemeral: bool = False,
    ) -> None:
        """Generate a QR code from any string."""
        await interaction.response.defer(ephemeral=ephemeral)

        file: File = await asyncio.to_thread(generate_qrcode, data)

        embed = Embed(
            title=f"{self.bot.success_emoji} QR Code Generated",
            description=f"QR code generated for:\n```{data}```",
            colour=Colour.green(),
        )
        embed.set_image(url="attachment://titanium_qrcode.png")
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        await interaction.followup.send(embed=embed, file=file, ephemeral=ephemeral)

    @app_commands.command(name="file-info", description="Get basic info about a file.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        file="The file to get info from.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    async def file_info(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        *,
        file: Attachment,
        ephemeral: bool = False,
    ) -> None:
        """Get detailed information of a file."""
        await interaction.response.defer(ephemeral=ephemeral)

        size_hr = humanize.naturalsize(file.size)

        embed = Embed(
            colour=Colour.light_grey(),
            title="File Information",
        )
        embed.set_thumbnail(url=file.url)

        embed.add_field(name="Name", value=f"`{file.filename}`")
        embed.add_field(name="Size", value=f"`{size_hr}`")
        embed.add_field(
            name="Content Type",
            value=f"`{file.content_type}`" if file.content_type else "`Unknown`",
        )
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # First Message command
    @app_commands.command(
        name="first-message",
        description="Get the first message in a channel, uses current channel by default.",
    )
    @app_commands.describe(
        channel="Optional: the target channel. Defaults to the current channel.",
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to true.",
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
