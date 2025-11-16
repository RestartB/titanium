from typing import TYPE_CHECKING, Literal

from discord import Attachment, Colour, Embed, app_commands
from discord.ext import commands

from lib.helpers.img_tools import ImageConverter

if TYPE_CHECKING:
    from main import TitaniumBot


class ImageCog(commands.Cog, name="Images", description="Image processing commands."):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

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
        image="Upload the image you want to convert.",
        output_format="Select the target image format.",
    )
    async def convert_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        output_format: Literal["PNG", "JPEG", "WEBP", "GIF"],
    ) -> None:
        """Convert a image to "PNG", "JPEG", "WEBP", "GIF" """
        await ctx.defer()

        valid_output_formats = ImageConverter.format_types()
        requested_output_format = output_format.upper()
        if requested_output_format not in valid_output_formats:
            e = Embed(
                color=Colour.red(),
                title="Invalid Output Format",
                description=f"Please specify a valid output format: {', '.join(valid_output_formats)}.",
            )
            await ctx.reply(embed=e)
            return

        converter = ImageConverter(image)
        file = await converter.convert(requested_output_format)
        await ctx.reply(file=file)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ImageCog(bot))
