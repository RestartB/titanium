# pylint: disable=no-member

import os
from io import BytesIO
import aiohttp

import discord
from discord import Color, app_commands
from discord.ext import commands
from PIL import Image, ImageEnhance, ImageOps


# noinspection PyTypeChecker
class Images(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot: commands.Bot

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

    # Image Resize command
    @imageGroup.command(name="resize", description="Resize an image.")
    @app_commands.describe(
        target_x="Set a target width for the image. Defaults to the original length."
    )
    @app_commands.describe(
        target_y="Set a target height for the image. Defaults to the original length."
    )
    @app_commands.describe(
        scale="Scale the resolution by a certain amount. Overrides target_x and target_y if set."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 20)
    async def resize_image(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        scale: float = None,
        target_x: int = None,
        target_y: int = None,
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

                            async for chunk in request.content.iter_chunked(10):
                                image_data.write(chunk)

                            image_data.seek(0)

                    # Open image
                    with Image.open(image_data) as im:
                        # Resize image
                        resized_image = im.resize((int(target_x), int(target_y)))

                        resized_image_data = BytesIO()

                        # Save resized image
                        resized_image.save(resized_image_data)
                        resized_image_data.seek(0)

                        new_size = resized_image.size

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
                            description=f"Image resized to {new_size[0]}x{new_size[1]}.",
                            color=Color.green(),
                        )
                        embed.set_footer(
                            text=f"@{interaction.user.name}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        file_processed = discord.File(
                            fp=resized_image_data,
                            filename="image.png",
                        )
                        embed.set_image(url="attachment://image.png")

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

    # Image to GIF command
    @imageGroup.command(name="to-gif", description="Convert an image to GIF.")
    @app_commands.checks.cooldown(1, 10)
    async def gif_image(
        self, interaction: discord.Interaction, file: discord.Attachment
    ):
        await interaction.response.defer()

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

                        async for chunk in request.content.iter_chunked(10):
                            image_data.write(chunk)

                        image_data.seek(0)

                # Open image
                with Image.open(image_data) as im:
                    gif_data = BytesIO()

                    # Convert image to GIF
                    im.save(gif_data, format="GIF")
                    gif_data.seek(0)

                    # Send resized image
                    embed = discord.Embed(
                        title="Image Converted",
                        description="Image converted to GIF.",
                        color=Color.green(),
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    file_processed = discord.File(fp=gif_data, filename="image.gif")
                    embed.set_image(url="attachment://image.gif")

                    await interaction.followup.send(embed=embed, file=file_processed)
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

                await interaction.followup.send(embed=embed)
        elif file.content_type.split("/")[0] == "video":  # If file is a video
            embed = discord.Embed(
                title="Error",
                description="I think you attached a **video.** To convert a video to GIF, use the `/video to-gif` command.",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed)
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

            await interaction.followup.send(embed=embed)

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

                                    async for chunk in request.content.iter_chunked(10):
                                        image_data.write(chunk)

                                    image_data.seek(0)

                            # Open image
                            with Image.open(image_data) as im:
                                gif_data = BytesIO()

                                # Convert image to GIF
                                im.save(gif_data, format="GIF")
                                gif_data.seek(0)

                                # Add converted file to list
                                converted_file = discord.File(
                                    fp=gif_data, filename="image.gif"
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

            # Remove temporary files
            for file in converted:
                os.remove(os.path.join("tmp", file.filename))

    # Image to GIF command
    @imageGroup.command(name="deepfry", description="Deepfry an image.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 10)
    async def deepfry_image(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
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

                        async for chunk in request.content.iter_chunked(10):
                            image_data.write(chunk)

                        image_data.seek(0)

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
                    r = ImageEnhance.Contrast(r).enhance(2.0)
                    r = ImageEnhance.Brightness(r).enhance(1.5)

                    colours = ((254, 0, 2), (255, 255, 15))
                    r = ImageOps.colorize(r, colours[0], colours[1])

                    # Overlay red and yellow onto main image and sharpen
                    img = Image.blend(img, r, 0.75)
                    img = ImageEnhance.Sharpness(img).enhance(100.0)

                    deepfried_data = BytesIO()

                    # Save image
                    img.save(deepfried_data, format="PNG")
                    deepfried_data.seek(0)

                # Send resized image
                embed = discord.Embed(
                    title="Done", description="Image deepfried.", color=Color.green()
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                file_processed = discord.File(
                    fp=deepfried_data,
                    filename="image.png",
                )
                embed.set_image(url="attachment://image.png")

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

                                    async for chunk in request.content.iter_chunked(10):
                                        image_data.write(chunk)

                                    image_data.seek(0)

                            # Open image
                            with Image.open(image_data) as img:
                                # Crediit: https://github.com/Ovyerus/deeppyer
                                # MIT Licence - https://github.com/Ovyerus/deeppyer/blob/master/LICENSE

                                # Deepfry image
                                img = img.convert("RGB")
                                width, height = img.width, img.height
                                img = img.resize(
                                    (int(width**0.75), int(height**0.75)),
                                    resample=Image.LANCZOS,
                                )
                                img = img.resize(
                                    (int(width**0.88), int(height**0.88)),
                                    resample=Image.BILINEAR,
                                )
                                img = img.resize(
                                    (int(width**0.9), int(height**0.9)),
                                    resample=Image.BICUBIC,
                                )
                                img = img.resize(
                                    (width, height), resample=Image.BICUBIC
                                )
                                img = ImageOps.posterize(img, 4)

                                # Generate colour overlay
                                r = img.split()[0]
                                r = ImageEnhance.Contrast(r).enhance(2.0)
                                r = ImageEnhance.Brightness(r).enhance(1.5)

                                colours = ((254, 0, 2), (255, 255, 15))
                                r = ImageOps.colorize(r, colours[0], colours[1])

                                # Overlay red and yellow onto main image and sharpen
                                img = Image.blend(img, r, 0.75)
                                img = ImageEnhance.Sharpness(img).enhance(100.0)

                                deepfried_data = BytesIO()

                                # Save image
                                img.save(deepfried_data, format="PNG")
                                deepfried_data.seek(0)

                                # Add converted file to list
                                converted_file = discord.File(
                                    fp=deepfried_data,
                                    filename="image.png",
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

            # Remove temporary files
            for file in converted:
                os.remove(os.path.join("tmp", file.filename))


async def setup(bot):
    await bot.add_cog(Images(bot))
