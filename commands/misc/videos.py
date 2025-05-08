# pylint: disable=no-member

import asyncio
import os
import tempfile
from typing import TYPE_CHECKING

import discord
from discord import Color, app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


class Videos(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=True, private_channel=True
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    videoGroup = app_commands.Group(
        name="video",
        description="Manipulate videos.",
        allowed_contexts=context,
        allowed_installs=installs,
    )

    # Video to GIF command
    @videoGroup.command(name="to-gif", description="Convert a video to WEBP or GIF.")
    @app_commands.choices(
        mode=[
            app_commands.Choice(
                name="High FPS (.webp, 10 seconds max, unlimited FPS) (recommended)",
                value="fps",
            ),
            app_commands.Choice(
                name="Length (.webp, 30 seconds max, 20FPS max)", value="length"
            ),
            app_commands.Choice(
                name="Compatibility (.gif, 10 seconds max, 10FPS max) (not recommended)",
                value="compatibility",
            ),
        ]
    )
    @app_commands.describe(file="The file to convert.")
    @app_commands.describe(
        mode="Optional: the mode to use when converting. Defaults to high FPS.",
        spoiler="Optional: whether to send the image as a spoiler. Defaults to false.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 20)
    async def video_to_gif(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        mode: app_commands.Choice[str] = None,
        spoiler: bool = False,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        # If mode is None, create a default Choice object
        if mode is None:
            mode = app_commands.Choice(
                name="High FPS (.webp, 10 seconds max, unlimited FPS) (recommended)",
                value="fps",
            )

        if file.content_type.split("/")[0] == "video":  # Check if file is a video
            if file.size < 50000000:  # 20MB file limit
                # Send resized image
                embed = discord.Embed(
                    title="Converting...",
                    description=f"{self.bot.options['loading-emoji']} Downloading your video to convert...",
                    color=Color.orange(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)

                with tempfile.NamedTemporaryFile(
                    "wb", suffix=os.path.splitext(file.filename)[1], dir="tmp"
                ) as tmp_input:
                    # Save file to /tmp
                    # noinspection PyTypeChecker
                    await file.save(tmp_input.file)

                    # Send converting message
                    embed = discord.Embed(
                        title="Converting...",
                        description=f"{self.bot.options['loading-emoji']} Converting your video...",
                        color=Color.orange(),
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.edit_original_response(embed=embed)

                    with tempfile.NamedTemporaryFile(
                        "wb",
                        suffix=(".gif" if mode.value == "compatibility" else ".webp"),
                        dir="tmp",
                    ) as tmp_output:
                        if mode.value == "compatibility":
                            # Run ffmpeg to convert to GIF, cap length at 10s
                            proc = await asyncio.create_subprocess_exec(
                                "ffmpeg",
                                "-t",
                                "10",
                                "-i",
                                tmp_input.name,
                                "-vf",
                                "fps=10,scale=400:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                                "-loop",
                                "0",
                                "-y",
                                tmp_output.name,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                        else:
                            # Run ffmpeg to convert to WEBP
                            proc = await asyncio.create_subprocess_exec(
                                "ffmpeg",
                                "-t",
                                "10" if mode.value == "fps" else "30",
                                "-i",
                                tmp_input.name,
                                "-vcodec",
                                "libwebp",
                                "-vf",
                                f"{'fps=20,' if mode.value == 'length' else ''}scale=400:-1:flags=lanczos",
                                "-lossless",
                                "1",
                                "-loop",
                                "0",
                                "-preset",
                                "default",
                                "-an",
                                "-y",
                                tmp_output.name,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )

                        # Wait for ffmpeg to finish
                        stdout, stderr = await proc.communicate()

                        if proc.returncode == 0:
                            # Send resized image
                            embed = discord.Embed(
                                title="Converting...",
                                description=f"{self.bot.options['loading-emoji']} Sending the converted file...",
                                color=Color.orange(),
                            )
                            embed.set_footer(
                                text=f"@{interaction.user.name}",
                                icon_url=interaction.user.display_avatar.url,
                            )

                            await interaction.edit_original_response(embed=embed)

                            # Send resized image
                            embed = discord.Embed(
                                title="Video Converted",
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
                                fp=tmp_output.name,
                                filename=f"titanium_image.{'gif' if mode.value == 'compatibility' else 'webp'}",
                                spoiler=spoiler,
                            )

                            await interaction.edit_original_response(
                                embed=embed, attachments=[file_processed]
                            )
                        else:
                            raise Exception(
                                f"ffmpeg failed with code {proc.returncode}:\n\n{stderr.decode()}"
                            )
            else:  # If file is too large
                embed = discord.Embed(
                    title="Error",
                    description="Your file is too large. Please ensure it is smaller than 50MB.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        elif file.content_type.split("/")[0] == "image":  # If file is an image
            commands = await self.bot.tree.fetch_commands()

            for command in commands:
                if command.name == "image":
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
                description=f"I think you attached an **image.** To convert an image to GIF, use the {mention} command, or right click on a message, select apps, then click **Convert to GIF.**",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:  # If file is not a video
            embed = discord.Embed(
                title="Error",
                description="Your file is not a video.",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(Videos(bot))
