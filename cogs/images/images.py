import os
import random
from io import BytesIO
from typing import TYPE_CHECKING, ClassVar, Literal, cast

import aiohttp
import discord
from discord import Attachment, ButtonStyle, Colour, app_commands
from discord.ext import commands

from lib.classes import img_tools
from lib.enums.images import ImageFormats
from lib.helpers.hybrid import defer, handle_group_command_not_found
from lib.helpers.log_error import log_error

if TYPE_CHECKING:
    from main import TitaniumBot

STANDARD_QUALITY = 95


class ImageFormatPicker(discord.ui.View):
    def __init__(self, message: discord.Message, quality: int):
        super().__init__(timeout=60)

        self.message: discord.Message = message
        self.quality = quality
        self.interaction: discord.Interaction["TitaniumBot"] | None = None

        for image_format in ImageFormats:
            self.format_picker.add_option(label=image_format.value)

    async def on_timeout(self) -> None:
        if self.interaction:
            await self.interaction.delete_original_response()

    @discord.ui.select(placeholder="Select a format...")
    async def format_picker(
        self, interaction: discord.Interaction["TitaniumBot"], select: discord.ui.Select
    ) -> None:
        self.stop()
        await interaction.response.defer()

        files = []
        for attachment in self.message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                continue

            converter = img_tools.ImageTools(attachment)
            files.append(await converter.convert(ImageFormats[select.values[0]], self.quality))

        if not files:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} No Files Converted",
                description="No files could be converted. Check that the files are actual files (not links) and valid images, then try again.",
                colour=Colour.red(),
            )
            await interaction.edit_original_response(view=None, embed=embed)
            return

        await interaction.edit_original_response(view=None, attachments=files)


class BaseModal(discord.ui.Modal):
    # TODO: maybe switch to a dropdown
    output_format = discord.ui.Label(
        text="Output Format",
        description="Select the image format to output to.",
        component=discord.ui.Select(
            options=[
                discord.SelectOption(
                    label=image_format.value,
                )
                for image_format in ImageFormats
            ],
        ),
    )

    def __init__(
        self,
        title: str,
        message: discord.Message,
        interaction: discord.Interaction | None,
        loading: discord.Embed,
        expired: discord.Embed,
    ):
        super().__init__(title=title, timeout=600)
        self.images: list[discord.File] = []
        self.message = message
        self.interaction = interaction
        self.loading = loading
        self.expired = expired

    async def on_timeout(self) -> None:
        if self.interaction:
            await self.interaction.edit_original_response(embed=self.expired)

    async def interaction_check(self, interaction: discord.Interaction["TitaniumBot"]) -> bool:
        self.stop()
        if self.interaction:
            await self.interaction.edit_original_response(embed=self.loading)
        return True

    async def on_error(
        self, interaction: discord.Interaction["TitaniumBot"], error: Exception
    ) -> None:
        self.stop()

        error_id = await log_error(
            interaction.client,
            module="Images",
            guild_id=None,
            error="Unexpected error when manipulating image",
            details=f"User ID: {interaction.user.id}",
            exc=error,
            store_err=False,
        )

        embed = discord.Embed(
            title=f"{interaction.client.error_emoji} Error",
            description="An error occurred when processing your image. Please try again later.",
            colour=Colour.red(),
        )
        embed.add_field(
            name="Error ID",
            value=f"`{error_id}`",
            inline=False,
        )

        if self.interaction:
            await interaction.edit_original_response(embed=embed)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)


