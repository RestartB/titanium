from typing import TYPE_CHECKING

from discord import Attachment, Colour, Embed, app_commands
from discord.ext import commands

from lib.enums.images import ImageFormats
from lib.helpers.img_tools import ImageTools

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
        await ctx.defer()

        valid_output_formats = ImageTools.format_types()
        requested_output_format = output_format

        if requested_output_format not in valid_output_formats:
            e = Embed(
                color=Colour.red(),
                title=f"{self.bot.error_emoji} Invalid Output Format",
                description=f"Please specify a valid output format: `{', '.join(valid_output_formats)}`.",
            )
            await ctx.reply(embed=e)
            return

        converter = ImageTools(image)
        file = await converter.convert(requested_output_format)
        await ctx.reply(file=file)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ImageCog(bot))
