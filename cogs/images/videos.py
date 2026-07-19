import asyncio
from io import BytesIO
from typing import TYPE_CHECKING, Literal

import discord
from discord import Attachment, Colour, app_commands
from discord.ext import commands

from lib.helpers.hybrid import defer, handle_group_command_not_found
from lib.helpers.log_error import log_error

if TYPE_CHECKING:
    from main import TitaniumBot


class VideoCog(commands.Cog, name="Videos", description="Video processing commands."):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

    def _get_output_filename(
        self, attachment: Attachment, output_format: Literal["gif", "webp"]
    ) -> str:
        """Generate output filename safely handling files with or without extensions."""
        filename = (
            attachment.filename.rsplit(".", 1)[0]
            if "." in attachment.filename
            else attachment.filename
        )
        return f"titanium_{filename}.{output_format.lower()}"

    @commands.hybrid_group(
        name="video",
        aliases=["videos"],
        description="Video processing commands.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def video_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        handle_group_command_not_found(ctx)

    @video_group.command(
        name="gif",
        description="Convert a video to GIF. Max 20MB, 10s, 15 FPS.",
        aliases=["to-gif", "togif"],
    )
    @app_commands.describe(
        video="The video to convert to GIF.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def gif_video(
        self, ctx: commands.Context["TitaniumBot"], video: Attachment, ephemeral: bool = False
    ) -> None:
        """Convert a video to GIF."""

        if not video.content_type or not video.content_type.startswith("video/"):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Invalid File",
                colour=Colour.red(),
            )

            if video.content_type and video.content_type.startswith("image/"):
                embed.description = f"Please upload a video. To manipulate images, use the `{ctx.clean_prefix}image` commands."
            else:
                embed.description = "Please upload a video."

            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        if video.size > 20_000_000:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Video Too Big",
                description="Your video is too big. Please ensure that your source video is less than `20MB`.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        async with defer(ctx, ephemeral=ephemeral):
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-t",
                "10",
                "-i",
                video.url,
                "-vf",
                "fps=15,scale=400:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                "-loop",
                "0",
                "-f",
                "gif",
                "pipe:1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_data, stderr_data = await proc.communicate()

            if proc.returncode != 0:
                await log_error(
                    bot=self.bot,
                    module="Videos",
                    error="Failed to convert video to GIF",
                    details=stderr_data.decode("utf-8"),
                    guild_id=None,
                )

                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Error",
                    description="Failed to convert your video. Please try again later.",
                    colour=Colour.red(),
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            output_size = len(stdout_data)
            if output_size > 10_000_000:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Output Too Big",
                    description=f"The output is bigger than the Discord file limit (limit: `10MB`, output size: `{round(output_size / 1_000_000, 2)}MB`). Please try a smaller source video.",
                    colour=Colour.red(),
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            output_data = BytesIO(stdout_data)
            output_data.seek(0)

            file = discord.File(
                output_data,
                filename=self._get_output_filename(video, "gif"),
                spoiler=video.is_spoiler(),
            )
            await ctx.reply(file=file, ephemeral=ephemeral)

    @video_group.command(
        name="webp",
        description="Convert a video to WebP. Max 20MB, 20s, 30 FPS.",
        aliases=["to-webp", "towebp"],
    )
    @app_commands.describe(
        video="The video to convert to WebP.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @commands.cooldown(1, 5)
    async def webp_video(
        self, ctx: commands.Context["TitaniumBot"], video: Attachment, ephemeral: bool = False
    ) -> None:
        """Convert a video to WebP."""

        if not video.content_type or not video.content_type.startswith("video/"):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Invalid File",
                colour=Colour.red(),
            )

            if video.content_type and video.content_type.startswith("image/"):
                embed.description = f"Please upload a video. To manipulate images, use the `{ctx.clean_prefix}image` commands."
            else:
                embed.description = "Please upload a video."

            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        if video.size > 20_000_000:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Video Too Big",
                description="Your video is too big. Please ensure that your source video is less than `20MB`.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        async with defer(ctx):
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-t",
                "20",
                "-i",
                video.url,
                "-vcodec",
                "libwebp",
                "-vf",
                "fps=30,scale=400:-1:flags=lanczos",
                "-loop",
                "0",
                "-preset",
                "default",
                "-f",
                "webp",
                "pipe:1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_data, stderr_data = await proc.communicate()

            if proc.returncode != 0:
                await log_error(
                    bot=self.bot,
                    module="Videos",
                    error="Failed to convert video to WebP",
                    details=stderr_data.decode("utf-8"),
                    guild_id=None,
                )

                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Error",
                    description="Failed to convert your video. Please try again later.",
                    colour=Colour.red(),
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            output_size = len(stdout_data)
            if output_size > 10_000_000:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Output Too Big",
                    description=f"The output is bigger than the Discord file limit (limit: `10MB`, output size: `{round(output_size / 1_000_000, 2)}MB`). Please try a smaller source video.",
                    colour=Colour.red(),
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            # fix RIFF size header
            if output_size >= 12 and stdout_data[:4] == b"RIFF" and stdout_data[8:12] == b"WEBP":
                stdout_data = bytearray(stdout_data)
                stdout_data[4:8] = (output_size - 8).to_bytes(4, byteorder="little")
                stdout_data = bytes(stdout_data)

            output_data = BytesIO(stdout_data)
            output_data.seek(0)

            file = discord.File(
                output_data,
                filename=self._get_output_filename(video, "webp"),
                spoiler=video.is_spoiler(),
            )
            await ctx.reply(file=file, ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(VideoCog(bot))