class ResizeModal(BaseModal):
    width = discord.ui.Label(
        text="Width",
        description="Enter the new width of the image.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.short,
            min_length=1,
            max_length=4,
        ),
    )

    height = discord.ui.Label(
        text="Height",
        description="Enter the new height of the image.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.short,
            min_length=1,
            max_length=4,
        ),
    )

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        assert isinstance(self.output_format.component, discord.ui.Select)
        assert isinstance(self.width.component, discord.ui.TextInput)
        assert isinstance(self.height.component, discord.ui.TextInput)

        try:
            width = int(self.width.component.value)
            height = int(self.width.component.value)

            if width > 5000 or height > 5000 or width < 1 or height < 1:
                raise ValueError("Size invalid")
        except ValueError:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Invalid Sizes",
                description="Please ensure your width and height are values between `1` and `5000`.",
                colour=Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            if self.interaction:
                await self.interaction.delete_original_response()
            return

        await interaction.response.defer(ephemeral=True)

        for attachment in self.message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                continue

            converter = img_tools.ImageTools(attachment)
            self.images.append(
                await converter.resize(
                    ImageFormats[self.output_format.component.values[0]], width, height
                )
            )

        await interaction.edit_original_response(attachments=self.images, embed=None)


class DeepfryModal(BaseModal):
    intensity = discord.ui.Label(
        text="Intensity",
        description="Enter the intensity of the deepfry, between 0 and 100.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.short, min_length=1, max_length=3, default="100"
        ),
    )

    filter = discord.ui.Label(
        text="Red Filter",
        description="Whether to add a red filter to the image.",
        component=discord.ui.Checkbox(default=True),
    )

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        assert isinstance(self.output_format.component, discord.ui.Select)
        assert isinstance(self.intensity.component, discord.ui.TextInput)
        assert isinstance(self.filter.component, discord.ui.Checkbox)

        try:
            intensity = int(self.intensity.component.value)

            if intensity > 100 or intensity < 0:
                raise ValueError("Intensity invalid")
        except ValueError:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Invalid Intensity",
                description="Please ensure your intensity is a number between `0` and `100`.",
                colour=Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            if self.interaction:
                await self.interaction.delete_original_response()
            return

        await interaction.response.defer(ephemeral=True)

        intensity /= 100.0
        for attachment in self.message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                continue

            converter = img_tools.ImageTools(attachment)
            self.images.append(
                await converter.deepfry(
                    ImageFormats[self.output_format.component.values[0]],
                    intensity,
                    self.filter.component.value,
                )
            )

        await interaction.edit_original_response(attachments=self.images, embed=None)


class InvertModal(BaseModal):
    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        assert isinstance(self.output_format.component, discord.ui.Select)

        await interaction.response.defer(ephemeral=True)
        for attachment in self.message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                continue

            converter = img_tools.ImageTools(attachment)
            self.images.append(
                await converter.invert(ImageFormats[self.output_format.component.values[0]])
            )

        await interaction.edit_original_response(attachments=self.images, embed=None)


class GreyscaleModal(BaseModal):
    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        assert isinstance(self.output_format.component, discord.ui.Select)

        await interaction.response.defer(ephemeral=True)
        for attachment in self.message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                continue

            converter = img_tools.ImageTools(attachment)
            self.images.append(
                await converter.grayscale(ImageFormats[self.output_format.component.values[0]])
            )

        await interaction.edit_original_response(attachments=self.images, embed=None)


class RotateModal(BaseModal):
    angle = discord.ui.Label(
        text="Angle",
        description="Enter the angle to rotate by.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.short,
            min_length=1,
            max_length=5,
        ),
    )

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        assert isinstance(self.output_format.component, discord.ui.Select)
        assert isinstance(self.angle.component, discord.ui.TextInput)

        try:
            angle = int(self.angle.component.value)
            if angle > 9999 or angle < -9999:
                raise ValueError("Angle invalid")
        except ValueError:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Invalid Angle",
                description="Please ensure the provided angle is a valid number between `-9999` and `9999`.",
                colour=Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            if self.interaction:
                await self.interaction.delete_original_response()
            return

        await interaction.response.defer(ephemeral=True)

        for attachment in self.message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                continue

            converter = img_tools.ImageTools(attachment)
            self.images.append(
                await converter.rotate(ImageFormats[self.output_format.component.values[0]], angle)
            )

        await interaction.edit_original_response(attachments=self.images, embed=None)


