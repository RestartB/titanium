import datetime
import platform
import time
from datetime import timedelta
from typing import TYPE_CHECKING

import cpuinfo
import psutil
from discord import Colour, Embed, Emoji, app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


class BasicCommandsCog(commands.Cog, name="Basic", description="General bot commands."):
    """Basic commands."""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    def websocket_emoji_select(self, latency: float) -> Emoji | str:
        if latency < 0.3:
            return self.bot.success_emoji
        elif 0.3 <= latency < 0.8:
            return self.bot.warn_emoji
        else:
            return self.bot.error_emoji

    def api_emoji_select(self, latency: float) -> Emoji | str:
        if latency < 0.5:
            return self.bot.success_emoji
        elif 0.5 <= latency < 1:
            return self.bot.warn_emoji
        else:
            return self.bot.error_emoji

    @commands.hybrid_command(name="ping", description="Get the bot's ping.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def ping(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        embed = Embed(
            title="🏓 Pong!",
            description=(
                f"{self.websocket_emoji_select(self.bot.latency)} **Websocket latency:** `{self.bot.latency * 1000:.2f}ms`\n"
                f"{self.api_emoji_select(self.bot.api_latency)} **API latency:** `{self.bot.api_latency * 1000:.2f}ms`"
                "\n\nIs ping high or is the bot running slow? Check the [status page](https://titaniumbot.me/status) or join the [support server](https://titaniumbot.me/server) for help!"
            ),
            colour=Colour.green(),
        )
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    @commands.hybrid_command(
        name="info", description="Get information about the bot.", aliases=["about"]
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def info(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        embed = Embed(
            title="Titanium",
            description="This is a development version of Titanium. For more information, please go to https://github.com/RestartB/titanium/tree/v2.",
            colour=Colour.light_gray(),
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url if self.bot.user else None)
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    # Host Info command
    @commands.hybrid_command(name="host-info", description="Info about the bot host.")
    @commands.cooldown(1, 5)
    async def host_info(self, ctx: commands.Context["TitaniumBot"]):
        await ctx.defer()

        embed = Embed(title="Host Info")

        uptime_seconds = int(time.time() - psutil.boot_time())
        sec = timedelta(seconds=uptime_seconds)
        d = datetime.datetime(1, 1, 1) + sec

        sysinfo = cpuinfo.get_cpu_info()

        embed.add_field(name="Python Version", value=f"`{sysinfo['python_version']}`")
        embed.add_field(
            name="System Uptime",
            value=f"`{(d.day - 1):02d}:{d.hour:02d}:{d.minute:02d}:{d.second:02d}`",
        )
        embed.add_field(
            name="Operating System", value=f"`{platform.system()} {platform.release()}`"
        )
        embed.add_field(name="CPU Name", value=f"`{sysinfo['brand_raw']}`")
        embed.add_field(name="CPU Usage", value=f"`{psutil.cpu_percent()}%`")
        embed.add_field(
            name="System RAM Usage",
            value=f"`{psutil.virtual_memory().percent}%` (`{psutil.virtual_memory().used / 1000000:.2f}MB` used, `{psutil.virtual_memory().total / 1000000:.2f}MB` total)",
        )

        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="prefixes", description="Get the bot's command prefixes.")
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def prefixes(self, ctx: commands.Context["TitaniumBot"]) -> None:
        if not ctx.guild or not self.bot.user:
            return

        await ctx.defer()

        prefix_str = ""
        if self.bot.guild_prefixes.get(ctx.guild.id):
            for i, prefix in enumerate(self.bot.guild_prefixes[ctx.guild.id].prefixes):
                if i == 0:
                    prefix_str = f"`{prefix}`"
                    continue

                prefix_str += f", `{prefix}`"
        else:
            prefix_str = "`t!`"

        prefix_str = prefix_str + (
            f", {self.bot.user.mention}" if prefix_str else self.bot.user.mention
        )

        embed = Embed(
            title="Command Prefixes",
            description=prefix_str,
            colour=Colour.green(),
        )

        embed.set_author(
            name=ctx.guild.name,
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        await ctx.reply(embed=embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(BasicCommandsCog(bot))
