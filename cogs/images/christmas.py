from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, UnidentifiedImageError

from lib.classes.img_tools import ImageTools, OperationTooLargeError, StaticImageRequiredError

if TYPE_CHECKING:
    from main import TitaniumBot


POSITIONS = [
    app_commands.Choice(name="Top Left", value="topleft"),
    app_commands.Choice(name="Top Middle", value="topmiddle"),
    app_commands.Choice(name="Top Right", value="topright"),
    app_commands.Choice(name="Middle Left", value="middleleft"),
    app_commands.Choice(name="Middle", value="middle"),
    app_commands.Choice(name="Middle Right", value="middleright"),
    app_commands.Choice(name="Bottom Left", value="bottomleft"),
    app_commands.Choice(name="Bottom Middle", value="bottommiddle"),
    app_commands.Choice(name="Bottom Right", value="bottomright"),
]


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class ChristmasCog(commands.GroupCog, group_name="christmas", description="Christmas commands."):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    async def _send_image(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        file: discord.File,
        title: str,
        ephemeral: bool,
        user: discord.User | discord.Member | None = None,
    ) -> None:
        embed = discord.Embed(
            title=title,
            colour=(user.accent_colour if user else None) or discord.Colour.light_grey(),
        )
        embed.set_image(url=f"attachment://{file.filename}")
        if user:
            embed.set_author(
                name=f"{user.display_name} (@{user.name})", icon_url=user.display_avatar.url
            )
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )
        message = await interaction.followup.send(
            embed=embed, file=file, ephemeral=ephemeral, wait=True
        )
        if message.attachments:
            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(label="Open in Browser", url=message.attachments[0].url)
            )
            await message.edit(view=view)

    async def _send_error(
        self, interaction: discord.Interaction["TitaniumBot"], description: str, ephemeral: bool
    ) -> None:
        embed = discord.Embed(
            title=f"{self.bot.error_emoji} Invalid Image",
            description=description,
            colour=discord.Colour.red(),
        )
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @app_commands.command(
        name="pfp", description="Add a Christmas hat and snow to a user's avatar."
    )
    @app_commands.describe(
        user="The target user. Defaults to you.",
        hat="Whether to add a Christmas hat. Defaults to true.",
        snow="Whether to add snow. Defaults to true.",
        hat_size="The size of the hat. Defaults to normal.",
        position="The position of the hat. Defaults to top middle.",
        x_offset="Horizontal adjustment (-128 to 128). Defaults to 0.",
        y_offset="Vertical adjustment (-128 to 128); positive moves up. Defaults to 0.",
        rotation="Hat rotation in degrees (-180 to 180). Defaults to 0.",
        ephemeral="Whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.choices(
        hat_size=[
            app_commands.Choice(name="Small", value=6),
            app_commands.Choice(name="Normal", value=4),
            app_commands.Choice(name="Large", value=2),
        ],
    )
    @app_commands.choices(
        position=[choice for choice in POSITIONS if not choice.value.startswith("middle")],
    )
    @app_commands.checks.cooldown(1, 5)
    async def christmas_pfp(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        user: discord.User | None = None,
        hat: bool = True,
        snow: bool = True,
        hat_size: app_commands.Choice[int] | None = None,
        position: app_commands.Choice[str] | None = None,
        x_offset: app_commands.Range[int, -128, 128] = 0,
        y_offset: app_commands.Range[int, -128, 128] = 0,
        rotation: app_commands.Range[int, -180, 180] = 0,
        ephemeral: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)
        target = user or interaction.user
        avatar = await target.display_avatar.replace(format="png").read()
        file = await ImageTools().christmas(
            avatar=avatar,
            hat=hat,
            snow=snow,
            hat_size=hat_size.value if hat_size else 4,
            position=position.value if position else "topmiddle",
            x_offset=x_offset,
            y_offset=y_offset,
            rotation=rotation,
        )
        await self._send_image(interaction, file, "Christmas PFP", ephemeral, target)

    @app_commands.command(
        name="image", description="Add a Christmas hat and snow to a static image."
    )
    @app_commands.describe(
        file="The static image to edit (smaller than 20MB).",
        hat="Whether to add a Christmas hat. Defaults to true.",
        snow="Whether to add snow. Defaults to true.",
        hat_width="Hat width in pixels (10 to 1000). Defaults to half the image width.",
        position="The position of the hat. Defaults to top middle.",
        x_offset="Horizontal adjustment in pixels. Defaults to 0.",
        y_offset="Vertical adjustment in pixels; positive moves up. Defaults to 0.",
        rotation="Hat rotation in degrees (-180 to 180). Defaults to 0.",
        ephemeral="Whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.choices(position=POSITIONS)
    @app_commands.checks.cooldown(1, 5)
    async def christmas_image(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        file: discord.Attachment,
        hat: bool = True,
        snow: bool = True,
        hat_width: app_commands.Range[int, 10, 1000] | None = None,
        position: app_commands.Choice[str] | None = None,
        x_offset: int = 0,
        y_offset: int = 0,
        rotation: app_commands.Range[int, -180, 180] = 0,
        ephemeral: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)
        if file.content_type and not file.content_type.startswith("image/"):
            await self._send_error(interaction, "Please provide a static image.", ephemeral)
            return
        try:
            result = await ImageTools(file).christmas(
                hat=hat,
                snow=snow,
                hat_width=hat_width if hat_width is not None else 0,
                position=position.value if position else "topmiddle",
                x_offset=x_offset,
                y_offset=y_offset,
                rotation=rotation,
            )
        except (StaticImageRequiredError, OperationTooLargeError) as error:
            await self._send_error(interaction, str(error), ephemeral)
            return
        except UnidentifiedImageError, OSError, Image.DecompressionBombError:
            await self._send_error(
                interaction,
                "This file could not be processed. Please provide a valid static image.",
                ephemeral,
            )
            return
        await self._send_image(interaction, result, "Christmas Image", ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ChristmasCog(bot))
