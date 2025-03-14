# pylint: disable=no-member

import os
import random
import string
import asyncio

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
    @videoGroup.command(
        name="to-gif", description="Convert a video to GIF up to 10 seconds long."
    )
    @app_commands.checks.cooldown(1, 30)
    async def video_to_gif(
        self, interaction: discord.Interaction, file: discord.Attachment
    ):
        await interaction.response.defer()

        if file.content_type.split("/")[0] == "video":  # Check if file is a video
            if file.size < 20000000:  # 20MB file limit
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

                await interaction.followup.send(embed=embed)

                while True:
                    # Generate random filename
                    letters = string.ascii_lowercase
                    filename = "".join(random.choice(letters) for i in range(8))

                    if not os.path.exists(
                        os.path.join(
                            "tmp", f"{filename}.{file.content_type.split('/')[-1]}"
                        )
                    ):
                        break

                try:
                    # Save file to /tmp
                    # noinspection PyTypeChecker
                    await file.save(
                        os.path.join(
                            "tmp", f"{filename}.{file.content_type.split('/')[-1]}"
                        )
                    )

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

                    # Save file to /tmp
                    input_path = os.path.join(
                        os.getcwd(),
                        "tmp",
                        f"{filename}.{file.content_type.split('/')[-1]}",
                    )
                    output_path = os.path.join(
                        os.getcwd(), "tmp", f"{filename}_processed.gif"
                    )

                    # Run ffmpeg to convert to GIF, cap length at 10s
                    proc = await asyncio.create_subprocess_exec(
                        "ffmpeg",
                        "-t",
                        "10",
                        "-i",
                        input_path,
                        "-vf",
                        "fps=10,scale=320:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                        "-loop",
                        "0",
                        output_path,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    # Wait for ffmpeg to finish
                    stdout, stderr = await proc.communicate()

                    if proc.returncode == 0:
                        # Send resized image
                        embed = discord.Embed(
                            title="Video Converted",
                            description="Video converted to GIF.",
                            color=Color.green(),
                        )
                        embed.set_footer(
                            text=f"@{interaction.user.name}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        file_processed = discord.File(
                            fp=os.path.join("tmp", f"{filename}_processed.gif"),
                            filename=f"{filename}_processed.gif",
                        )
                        embed.set_image(url=f"attachment://{filename}_processed.gif")

                        await interaction.edit_original_response(
                            embed=embed, attachments=[file_processed]
                        )
                    else:
                        raise Exception(
                            f"ffmpeg failed with code {proc.returncode}:\n\n{stderr.decode()}"
                        )
                finally:
                    # Delete temporary files
                    os.remove(os.path.join("tmp", f"{filename}_processed.gif"))
                    os.remove(
                        os.path.join(
                            "tmp", f"{filename}.{file.content_type.split('/')[-1]}"
                        )
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

                await interaction.followup.send(embed=embed)
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

            await interaction.followup.send(embed=embed)
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

            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Videos(bot))
