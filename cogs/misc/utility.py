import asyncio
import base64
from datetime import datetime
from typing import TYPE_CHECKING

import humanize
from discord import Attachment, Colour, Embed, File, Interaction, app_commands
from discord.ext import commands

from lib.helpers.qrcode import generate_qrcode
from lib.views.feedback_modal import FeedbackModal

if TYPE_CHECKING:
    from main import TitaniumBot


class UtilityCog(commands.Cog, name="Utility", description="General utility commands."):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

    @app_commands.command(name="feedback", description="Share any suggestions or feedback.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def feedback(self, interaction: Interaction["TitaniumBot"]) -> None:
        """
        This command allows you to provide feedback or share your suggestions or maybe any bug/issue with the bot's developers.
        """
        modal = FeedbackModal()
        await interaction.response.send_modal(modal)

    @commands.hybrid_group(name="base64", description="Base64 encoding and decoding.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def base64_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise commands.CommandNotFound

    @base64_group.command(name="encode", description="Convert text to Base64.")
    @app_commands.describe(
        text="Text to encode to Base64.",
    )
    async def base64_encode(
        self,
        ctx: commands.Context["TitaniumBot"],
        text: str,
    ) -> None:
        """
        Encode text to Base64.
        """

        await ctx.defer()

        encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")

        if len(encoded) > 4090:
            embed = Embed(
                colour=Colour.red(),
                title=f"{self.bot.error_emoji} Too Long",
                description="The encoded text is too long to display.",
            )
            embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed)
            return

        embed = Embed(
            colour=Colour.green(),
            title=f"{self.bot.success_emoji} Base64 Encoded",
            description=f"```{encoded}```",
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @base64_group.command(name="decode", description="Convert text from Base64.")
    @app_commands.describe(
        base_64="Base64 to convert to text.",
    )
    async def base64_decode(
        self,
        ctx: commands.Context["TitaniumBot"],
        base_64: str,
    ) -> None:
        """
        Decode Base64 to text.
        """

        await ctx.defer()

        decoded = base64.b64decode(base_64.encode("utf-8")).decode("utf-8")

        if len(decoded) > 4090:
            embed = Embed(
                colour=Colour.red(),
                title=f"{self.bot.error_emoji} Too Long",
                description="The decoded text is too long to display.",
            )
            embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)
            await ctx.reply(embed=embed)
            return

        embed = Embed(
            colour=Colour.green(),
            title=f"{self.bot.success_emoji} Base64 Decoded",
            description=f"```{decoded}```",
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="qrcode", description="Generate a QR code from a string.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(data="Data to be included in the QR code.")
    async def qrcode(
        self,
        ctx: commands.Context["TitaniumBot"],
        *,
        data: commands.Range[str, 1, 1000],
    ) -> None:
        """Generate a QR code from any string."""
        await ctx.defer()

        file: File = await asyncio.to_thread(generate_qrcode, data)

        embed = Embed(
            title=f"{str(self.bot.success_emoji)} QR Code Generated",
            description=f"QR code generated for:\n```{data}```",
            color=Colour.green(),
        )
        embed.set_image(url="attachment://titanium_qrcode.png")
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        await ctx.reply(embed=embed, file=file)

    @commands.hybrid_command(name="file-info", description="Get info of a file.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(file="The file attachment to analyse.")
    async def file_info(self, ctx: commands.Context["TitaniumBot"], *, file: Attachment) -> None:
        """Get detailed information of a file."""
        await ctx.defer()

        size_hr = humanize.naturalsize(file.size)

        embed = Embed(
            color=Colour.blue(),
            title="File Information",
        )
        embed.set_thumbnail(url=file.url)
        embed.add_field(name="ID", value=f"`{file.id}`")
        embed.add_field(name="File Name", value=f"`{file.filename}`")
        embed.add_field(name="File Size", value=f"`{size_hr}`")
        embed.add_field(name="Content Type", value=f"`{file.content_type}`" or "`Unknown`")
        embed.add_field(name="URL", value=f"[Click here]({file.url})")
        embed.add_field(name="Proxy URL", value=f"[Click here]({file.proxy_url})")
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = datetime.now()

        await ctx.reply(embed=embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(UtilityCog(bot))