class SpeechBubbleModal(BaseModal):
    direction = discord.ui.Label(
        text="Direction",
        description="Select the direction that the bubble will point to.",
        component=discord.ui.RadioGroup(
            options=[
                discord.RadioGroupOption(label="Left", value="left"),
                discord.RadioGroupOption(label="Right", value="right"),
            ],
        ),
    )

    colour = discord.ui.Label(
        text="Colour",
        description="Select the colour of the speech bubble.",
        component=discord.ui.RadioGroup(
            options=[
                discord.RadioGroupOption(label="White", value="white"),
                discord.RadioGroupOption(label="Black", value="black"),
                discord.RadioGroupOption(label="Transparent", value="transparent"),
            ],
        ),
    )

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        assert isinstance(self.output_format.component, discord.ui.Select)
        assert isinstance(self.direction.component, discord.ui.RadioGroup)
        assert isinstance(self.colour.component, discord.ui.RadioGroup)

        direction = self.direction.component.value
        colour = self.colour.component.value
        assert direction in ("left", "right")
        assert colour in ("white", "black", "transparent")

        bubble_direction = cast(Literal["left", "right"], direction)
        bubble_colour = cast(Literal["black", "white", "transparent"], colour)

        await interaction.response.defer(ephemeral=True)

        for attachment in self.message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                continue

            converter = img_tools.ImageTools(attachment)
            self.images.append(
                await converter.speech_bubble(
                    ImageFormats[self.output_format.component.values[0]],
                    bubble_direction,
                    bubble_colour,
                )
            )

        await interaction.edit_original_response(attachments=self.images, embed=None)


class CaptionModel(BaseModal):
    content = discord.ui.Label(
        text="Content",
        description="Enter the content of the caption.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.long,
            min_length=1,
            max_length=500,
        ),
    )

    position = discord.ui.Label(
        text="Position",
        description="Select the position of the caption.",
        component=discord.ui.RadioGroup(
            options=[
                discord.RadioGroupOption(label="Top", value="top", default=True),
                discord.RadioGroupOption(label="Bottom", value="bottom"),
            ],
        ),
    )

    font = discord.ui.Label(
        text="Font",
        description="Select the font to use for the caption.",
        component=discord.ui.RadioGroup(
            options=[
                discord.RadioGroupOption(label="Futura Condensed", value="futura", default=True),
                discord.RadioGroupOption(label="Impact", value="impact"),
                discord.RadioGroupOption(label="Figtree", value="figtree"),
            ],
        ),
    )

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        assert isinstance(self.output_format.component, discord.ui.Select)
        assert isinstance(self.content.component, discord.ui.TextInput)
        assert isinstance(self.position.component, discord.ui.RadioGroup)
        assert isinstance(self.font.component, discord.ui.RadioGroup)

        position = self.position.component.value
        font = self.font.component.value
        assert position in ("top", "bottom")
        assert font in ("futura", "impact", "figtree")

        position = cast(Literal["top", "bottom"], position)
        font = cast(Literal["futura", "impact", "figtree"], font)

        await interaction.response.defer(ephemeral=True)

        if font == "futura":
            selected_font = os.path.join("lib", "fonts", "futura.otf")
        else:
            selected_font = os.path.join("lib", "fonts", f"{font}.ttf")

        for attachment in self.message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                continue

            converter = img_tools.ImageTools(attachment)
            self.images.append(
                await converter.caption(
                    ImageFormats[self.output_format.component.values[0]],
                    self.content.component.value,
                    selected_font,
                    interaction.client.browser_renderer,
                    position,
                )
            )

        await interaction.edit_original_response(attachments=self.images, embed=None)


