import asyncio
import os
from io import BytesIO

import aiohttp
import discord
import pillow_avif  # noqa: F401
from discord import Color, app_commands
from discord.ext import commands
from PIL import Image, ImageChops, ImageEnhance, ImageOps
from wand.image import Image as WandImage


class Images(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Convert to GIF option
        self.img_gif_ctx = app_commands.ContextMenu(
            name="Convert to GIF",
            callback=self.gif_callback,
            allowed_contexts=discord.app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=discord.app_commands.AppInstallationType(
                guild=True, user=True
            ),
        )

        # Deepfry option
        self.deepfry_ctx = app_commands.ContextMenu(
            name="Deepfry Images",
            callback=self.deepfry_callback,
            allowed_contexts=discord.app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=discord.app_commands.AppInstallationType(
                guild=True, user=True
            ),
        )

        self.bot.tree.add_command(self.img_gif_ctx)
        self.bot.tree.add_command(self.deepfry_ctx)

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=True, private_channel=True
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    imageGroup = app_commands.Group(
        name="image",
        description="Manipulate images.",
        allowed_contexts=context,
        allowed_installs=installs,
    )

    def _resize_image(
        self,
        image_data: BytesIO,
        width: int,
        height: int,
        format: str,
    ) -> tuple[BytesIO, tuple[int, int]]:
        # Open image
        with Image.open(image_data) as im:
            # Resize image
            resized_image = im.resize((int(width), int(height)))

            resized_image_data = BytesIO()

            # Save resized image
            resized_image.save(
                resized_image_data,
                format=format.upper().replace("JPG", "JPEG"),
            )

            new_size = resized_image.size

        resized_image_data.seek(0)
        return resized_image_data, new_size

    # Image Resize command
    @imageGroup.command(name="resize", description="Resize an image.")
    @app_commands.describe(
        target_x="Set a target width for the image. Defaults to the original length.",
        target_y="Set a target height for the image. Defaults to the original length.",
        scale="Scale the resolution by a certain amount. Overrides target_x and target_y if set.",
        spoiler="Optional: whether to send the image as a spoiler. Defaults to false.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 10)
    async def resize_image(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        scale: float = None,
        target_x: int = None,
        target_y: int = None,
        spoiler: bool = False,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        if (
            file.content_type.split("/")[0] == "image"
            and file.content_type.split("/")[1] != "gif"
            and file.content_type.split("/")[1] != "apng"
        ):  # Check if file is a static image
            if file.size < 20000000:  # 20MB file limit
                if (
                    (scale is not None)
                    or (target_x is not None)
                    or (target_y is not None)
                ):  # If scale or target_x or target_y are set
                    if scale is not None:  # If scale is set
                        # Set target_x and target_y to scaled image size
                        target_x = int(file.width * scale)
                        target_y = int(file.height * scale)
                    else:  # If scale is not set
                        # Set target_x and target_y to original image size if not set
                        target_x = target_x if target_x is not None else file.width
                        target_y = target_y if target_y is not None else file.height

                    if (
                        target_x > 4000 or target_y > 4000
                    ):  # Check if image is too large
                        embed = discord.Embed(
                            title="Error",
                            description=f"The result of this operation is too large. Please ensure it is smaller than 4000x4000. (current size: {target_x}x{target_y})",
                            color=Color.red(),
                        )
                        embed.set_footer(
                            text=f"@{interaction.user.name}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.followup.send(
                            embed=embed, ephemeral=ephemeral
                        )
                        return

                    # Get image, store in memory
                    async with aiohttp.ClientSession() as session:
                        async with session.get(file.url) as request:
                            image_data = BytesIO()

                            async for chunk in request.content.iter_chunked(8192):
                                image_data.write(chunk)

                            image_data.seek(0)

                        resized_image_data, new_size = await asyncio.to_thread(
                            self._resize_image,
                            image_data=image_data,
                            width=target_x,
                            height=target_y,
                            format=os.path.splitext(file.filename)[1][1:],
                        )

                        if (
                            new_size[0] > 10000 or new_size[1] > 10000
                        ):  # Check if image is too large
                            embed = discord.Embed(
                                title="Error",
                                description=f"The result of this operation is too large. Please ensure the result is smaller than 10000x10000. (current size: {new_size[0]}x{new_size[1]})",
                                color=Color.red(),
                            )
                            embed.set_footer(
                                text=f"@{interaction.user.name}",
                                icon_url=interaction.user.display_avatar.url,
                            )

                            await interaction.followup.send(
                                embed=embed, ephemeral=ephemeral
                            )
                            return

                        # Send resized image
                        embed = discord.Embed(
                            title="Image Resized",
                            description=f"**New Size: **`{new_size[0]}x{new_size[1]}`\n**Format: **`.{os.path.splitext(file.filename)[1][1:]}`",
                            color=Color.green(),
                        )
                        embed.set_footer(
                            text=f"@{interaction.user.name}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        if ephemeral:
                            embed.add_field(
                                name="Alert",
                                value="This message is ephemeral, so the image will expire after 1 view. To keep using the image and not lose it, please download it, then resend it.",
                                inline=False,
                            )
                        else:
                            embed.add_field(
                                name="Tip",
                                value="If the message shows `Only you can see this message` below, the image will expire after 1 view. To bypass this, please download the image, resend it, then star that. Run the command in a channel where you have permissions to avoid this.",
                                inline=False,
                            )

                        file_processed = discord.File(
                            fp=resized_image_data,
                            filename=f"titanium_image.{os.path.splitext(file.filename)[1][1:]}",
                            spoiler=spoiler,
                        )
                        embed.set_image(url=f"attachment://{file_processed.filename}")

                        await interaction.followup.send(
                            embed=embed, file=file_processed, ephemeral=ephemeral
                        )
                else:  # Check if both scale and target_x or target_y are set
                    embed = discord.Embed(
                        title="Error",
                        description="Please provide a scale, target width or target height.",
                        color=Color.red(),
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            else:  # If file is too large
                embed = discord.Embed(
                    title="Error",
                    description="Your file is too large. Please ensure it is smaller than 20MB.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:  # If file is not a static image
            embed = discord.Embed(
                title="Error",
                description="Your file is not a static image.",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    def _to_gif(
        self,
        image_data: BytesIO,
        mode: str,
    ) -> tuple[BytesIO, tuple[int, int]]:
        output_data = BytesIO()

        # Open image
        with Image.open(image_data) as im:
            if mode == "quality":
                with Image.open(image_data) as im2:
                    # Convert image to GIF
                    im.save(
                        output_data,
                        format="AVIF",
                        append_images=[im2],
                        save_all=True,
                        duration=500,
                        loop=0,
                    )
                    output_size = im.size
            else:
                # Convert to GIF with wand
                with WandImage(blob=image_data.getvalue()) as wand_image:
                    # Set GIF optimization options
                    wand_image.compression_quality = 80
                    wand_image.quantum_operator = "dither"

                    # Convert to GIF format
                    wand_image.format = "gif"

                    # Write to output BytesIO
                    output_data.write(wand_image.make_blob("gif"))

                    output_size = (wand_image.width, wand_image.height)

        output_data.seek(0)
        return output_data, output_size

    # Image to GIF command
    @imageGroup.command(name="to-gif", description="Convert an image to GIF.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(
        file="The static image to convert.",
        mode="The mode to use when generating the image.",
        spoiler="Optional: whether to send the image as a spoiler. Defaults to false.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(
                name="Quality (.avif, 16 million colours) (recommended)",
                value="quality",
            ),
            app_commands.Choice(
                name="Compatibility (.gif, limited colours) (not recommended)",
                value="compatibility",
            ),
        ]
    )
    async def gif_image(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        mode: app_commands.Choice[str] = None,
        spoiler: bool = False,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        if mode is None:
            mode = app_commands.Choice(
                name="Quality (.avif, 16 million colours) (recommended)",
                value="quality",
            )

        if (
            file.content_type.split("/")[0] == "image"
            and file.content_type.split("/")[1] != "gif"
            and file.content_type.split("/")[1] != "apng"
        ):  # Check if file is a static image
            if file.size < 20000000:  # 20MB file limit
                # Get image, store in memory
                async with aiohttp.ClientSession() as session:
                    async with session.get(file.url) as request:
                        image_data = BytesIO()

                        async for chunk in request.content.iter_chunked(8192):
                            image_data.write(chunk)

                        image_data.seek(0)

                output_data, output_size = await asyncio.to_thread(
                    self._to_gif,
                    image_data=image_data,
                    mode=mode.value,
                )

                # Send resized image
                embed = discord.Embed(
                    title="Image Converted",
                    description=f"**Size: **`{output_size[0]}x{output_size[1]}`\n**Format: **`.{'avif' if mode.value == 'quality' else 'gif'}`",
                    color=Color.green(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                if ephemeral:
                    embed.add_field(
                        name="Alert",
                        value="This message is ephemeral, so the image will expire after 1 view. To keep using the image and not lose it, please download it, then resend it.",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="Tip",
                        value="If the message shows `Only you can see this message` below, the image will expire after 1 view. To bypass this, please download the image, resend it, then star that. Run the command in a channel where you have permissions to avoid this.",
                        inline=False,
                    )

                file_processed = discord.File(
                    fp=output_data,
                    filename=f"titanium_image.{'avif' if mode.value == 'quality' else 'gif'}",
                    spoiler=spoiler,
                )

                await interaction.followup.send(
                    embed=embed, file=file_processed, ephemeral=ephemeral
                )
            else:  # If file is too large
                embed = discord.Embed(
                    title="Error",
                    description="Your file is too large. Please ensure it is smaller than 20MB.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        elif file.content_type.split("/")[0] == "video":  # If file is a video
            commands = await self.bot.tree.fetch_commands()

            for command in commands:
                if command.name == "video":
                    try:
                        if (
                            command.options[0].type
                            == discord.AppCommandOptionType.subcommand
                        ):
                            for option in command.options:
                                if option.name == "to-gif":
                                    mention = option.mention
                                    break
                    except IndexError:
                        pass

            embed = discord.Embed(
                title="Error",
                description=f"I think you attached a **video.** To convert a video to GIF, use the {mention} command.",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:  # If file is not a static image
            embed = discord.Embed(
                title="Error",
                description="Your file is not a static image.",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Image to GIF callback
    async def gif_callback(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        if message.attachments == []:
            await interaction.response.defer(ephemeral=True)

            embed = discord.Embed(
                title="Error",
                description="This message has no attachments.",
                color=Color.red(),
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.defer()

            converted = []
            fails = []

            for file in message.attachments:
                try:
                    if (
                        file.content_type.split("/")[0] == "image"
                        and file.content_type.split("/")[1] != "gif"
                        and file.content_type.split("/")[1] != "apng"
                    ):  # Check if file is a static image
                        if file.size < 20000000:  # 20MB file limit
                            # Get image, store in memory
                            async with aiohttp.ClientSession() as session:
                                async with session.get(file.url) as request:
                                    image_data = BytesIO()

                                    async for chunk in request.content.iter_chunked(
                                        8192
                                    ):
                                        image_data.write(chunk)

                                    image_data.seek(0)

                            output_data, output_size = await asyncio.to_thread(
                                self._to_gif,
                                image_data=image_data,
                                mode="quality",
                            )

                            # Add converted file to list
                            converted_file = discord.File(
                                fp=output_data, filename="titanium_image.avif"
                            )
                            converted.append(converted_file)
                        else:  # If file is too large
                            fails.append(
                                f"**{file.filename}** - too large (limit: 20MB, actual: {file.size * 1000000}MB)"
                            )
                    else:  # If file is not a static image
                        fails.append(f"**{file.filename}** - not a static image")
                except Exception:
                    fails.append(f"**{file.filename}** - error during conversion")

            # Show fail messages if present
            if fails != []:
                embed = discord.Embed(
                    title="Fails", description="\n".join(fails), color=Color.red()
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                if converted != []:
                    await interaction.followup.send(embed=embed, files=converted)
                else:
                    await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(files=converted)

    def _deepfry_image(
        self,
        image_data: BytesIO,
        intensity_scale: float,
        red_filter: bool,
    ) -> tuple[BytesIO, tuple[int, int]]:
        # Open image
        with Image.open(image_data) as img:
            # Crediit: https://github.com/Ovyerus/deeppyer
            # MIT Licence - https://github.com/Ovyerus/deeppyer/blob/master/LICENSE

            # Deepfry image
            img = img.convert("RGB")
            width, height = img.width, img.height
            img = img.resize(
                (int(width**0.75), int(height**0.75)), resample=Image.LANCZOS
            )
            img = img.resize(
                (int(width**0.88), int(height**0.88)), resample=Image.BILINEAR
            )
            img = img.resize(
                (int(width**0.9), int(height**0.9)), resample=Image.BICUBIC
            )
            img = img.resize((width, height), resample=Image.BICUBIC)
            img = ImageOps.posterize(img, 4)

            # Generate colour overlay
            r = img.split()[0]
            r = ImageEnhance.Contrast(r).enhance(
                1.0 + intensity_scale
            )  # Scale from 1.0 to 2.0
            r = ImageEnhance.Brightness(r).enhance(
                1.0 + (0.5 * intensity_scale)
            )  # Scale from 1.0 to 1.5

            if red_filter:
                colours = ((254, 0, 2), (255, 255, 15))
                r = ImageOps.colorize(r, colours[0], colours[1])
            else:
                r = img.copy()

            # Blend scaled from 0 to 0.75
            img = Image.blend(img, r, 0.75 * intensity_scale)

            # Sharpness scaled from 1.0 to 100.0
            img = ImageEnhance.Sharpness(img).enhance(1.0 + (99.0 * intensity_scale))

            deepfried_data = BytesIO()

            # Save image
            img.save(deepfried_data, format="PNG")
            output_size = img.size

        deepfried_data.seek(0)
        return deepfried_data, output_size

    # Deepfry image command
    @imageGroup.command(name="deepfry", description="Deepfry an image.")
    @app_commands.describe(
        file="The static image to deepfry.",
        intensity="The intensity of the deepfry effect. (1% to 100%)",
        red_filter="Whether to apply a red filter to the image. (recommended: true)",
        spoiler="Optional: whether to send the image as a spoiler. Defaults to false.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 10)
    async def deepfry_image(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        intensity: app_commands.Range[int, 1, 100],
        red_filter: bool,
        spoiler: bool = False,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)
        intensity_scale = intensity / 100.0

        if (
            file.content_type.split("/")[0] == "image"
            and file.content_type.split("/")[1] != "gif"
            and file.content_type.split("/")[1] != "apng"
        ):  # Check if file is a static image
            if file.size < 20000000:  # 20MB file limit
                # Get image, store in memory
                async with aiohttp.ClientSession() as session:
                    async with session.get(file.url) as request:
                        image_data = BytesIO()

                        async for chunk in request.content.iter_chunked(8192):
                            image_data.write(chunk)

                        image_data.seek(0)

                deepfried_data, output_size = await asyncio.to_thread(
                    self._deepfry_image,
                    image_data=image_data,
                    intensity_scale=intensity_scale,
                    red_filter=red_filter,
                )

                # Send resized image
                embed = discord.Embed(
                    title="Image Deepfried",
                    description=f"**Size: **`{output_size[0]}x{output_size[1]}`\n**Format: **`.png`",
                    color=Color.green(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                if ephemeral:
                    embed.add_field(
                        name="Alert",
                        value="This message is ephemeral, so the image will expire after 1 view. To keep using the image and not lose it, please download it, then resend it.",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="Tip",
                        value="If the message shows `Only you can see this message` below, the image will expire after 1 view. To bypass this, please download the image, resend it, then star that. Run the command in a channel where you have permissions to avoid this.",
                        inline=False,
                    )

                file_processed = discord.File(
                    fp=deepfried_data,
                    filename="titanium_image.png",
                    spoiler=spoiler,
                )
                embed.set_image(url=f"attachment://{file_processed.filename}")

                await interaction.followup.send(
                    embed=embed, file=file_processed, ephemeral=ephemeral
                )
            else:  # If file is too large
                embed = discord.Embed(
                    title="Error",
                    description="Your file is too large. Please ensure it is smaller than 20MB.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:  # If file is not a static image
            embed = discord.Embed(
                title="Error",
                description="Your file is not a static image.",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Deepfry callback
    async def deepfry_callback(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        if message.attachments == []:
            await interaction.response.defer(ephemeral=True)

            embed = discord.Embed(
                title="Error",
                description="This message has no attachments.",
                color=Color.red(),
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.defer()

            converted = []
            fails = []

            for file in message.attachments:
                try:
                    if (
                        file.content_type.split("/")[0] == "image"
                        and file.content_type.split("/")[1] != "gif"
                        and file.content_type.split("/")[1] != "apng"
                    ):  # Check if file is a static image
                        if file.size < 20000000:  # 20MB file limit
                            # Get image, store in memory
                            async with aiohttp.ClientSession() as session:
                                async with session.get(file.url) as request:
                                    image_data = BytesIO()

                                    async for chunk in request.content.iter_chunked(
                                        8192
                                    ):
                                        image_data.write(chunk)

                                    image_data.seek(0)

                            deepfried_data, output_size = await asyncio.to_thread(
                                self._deepfry_image,
                                image_data=image_data,
                                intensity_scale=1.0,
                                red_filter=True,
                            )

                            # Add converted file to list
                            converted_file = discord.File(
                                fp=deepfried_data,
                                filename="titanium_image.png",
                            )
                            converted.append(converted_file)
                        else:  # If file is too large
                            fails.append(
                                f"**{file.filename}** - too large (limit: 20MB, actual: {file.size * 1000000}MB)"
                            )
                    else:  # If file is not a static image
                        fails.append(f"**{file.filename}** - not a static image")
                except Exception:
                    fails.append(f"**{file.filename}** - error during conversion")

            # Show fail messages if present
            if fails != []:
                embed = discord.Embed(
                    title="Fails", description="\n".join(fails), color=Color.red()
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                if converted != []:
                    await interaction.followup.send(embed=embed, files=converted)
                else:
                    await interaction.followup.send(embed=embed)
            else:
                if converted != []:
                    await interaction.followup.send(files=converted)
                else:
                    embed = discord.Embed(
                        title="Done",
                        description="No images to convert.",
                        color=Color.red(),
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.followup.send(embed=embed)

    def _speech_bubble_image(
        self,
        image_data: BytesIO,
        colour: str,
        direction: str,
        format: str,
    ) -> tuple[BytesIO, tuple[int, int]]:
        output_data = BytesIO()

        # Open image
        with Image.open(image_data) as im:
            im = im.convert("RGBA")

            # Open speech bubble image
            with Image.open(os.path.join("content", "speech.png")) as bubble:
                bubble = bubble.convert("RGBA")
                bubble = bubble.resize(im.size, Image.Resampling.LANCZOS)

                if direction == "left":  # Flip bubble image if left selected
                    bubble = bubble.transpose(Image.FLIP_LEFT_RIGHT)

                if colour == "black":  # Invert if black selected
                    bubble_a = bubble.getchannel("A")
                    bubble = bubble.convert("RGB")  # Convert to RGB for invert

                    bubble = ImageOps.invert(bubble)
                    bubble.putalpha(bubble_a)

                if colour == "transparent":
                    # Subtract bubble shape from image
                    output_image = ImageChops.subtract_modulo(im, bubble)

                    with Image.open(
                        os.path.join("content", "speech_border.png")
                    ) as bubble_border:
                        # Add speech bubble border
                        bubble_border = bubble_border.convert("RGBA")
                        bubble_border = bubble_border.resize(
                            im.size, Image.Resampling.LANCZOS
                        )

                        # Make border white
                        bubble_border_a = bubble_border.getchannel("A")
                        bubble_border = bubble_border.convert(
                            "RGB"
                        )  # Convert to RGB for invert

                        bubble_border = ImageOps.invert(bubble_border)
                        bubble_border.putalpha(bubble_border_a)

                        if direction == "left":
                            bubble_border = bubble_border.transpose(
                                Image.FLIP_LEFT_RIGHT
                            )

                        output_image.paste(bubble_border, (0, 0), bubble_border)

                    if format == "AVIF":
                        # Save image to AVIF
                        output_image.save(
                            output_data,
                            format="AVIF",
                            append_images=[output_image],
                            save_all=True,
                            duration=500,
                            loop=0,
                        )
                        output_size = output_image.size
                    elif format == "GIF":
                        output_data_temp = BytesIO()

                        # Save image as PNG temporarily
                        output_image.save(output_data_temp, format="PNG")

                        # Convert to GIF
                        output_data_temp.seek(0)
                        with WandImage(blob=output_data_temp.getvalue()) as wand_image:
                            # Set GIF optimization options
                            wand_image.compression_quality = 80
                            wand_image.quantum_operator = "dither"

                            # Convert to GIF format
                            wand_image.format = "gif"

                            # Write to output BytesIO
                            output_data.write(wand_image.make_blob("gif"))

                            output_size = (wand_image.width, wand_image.height)
                    else:
                        # Save image
                        output_image.save(output_data, format="PNG")
                        output_size = output_image.size
                else:
                    with Image.new("RGBA", im.size) as output_image:
                        # Add speech bubble
                        output_image.paste(im, (0, 0))
                        output_image.paste(bubble, (0, 0), bubble.getchannel("A"))

                        if format == "AVIF":
                            # Save image to AVIF
                            output_image.save(
                                output_data,
                                format="AVIF",
                                append_images=[output_image],
                                save_all=True,
                                duration=500,
                                loop=0,
                            )
                            output_size = output_image.size
                        else:
                            # Save image
                            output_image.save(output_data, format=format)
                            output_size = output_image.size

        output_data.seek(0)
        return output_data, output_size

    # Speech bubble command
    @imageGroup.command(
        name="speechbubble", description="Add a speech bubble overlay to an image."
    )
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(
        file="The static image to use.",
        colour="The colour of the speech bubble.",
        direction="The direction of the speech bubble.",
        format="The format of the output image.",
        spoiler="Optional: whether to send the image as a spoiler. Defaults to false.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.choices(
        colour=[
            app_commands.Choice(
                name="White",
                value="white",
            ),
            app_commands.Choice(
                name="Black",
                value="black",
            ),
            app_commands.Choice(
                name="Transparent",
                value="transparent",
            ),
        ],
        direction=[
            app_commands.Choice(
                name="Left",
                value="left",
            ),
            app_commands.Choice(
                name="Right",
                value="right",
            ),
        ],
        format=[
            app_commands.Choice(
                name=".png (can't be favourited, very good quality)",
                value="PNG",
            ),
            app_commands.Choice(
                name=".gif (can be favourited, bad quality, best compatibility)",
                value="GIF",
            ),
            app_commands.Choice(
                name=".avif (can be favourited, very good quality)",
                value="AVIF",
            ),
        ],
    )
    async def speech_bubble(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        colour: app_commands.Choice[str],
        direction: app_commands.Choice[str],
        format: app_commands.Choice[str],
        spoiler: bool = False,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        if (
            file.content_type.split("/")[0] == "image"
            and file.content_type.split("/")[1] != "gif"
            and file.content_type.split("/")[1] != "apng"
        ):  # Check if file is a static image
            if file.size < 20000000:  # 20MB file limit
                # Get image, store in memory
                async with aiohttp.ClientSession() as session:
                    async with session.get(file.url) as request:
                        image_data = BytesIO()

                        async for chunk in request.content.iter_chunked(8192):
                            image_data.write(chunk)

                        image_data.seek(0)

                output_data, output_size = await asyncio.to_thread(
                    self._speech_bubble_image,
                    image_data=image_data,
                    colour=colour.value,
                    direction=direction.value,
                    format=format.value,
                )

                # Send resized image
                embed = discord.Embed(
                    title="Image Generated",
                    description=f"**Size: **`{output_size[0]}x{output_size[1]}`\n**Format: **`.{format.value.lower()}`",
                    color=Color.green(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                if ephemeral:
                    embed.add_field(
                        name="Alert",
                        value="This message is ephemeral, so the image will expire after 1 view. To keep using the image and not lose it, please download it, then resend it.",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="Tip",
                        value="If the message shows `Only you can see this message` below, the image will expire after 1 view. To bypass this, please download the image, resend it, then star that. Run the command in a channel where you have permissions to avoid this.",
                        inline=False,
                    )

                file_processed = discord.File(
                    fp=output_data,
                    filename=f"titanium_image.{format.value.lower()}",
                    spoiler=spoiler,
                )

                await interaction.followup.send(
                    embed=embed, file=file_processed, ephemeral=ephemeral
                )
            else:  # If file is too large
                embed = discord.Embed(
                    title="Error",
                    description="Your file is too large. Please ensure it is smaller than 20MB.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:  # If file is not a static image
            embed = discord.Embed(
                title="Error",
                description="Your file is not a static image.",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    def _convert_image(
        self,
        image_data: BytesIO,
        format: str,
    ) -> tuple[BytesIO, tuple[int, int]]:
        output_data = BytesIO()

        if format == "GIF":
            # Convert to GIF with wand
            with WandImage(blob=image_data.getvalue()) as wand_image:
                # Set GIF optimization options
                wand_image.compression_quality = 80
                wand_image.quantum_operator = "dither"

                # Convert to GIF format
                wand_image.format = "gif"

                # Write to output BytesIO
                output_data.write(wand_image.make_blob("gif"))

                output_size = (wand_image.width, wand_image.height)
        else:
            # Convert with pillow
            with Image.open(image_data) as im:
                im.save(output_data, format=format)
                output_size = im.size

        output_data.seek(0)
        return output_data, output_size

    # Convert image command
    @imageGroup.command(
        name="convert", description="Convert an image to a different format."
    )
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(
        file="The image to convert.",
        format="The format of the output image.",
        spoiler="Optional: whether to send the image as a spoiler. Defaults to false.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(
                name=".jpg / .jpeg",
                value="JPEG",
            ),
            app_commands.Choice(
                name=".png",
                value="PNG",
            ),
            app_commands.Choice(
                name=".webp",
                value="WEBP",
            ),
            app_commands.Choice(
                name=".gif",
                value="GIF",
            ),
            app_commands.Choice(
                name=".avif",
                value="AVIF",
            ),
            app_commands.Choice(
                name=".bmp",
                value="BMP",
            ),
            app_commands.Choice(
                name=".tiff",
                value="TIFF",
            ),
        ],
    )
    async def convert_image(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        format: app_commands.Choice[str],
        spoiler: bool = False,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        if file.content_type.split("/")[0] == "image":  # Check if file is an image
            if file.size < 20000000:  # 20MB file limit
                # Get image, store in memory
                async with aiohttp.ClientSession() as session:
                    async with session.get(file.url) as request:
                        image_data = BytesIO()

                        async for chunk in request.content.iter_chunked(8192):
                            image_data.write(chunk)

                        image_data.seek(0)

                output_data, output_size = await asyncio.to_thread(
                    self._convert_image,
                    image_data=image_data,
                    format=format.value,
                )

                # Send resized image
                embed = discord.Embed(
                    title="Image Converted",
                    description=f"**Size: **`{output_size[0]}x{output_size[1]}`\n**Format: **`.{format.value.lower()}`",
                    color=Color.green(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                if ephemeral:
                    embed.add_field(
                        name="Alert",
                        value="This message is ephemeral, so the image will expire after 1 view. To keep using the image and not lose it, please download it, then resend it.",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="Tip",
                        value="If the message shows `Only you can see this message` below, the image will expire after 1 view. To keep using the image and not lose it, please download it, then resend it.",
                        inline=False,
                    )

                file_processed = discord.File(
                    fp=output_data,
                    filename=f"titanium_image.{format.value.lower()}",
                    spoiler=spoiler,
                )

                await interaction.followup.send(
                    embed=embed, file=file_processed, ephemeral=ephemeral
                )
            else:  # If file is too large
                embed = discord.Embed(
                    title="Error",
                    description="Your file is too large. Please ensure it is smaller than 20MB.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:  # If file is not an image
            embed = discord.Embed(
                title="Error",
                description="Your file is not an image.",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(Images(bot))
