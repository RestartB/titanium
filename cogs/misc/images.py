import os
from typing import TYPE_CHECKING, Literal

import discord
from discord import Attachment, app_commands
from discord.ext import commands

from lib.classes.img_tools import ImageTools, ImageTooSmallError, OperationTooLargeError
from lib.enums.images import ImageFormats
from lib.helpers.hybrid_adapters import defer, stop_loading

if TYPE_CHECKING:
    from main import TitaniumBot


class ImageCog(commands.Cog, name="Images", description="Image processing commands."):
    STANDARD_QUALITY = 95

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        embed = discord.Embed(title=f"{self.bot.error_emoji} Error", colour=discord.Colour.red())

        if isinstance(error, ImageTooSmallError):
            embed.description = "The provided image is too small for this operation."
        elif isinstance(error, OperationTooLargeError):
            embed.description = "The resulting image would be too large to process. Please ensure that the result image is below 10000x10000px."
        else:
            raise error

        await ctx.reply(embed=embed)

    async def cog_app_command_error(
        self, interaction: discord.Interaction[discord.Client], error: app_commands.AppCommandError
    ) -> None:
        embed = discord.Embed(title=f"{self.bot.error_emoji} Error", colour=discord.Colour.red())

        if isinstance(error, ImageTooSmallError):
            embed.description = "The provided image is too small for this operation."
        elif isinstance(error, OperationTooLargeError):
            embed.description = "The resulting image would be too large to process. Please ensure that the result image is below 10000x10000px."
        else:
            raise error

        await interaction.edit_original_response(embed=embed)

    @commands.hybrid_group(name="image", description="Image processing commands.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def image_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise commands.CommandNotFound

    @image_group.command(
        name="convert",
        description="Convert an uploaded image to a different format.",
    )
    @app_commands.describe(
        image="The image to convert.",
        output_format="The format to convert to.",
    )
    async def convert_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        output_format: ImageFormats,
    ) -> None:
        """Convert a image to various formats."""
        await defer(ctx)

        try:
            converter = ImageTools(image)
            file = await converter.convert(output_format, self.STANDARD_QUALITY)

            await ctx.reply(file=file)
        finally:
            await stop_loading(ctx)

    @image_group.command(
        name="resize",
        description="Resize an uploaded image.",
    )
    @app_commands.describe(
        image="The image to resize.",
        width="The new width of the image.",
        height="The new height of the image.",
    )
    async def resize_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        width: commands.Range[int, 1, 5000],
        height: commands.Range[int, 1, 5000],
    ) -> None:
        """Resize an image to the specified dimensions."""
        await defer(ctx)

        try:
            converter = ImageTools(image)
            file = await converter.resize(ImageFormats.PNG, width, height)

            await ctx.reply(file=file)
        finally:
            await stop_loading(ctx)

    @image_group.command(
        name="deepfry",
        description="Deepfry an uploaded image.",
    )
    @app_commands.describe(
        image="The image to deepfry.",
        intensity_scale="Optional: the intensity scale to apply (0 to 100). Defaults to 100.",
        red_filter="Optional: whether to apply a red filter. Defaults to True.",
    )
    async def deepfry_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        intensity_scale: commands.Range[float, 1, 100] = 100,
        red_filter: bool = True,
    ) -> None:
        """Deepfry an image."""

        await defer(ctx)

        try:
            intensity_scale /= 100.0

            converter = ImageTools(image)
            file = await converter.deepfry(ImageFormats.PNG, intensity_scale, red_filter)

            await ctx.reply(file=file)
        finally:
            await stop_loading(ctx)

    @image_group.command(
        name="invert",
        description="Invert the colors of an uploaded image.",
    )
    @app_commands.describe(
        image="The image to invert.",
    )
    async def invert_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
    ) -> None:
        """Invert the colors of an image."""
        await defer(ctx)

        try:
            converter = ImageTools(image)
            file = await converter.invert(ImageFormats.PNG)

            await ctx.reply(file=file)
        finally:
            await stop_loading(ctx)

    @image_group.command(
        name="grayscale",
        description="Convert an uploaded image to grayscale.",
    )
    @app_commands.describe(
        image="The image to convert to grayscale.",
    )
    async def grayscale_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
    ) -> None:
        """Convert an image to grayscale."""
        await defer(ctx)

        try:
            converter = ImageTools(image)
            file = await converter.grayscale(ImageFormats.PNG)

            await ctx.reply(file=file)
        finally:
            await stop_loading(ctx)

    @image_group.command(
        name="rotate",
        description="Rotate an uploaded image.",
    )
    @app_commands.describe(
        image="The image to rotate.",
        angle="The angle to rotate the image by (in degrees).",
    )
    async def rotate_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        angle: int,
    ) -> None:
        """Rotate an image by the specified angle."""
        await defer(ctx)

        try:
            converter = ImageTools(image)
            file = await converter.rotate(ImageFormats.PNG, angle)

            await ctx.reply(file=file)
        finally:
            await stop_loading(ctx)

    @image_group.command(
        name="speechbubble",
        description="Add a speech bubble effect to an uploaded image.",
    )
    @app_commands.describe(
        image="The image to add a speech bubble to.",
        direction="Optional: the direction the speech bubble points to. Defaults to right.",
        colour="Optional: the colour of the speech bubble. Defaults to white.",
    )
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="Left", value="left"),
            app_commands.Choice(name="Right", value="right"),
        ],
        colour=[
            app_commands.Choice(name="Black", value="black"),
            app_commands.Choice(name="White", value="white"),
            app_commands.Choice(name="Transparent", value="transparent"),
        ],
    )
    async def speechbubble_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        direction: Literal["left", "right"] = "right",
        colour: Literal["black", "white", "transparent"] = "white",
    ) -> None:
        """Add a speech bubble effect to an image."""
        await defer(ctx)

        try:
            converter = ImageTools(image)
            file = await converter.speech_bubble(ImageFormats.PNG, direction, colour)

            await ctx.reply(file=file)
        finally:
            await stop_loading(ctx)

    @image_group.command(
        name="caption",
        description="Add a caption to an uploaded image.",
    )
    @app_commands.describe(
        image="The image to caption.",
        caption="The caption text to add to the image.",
        font="Optional: the font to use for the caption. Defaults to Figtree.",
    )
    @app_commands.choices(
        position=[
            app_commands.Choice(name="Top", value="top"),
            app_commands.Choice(name="Bottom", value="bottom"),
        ],
        font=[
            app_commands.Choice(name="Futura Condensed", value="futura"),
            app_commands.Choice(name="Impact", value="impact"),
            app_commands.Choice(name="Figtree", value="figtree"),
        ],
    )
    async def caption_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        caption: str,
        font: Literal["futura", "impact", "figtree"] = "figtree",
        position: Literal["top", "bottom"] = "top",
    ) -> None:
        """Add a caption to an image."""
        await defer(ctx)

        try:
            if font == "futura":
                selected_font = os.path.join("lib", "fonts", "futura.otf")
            else:
                selected_font = os.path.join("lib", "fonts", f"{font}.ttf")

            converter = ImageTools(image)
            file = await converter.caption(
                ImageFormats.GIF, caption.lower(), selected_font, position
            )

            await ctx.reply(file=file)
        finally:
            await stop_loading(ctx)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ImageCog(bot))