class OverlayModal(BaseModal):
    # TODO: add client side file format filter when discord.py implements this
    overlay = discord.ui.Label(
        text="Content",
        description="The image to overlay on top of the source.",
        component=discord.ui.FileUpload(max_values=1),
    )

    opacity = discord.ui.Label(
        text="Opacity",
        description="Enter the opacity of the overlay, between 1 and 100.",
        component=discord.ui.TextInput(style=discord.TextStyle.short, min_length=1, max_length=3),
    )

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        assert isinstance(self.output_format.component, discord.ui.Select)
        assert isinstance(self.overlay.component, discord.ui.FileUpload)
        assert isinstance(self.opacity.component, discord.ui.TextInput)

        try:
            opacity = int(self.opacity.component.value)
            if opacity > 100 or opacity < 1:
                raise ValueError("Opacity invalid")
        except ValueError:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Invalid Opacity",
                description="Please ensure the provided opacity is a valid number between `1` and `100`.",
                colour=Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            if self.interaction:
                await self.interaction.delete_original_response()
            return

        overlay = self.overlay.component.values[0]
        if not overlay.content_type or not overlay.content_type.startswith("image/"):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Invalid Overlay File",
                description="Please ensure the overlay file is a valid image.",
                colour=Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            if self.interaction:
                await self.interaction.delete_original_response()
            return

        if overlay.size > 5_000_000:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Invalid Overlay File",
                description="Please ensure the overlay file is `5MB` or lower.",
                colour=Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            if self.interaction:
                await self.interaction.delete_original_response()
            return

        await interaction.response.defer(ephemeral=True)

        overlay_bytes = BytesIO()
        await self.overlay.component.values[0].save(overlay_bytes)

        for attachment in self.message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                continue

            converter = img_tools.ImageTools(attachment)
            self.images.append(
                await converter.overlay(
                    overlay_bytes,
                    opacity,
                    ImageFormats[self.output_format.component.values[0]],
                )
            )

        await interaction.edit_original_response(attachments=self.images, embed=None)


