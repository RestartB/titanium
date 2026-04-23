import os
import random
from io import BytesIO
from typing import TYPE_CHECKING, Literal

import aiohttp
import discord
from discord import Attachment, app_commands
from discord.ext import commands

from lib.classes import img_tools
from lib.enums.images import ImageFormats
from lib.helpers.hybrid_adapters import defer, handle_group_command_not_found

if TYPE_CHECKING:
    from main import TitaniumBot


class ImageCog(commands.Cog, name="Images", description="Image processing commands."):
    STANDARD_QUALITY = 95
    NASA_NUMBER_OF = {
        "A": [0, 1, 2, 3, 4],
        "B": [0, 1],
        "C": [0, 1, 2],
        "D": [0, 1],
        "E": [0, 1, 2, 3],
        "F": [0, 1],
        "G": [0],
        "H": [0, 1],
        "I": [0, 1, 2, 3, 4],
        "J": [0, 1, 2],
        "K": [0, 1],
        "L": [0, 1, 2, 3],
        "M": [0, 1, 2],
        "N": [0, 1, 2],
        "O": [0, 1],
        "P": [0, 1],
        "Q": [0, 1],
        "R": [0, 1, 2, 3],
        "S": [0, 1, 2],
        "T": [0, 1],
        "U": [0, 1],
        "V": [0, 1, 2, 3],
        "W": [0, 1],
        "X": [0, 1, 2],
        "Y": [0, 1],
        "Z": [0, 1],
    }

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        embed = discord.Embed(title=f"{self.bot.error_emoji} Error", colour=discord.Colour.red())

        if isinstance(error, img_tools.ImageTooSmallError):
            embed.description = "The provided image is too small for this operation."
        elif isinstance(error, img_tools.OperationTooLargeError):
            embed.description = "The resulting image would be too large to process. Please ensure that the result image is below 10000x10000px."
        else:
            raise error

        await ctx.reply(embed=embed)

    async def cog_app_command_error(
        self, interaction: discord.Interaction["TitaniumBot"], error: app_commands.AppCommandError
    ) -> None:
        embed = discord.Embed(title=f"{self.bot.error_emoji} Error", colour=discord.Colour.red())

        if isinstance(error, img_tools.ImageTooSmallError):
            embed.description = "The provided image is too small for this operation."
        elif isinstance(error, img_tools.OperationTooLargeError):
            embed.description = "The resulting image would be too large to process. Please ensure that the result image is below 10000x10000px."
        else:
            raise error

        await interaction.edit_original_response(embed=embed)

    @commands.hybrid_group(
        name="image",
        aliases=["images", "photo", "photos"],
        description="Image processing commands.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def image_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        handle_group_command_not_found(ctx)

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
        async with defer(ctx):
            converter = img_tools.ImageTools(image)
            file = await converter.convert(output_format, self.STANDARD_QUALITY)

            await ctx.reply(file=file)

    @image_group.command(
        name="resize",
        description="Resize an uploaded image.",
    )
    @app_commands.describe(
        image="The image to resize.",
        width="The new width of the image.",
        height="The new height of the image.",
        output_format="Optional: the format to output to. Defaults to PNG.",
    )
    async def resize_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        width: commands.Range[int, 1, 5000],
        height: commands.Range[int, 1, 5000],
        output_format: ImageFormats = ImageFormats.PNG,
    ) -> None:
        """Resize an image to the specified dimensions."""
        async with defer(ctx):
            converter = img_tools.ImageTools(image)
            file = await converter.resize(output_format, width, height)

            await ctx.reply(file=file)

    @image_group.command(
        name="deepfry",
        description="Deepfry an uploaded image.",
    )
    @app_commands.describe(
        image="The image to deepfry.",
        intensity_scale="Optional: the intensity scale to apply (0 to 100). Defaults to 100.",
        red_filter="Optional: whether to apply a red filter. Defaults to True.",
        output_format="Optional: the format to output to. Defaults to PNG.",
    )
    async def deepfry_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        intensity_scale: commands.Range[float, 1, 100] = 100,
        red_filter: bool = True,
        output_format: ImageFormats = ImageFormats.PNG,
    ) -> None:
        """Deepfry an image."""

        async with defer(ctx):
            intensity_scale /= 100.0

            converter = img_tools.ImageTools(image)
            file = await converter.deepfry(output_format, intensity_scale, red_filter)

            await ctx.reply(file=file)

    @image_group.command(
        name="invert",
        description="Invert the colours of an uploaded image.",
    )
    @app_commands.describe(
        image="The image to invert.",
        output_format="Optional: the format to output to. Defaults to PNG.",
    )
    async def invert_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        output_format: ImageFormats = ImageFormats.PNG,
    ) -> None:
        """Invert the colours of an image."""
        async with defer(ctx):
            converter = img_tools.ImageTools(image)
            file = await converter.invert(output_format)

            await ctx.reply(file=file)

    @image_group.command(
        name="grayscale",
        description="Convert an uploaded image to grayscale.",
    )
    @app_commands.describe(
        image="The image to convert to grayscale.",
        output_format="Optional: the format to output to. Defaults to PNG.",
    )
    async def grayscale_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        output_format: ImageFormats = ImageFormats.PNG,
    ) -> None:
        """Convert an image to grayscale."""
        async with defer(ctx):
            converter = img_tools.ImageTools(image)
            file = await converter.grayscale(output_format)

            await ctx.reply(file=file)

    @image_group.command(
        name="rotate",
        description="Rotate an uploaded image.",
    )
    @app_commands.describe(
        image="The image to rotate.",
        angle="The angle to rotate the image by (in degrees).",
        output_format="Optional: the format to output to. Defaults to PNG.",
    )
    async def rotate_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        angle: int,
        output_format: ImageFormats = ImageFormats.PNG,
    ) -> None:
        """Rotate an image by the specified angle."""
        async with defer(ctx):
            converter = img_tools.ImageTools(image)
            file = await converter.rotate(output_format, angle)

            await ctx.reply(file=file)

    @image_group.command(
        name="speechbubble",
        description="Add a speech bubble effect to an uploaded image.",
    )
    @app_commands.describe(
        image="The image to add a speech bubble to.",
        direction="Optional: the direction the speech bubble points to. Defaults to right.",
        colour="Optional: the colour of the speech bubble. Defaults to white.",
        output_format="Optional: the format to output to. Defaults to PNG.",
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
        output_format: ImageFormats = ImageFormats.PNG,
    ) -> None:
        """Add a speech bubble effect to an image."""
        async with defer(ctx):
            converter = img_tools.ImageTools(image)
            file = await converter.speech_bubble(output_format, direction, colour)

            await ctx.reply(file=file)

    @image_group.command(
        name="caption",
        description="Add a caption to an uploaded image.",
    )
    @app_commands.describe(
        image="The image to caption.",
        caption="The caption text to add to the image. Note: custom emojis are not supported.",
        font="Optional: the font to use for the caption. Defaults to Figtree.",
        position="Optional: the position to place the text in. Defaults to top.",
        output_format="Optional: the format to output to. Defaults to GIF.",
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
        caption: commands.Range[str, 1, 500],
        font: Literal["futura", "impact", "figtree"] = "figtree",
        position: Literal["top", "bottom"] = "top",
        output_format: ImageFormats = ImageFormats.GIF,
    ) -> None:
        """Add a caption to an image."""
        async with defer(ctx):
            if font == "futura":
                selected_font = os.path.join("lib", "fonts", "futura.otf")
            else:
                selected_font = os.path.join("lib", "fonts", f"{font}.ttf")

            converter = img_tools.ImageTools(image)
            file = await converter.caption(output_format, caption.lower(), selected_font, position)

            await ctx.reply(file=file)

    @image_group.command(
        name="nasa",
        description="Create an image of characters spelt by Earth images by NASA Landsat.",
    )
    @app_commands.describe(
        word="Word to generate image of. Cannot contain spaces, numbers or special characters.",
        output_format="Optional: the format to output to. Defaults to GIF.",
    )
    async def nasa(
        self,
        ctx: commands.Context["TitaniumBot"],
        word: commands.Range[str, 1, 50],
        output_format: ImageFormats = ImageFormats.GIF,
    ) -> None:
        async with defer(ctx):
            if len(word) > 50:
                embed = discord.Embed(
                    title=f"{ctx.bot.error_emoji} Error",
                    description="The word is too long. It can only be 50 letters long.",
                    colour=discord.Colour.red(),
                )
                await ctx.reply(embed=embed)
                return

            if not (word.isascii() and word.isalpha()):
                embed = discord.Embed(
                    title=f"{ctx.bot.error_emoji} Error",
                    description="The word can only contain letters.",
                    colour=discord.Colour.red(),
                )
                await ctx.reply(embed=embed)
                return

            images: list[BytesIO] = []
            for character in word:
                number = random.choice(self.NASA_NUMBER_OF[character.upper()])

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://science.nasa.gov/specials/your-name-in-landsat/images/{character}_{number}.jpg"
                    ) as request:
                        image_data = BytesIO()

                        async for chunk in request.content.iter_chunked(8192):
                            image_data.write(chunk)

                        image_data.seek(0)

                images.append(image_data)

            converter = img_tools.ImageTools()
            file = await converter.nasa(output_format, images)

            embed = discord.Embed(
                description=f"{ctx.bot.info_emoji} Images sourced from NASA and the U.S. Geological Survey.",
                colour=discord.Colour.light_grey(),
            )
            await ctx.reply(embed=embed, file=file)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ImageCog(bot))