class MoreImageToolsView(discord.ui.View):
    def __init__(
        self,
        message: discord.Message,
        waiting: discord.Embed,
        loading: discord.Embed,
        expired: discord.Embed,
    ):
        super().__init__(timeout=60)

        self.message: discord.Message = message
        self.waiting: discord.Embed = waiting
        self.loading: discord.Embed = loading
        self.expired: discord.Embed = expired
        self.interaction: discord.Interaction["TitaniumBot"] | None = None

    async def on_timeout(self) -> None:
        if self.interaction:
            await self.interaction.delete_original_response()

    async def interaction_check(self, interaction: discord.Interaction["TitaniumBot"]) -> bool:
        if self.interaction and interaction.user.id == self.interaction.user.id:
            if interaction.custom_id != self.close.custom_id:
                await self.interaction.edit_original_response(embed=self.waiting, view=None)
            return True

        embed = discord.Embed(
            title=f"{interaction.client.error_emoji} Not Allowed",
            description="Only the original sender of this panel can control it.",
            colour=Colour.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False

    @discord.ui.button(label="Resize")
    async def resize(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.send_modal(
            ResizeModal(
                title="Resize Options",
                message=self.message,
                interaction=interaction,
                loading=self.loading,
                expired=self.expired,
            )
        )

    @discord.ui.button(label="Deepfry")
    async def deepfry(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.send_modal(
            DeepfryModal(
                title="Deepfry Options",
                message=self.message,
                interaction=interaction,
                loading=self.loading,
                expired=self.expired,
            )
        )

    @discord.ui.button(label="Invert")
    async def invert(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.send_modal(
            InvertModal(
                title="Invert Options",
                message=self.message,
                interaction=interaction,
                loading=self.loading,
                expired=self.expired,
            )
        )

    @discord.ui.button(label="Greyscale")
    async def greyscale(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.send_modal(
            GreyscaleModal(
                title="Greyscale Options",
                message=self.message,
                interaction=interaction,
                loading=self.loading,
                expired=self.expired,
            )
        )

    @discord.ui.button(label="Rotate")
    async def rotate(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.send_modal(
            RotateModal(
                title="Rotate Options",
                message=self.message,
                interaction=interaction,
                loading=self.loading,
                expired=self.expired,
            )
        )

    @discord.ui.button(label="Speech Bubble")
    async def speech_bubble(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.send_modal(
            SpeechBubbleModal(
                title="Speech Bubble Options",
                message=self.message,
                interaction=interaction,
                loading=self.loading,
                expired=self.expired,
            )
        )

    @discord.ui.button(label="Caption")
    async def caption(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.send_modal(
            CaptionModel(
                title="Caption Options",
                message=self.message,
                interaction=interaction,
                loading=self.loading,
                expired=self.expired,
            )
        )

    @discord.ui.button(label="Overlay")
    async def overlay(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.send_modal(
            OverlayModal(
                title="Overlay Options",
                message=self.message,
                interaction=interaction,
                loading=self.loading,
                expired=self.expired,
            )
        )

    @discord.ui.button(label="Close", emoji="❌", style=ButtonStyle.red)
    async def close(
        self, interaction: discord.Interaction["TitaniumBot"], button: discord.ui.Button
    ) -> None:
        self.stop()
        if self.interaction:
            await self.interaction.delete_original_response()


class ImageCog(commands.Cog, name="Images", description="Image processing commands."):
    NASA_NUMBER_OF: ClassVar = {
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

        self.WAITING_EMBED = discord.Embed(
            title=f"{self.bot.loading_emoji} Waiting for input...",
            description="Please complete the questions in the popup displayed.",
            colour=Colour.light_grey(),
        )
        self.LOADING_EMBED = discord.Embed(
            title=f"{self.bot.loading_emoji} Generating...",
            colour=Colour.light_grey(),
        )
        self.EXPIRED_EMBED = discord.Embed(
            title=f"{self.bot.error_emoji} Expired",
            description="You cancelled the prompt or didn't respond within 10 minutes.",
            colour=Colour.red(),
        )

        self.convert_ctx = app_commands.ContextMenu(
            name="Convert Images",
            callback=self.convert_images_callback,
            allowed_contexts=discord.app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True),
        )
        self.more_tools_ctx = app_commands.ContextMenu(
            name="Edit Images",
            callback=self.more_tools_callback,
            allowed_contexts=discord.app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True),
        )

        self.bot.tree.add_command(self.convert_ctx)
        self.bot.tree.add_command(self.more_tools_ctx)

    @app_commands.checks.cooldown(1, 5)
    async def convert_images_callback(
        self, interaction: discord.Interaction["TitaniumBot"], message: discord.Message
    ) -> None:
        await interaction.response.defer()

        if not message.attachments:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Attachments",
                description="Titanium can't see any attachments on this message. Make sure the images are actual attachments (not links), then try again.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed)
            return

        view = ImageFormatPicker(message=message, quality=STANDARD_QUALITY)
        await interaction.followup.send(view=view)
        view.interaction = interaction

    @app_commands.checks.cooldown(1, 5)
    async def more_tools_callback(
        self, interaction: discord.Interaction["TitaniumBot"], message: discord.Message
    ) -> None:
        await interaction.response.defer()

        if not message.attachments:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Attachments",
                description="Titanium can't see any attachments on this message. Make sure the images are actual attachments (not links), then try again.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed)
            return

        view = MoreImageToolsView(
            message=message,
            waiting=self.WAITING_EMBED,
            loading=self.LOADING_EMBED,
            expired=self.EXPIRED_EMBED,
        )
        await interaction.followup.send(view=view)
        view.interaction = interaction

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
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def convert_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        output_format: ImageFormats,
        ephemeral: bool = False,
    ) -> None:
        """Convert a image to various formats."""
        async with defer(ctx, ephemeral=ephemeral):
            converter = img_tools.ImageTools(image)
            file = await converter.convert(output_format, STANDARD_QUALITY)

            await ctx.reply(file=file, ephemeral=ephemeral)

    @image_group.command(
        name="gif",
        description="Convert an image to GIF. For more formats, use the /image format command.",
        aliases=["to-gif", "togif"],
    )
    @app_commands.describe(
        image="The image to convert.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def gif_image(
        self, ctx: commands.Context["TitaniumBot"], image: Attachment, ephemeral: bool = False
    ) -> None:
        """Convert a image to GIF."""
        async with defer(ctx, ephemeral=ephemeral):
            converter = img_tools.ImageTools(image)
            file = await converter.convert(ImageFormats.GIF, STANDARD_QUALITY)

            await ctx.reply(file=file, ephemeral=ephemeral)

    @image_group.command(
        name="resize",
        description="Resize an uploaded image.",
    )
    @app_commands.describe(
        image="The image to resize.",
        width="The new width of the image.",
        height="The new height of the image.",
        output_format="Optional: the format to output to. Defaults to PNG.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def resize_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        width: commands.Range[int, 1, 5000],
        height: commands.Range[int, 1, 5000],
        output_format: ImageFormats = ImageFormats.PNG,
        ephemeral: bool = False,
    ) -> None:
        """Resize an image to the specified dimensions."""
        async with defer(ctx, ephemeral=ephemeral):
            converter = img_tools.ImageTools(image)
            file = await converter.resize(output_format, width, height)

            await ctx.reply(file=file, ephemeral=ephemeral)

    @image_group.command(
        name="deepfry",
        description="Deepfry an uploaded image.",
    )
    @app_commands.describe(
        image="The image to deepfry.",
        intensity_scale="Optional: the intensity scale to apply (0 to 100). Defaults to 100.",
        red_filter="Optional: whether to apply a red filter. Defaults to True.",
        output_format="Optional: the format to output to. Defaults to PNG.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def deepfry_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        intensity_scale: commands.Range[float, 1, 100] = 100,
        red_filter: bool = True,
        output_format: ImageFormats = ImageFormats.PNG,
        ephemeral: bool = False,
    ) -> None:
        """Deepfry an image."""

        async with defer(ctx, ephemeral=ephemeral):
            intensity_scale /= 100.0

            converter = img_tools.ImageTools(image)
            file = await converter.deepfry(output_format, intensity_scale, red_filter)

            await ctx.reply(file=file, ephemeral=ephemeral)

    @image_group.command(
        name="invert",
        description="Invert the colours of an uploaded image.",
    )
    @app_commands.describe(
        image="The image to invert.",
        output_format="Optional: the format to output to. Defaults to PNG.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def invert_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        output_format: ImageFormats = ImageFormats.PNG,
        ephemeral: bool = False,
    ) -> None:
        """Invert the colours of an image."""
        async with defer(ctx, ephemeral=ephemeral):
            converter = img_tools.ImageTools(image)
            file = await converter.invert(output_format)

            await ctx.reply(file=file, ephemeral=ephemeral)

    @image_group.command(
        name="grayscale",
        description="Convert an uploaded image to greyscale.",
    )
    @app_commands.describe(
        image="The image to convert to greyscale.",
        output_format="Optional: the format to output to. Defaults to PNG.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def greyscale_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        output_format: ImageFormats = ImageFormats.PNG,
        ephemeral: bool = False,
    ) -> None:
        """Convert an image to greyscale."""
        async with defer(ctx, ephemeral=ephemeral):
            converter = img_tools.ImageTools(image)
            file = await converter.grayscale(output_format)

            await ctx.reply(file=file, ephemeral=ephemeral)

    @image_group.command(
        name="rotate",
        description="Rotate an uploaded image.",
    )
    @app_commands.describe(
        image="The image to rotate.",
        angle="The angle to rotate the image by (in degrees).",
        output_format="Optional: the format to output to. Defaults to PNG.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def rotate_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        angle: commands.Range[int, -9999, 9999],
        output_format: ImageFormats = ImageFormats.PNG,
        ephemeral: bool = False,
    ) -> None:
        """Rotate an image by the specified angle."""
        async with defer(ctx, ephemeral=ephemeral):
            converter = img_tools.ImageTools(image)
            file = await converter.rotate(output_format, angle)

            await ctx.reply(file=file, ephemeral=ephemeral)

    @image_group.command(
        name="speechbubble",
        description="Add a speech bubble effect to an uploaded image.",
    )
    @app_commands.describe(
        image="The image to add a speech bubble to.",
        direction="Optional: the direction the speech bubble points to. Defaults to right.",
        colour="Optional: the colour of the speech bubble. Defaults to white.",
        output_format="Optional: the format to output to. Defaults to PNG.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
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
    @commands.cooldown(1, 5)
    async def speechbubble_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        direction: Literal["left", "right"] = "right",
        colour: Literal["black", "white", "transparent"] = "white",
        output_format: ImageFormats = ImageFormats.PNG,
        ephemeral: bool = False,
    ) -> None:
        """Add a speech bubble effect to an image."""
        async with defer(ctx, ephemeral=ephemeral):
            converter = img_tools.ImageTools(image)
            file = await converter.speech_bubble(output_format, direction, colour)

            await ctx.reply(file=file, ephemeral=ephemeral)

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
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
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
    @commands.cooldown(1, 5)
    async def caption_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        image: Attachment,
        caption: commands.Range[str, 1, 500],
        font: Literal["futura", "impact", "figtree"] = "futura",
        position: Literal["top", "bottom"] = "top",
        output_format: ImageFormats = ImageFormats.GIF,
        ephemeral: bool = False,
    ) -> None:
        """Add a caption to an image."""
        async with defer(ctx, ephemeral=ephemeral):
            if font == "futura":
                selected_font = os.path.join("lib", "fonts", "futura.otf")
            else:
                selected_font = os.path.join("lib", "fonts", f"{font}.ttf")

            converter = img_tools.ImageTools(image)
            file = await converter.caption(
                output_format, caption.lower(), selected_font, self.bot.browser_renderer, position
            )

            await ctx.reply(file=file, ephemeral=ephemeral)

    @image_group.command(
        name="overlay",
        description="Overlay a static image onto another static image.",
    )
    @app_commands.describe(
        source="The source image.",
        overlay="The image to overlay.",
        opacity="The percentage opacity of the overlay image.",
        output_format="Optional: the format to output to. Defaults to PNG.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def overlay_image(
        self,
        ctx: commands.Context["TitaniumBot"],
        source: Attachment,
        overlay: Attachment,
        opacity: commands.Range[int, 1, 100],
        output_format: ImageFormats = ImageFormats.PNG,
        ephemeral: bool = False,
    ) -> None:
        """Overlay a static image onto another static image."""
        async with defer(ctx, ephemeral=ephemeral):
            if not overlay.content_type or not overlay.content_type.startswith("image/"):
                embed = discord.Embed(
                    title=f"{ctx.bot.error_emoji} Invalid Overlay File",
                    description="Please ensure the overlay file is a valid image.",
                    colour=Colour.red(),
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            if overlay.size > 5_000_000:
                embed = discord.Embed(
                    title=f"{ctx.bot.error_emoji} Invalid Overlay File",
                    description="Please ensure the overlay file is `5MB` or lower.",
                    colour=Colour.red(),
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            converter = img_tools.ImageTools(source)
            file = await converter.overlay(overlay, opacity, output_format)
            await ctx.reply(file=file, ephemeral=ephemeral)

    @image_group.command(
        name="nasa",
        description="Create an image of characters spelt by Earth images by NASA Landsat.",
    )
    @app_commands.describe(
        word="Word to generate image of. Cannot contain spaces, numbers or special characters.",
        output_format="Optional: the format to output to. Defaults to GIF.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def nasa(
        self,
        ctx: commands.Context["TitaniumBot"],
        word: commands.Range[str, 1, 50],
        output_format: ImageFormats = ImageFormats.GIF,
        ephemeral: bool = False,
    ) -> None:
        async with defer(ctx, ephemeral=ephemeral):
            if len(word) > 50:
                embed = discord.Embed(
                    title=f"{ctx.bot.error_emoji} Too Long",
                    description="The word is too long. It can only be 50 letters long.",
                    colour=discord.Colour.red(),
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            if not (word.isascii() and word.isalpha()):
                embed = discord.Embed(
                    title=f"{ctx.bot.error_emoji} Invalid Input",
                    description="The word can only contain letters.",
                    colour=discord.Colour.red(),
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            images: list[BytesIO] = []
            for character in word:
                number = random.choice(self.NASA_NUMBER_OF[character.upper()])

                async with (
                    aiohttp.ClientSession() as session,
                    session.get(
                        f"https://science.nasa.gov/specials/your-name-in-landsat/images/{character}_{number}.jpg"
                    ) as request,
                ):
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
            await ctx.reply(embed=embed, file=file, ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ImageCog(bot))
