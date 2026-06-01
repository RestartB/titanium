import datetime
import os
import platform
import time
from datetime import timedelta
from typing import TYPE_CHECKING

import cpuinfo
import psutil
from discord import ButtonStyle, Colour, Embed, Emoji, __version__, app_commands
from discord.ext import commands
from discord.ui import Button, View

if TYPE_CHECKING:
    from main import TitaniumBot


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class BasicCommandsCog(
    commands.GroupCog, group_name="bot", description="General bot related commands."
):
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
        if latency == 0:
            return self.bot.error_emoji

        if latency < 0.5:
            return self.bot.success_emoji
        elif 0.5 <= latency < 1:
            return self.bot.warn_emoji
        else:
            return self.bot.error_emoji

    @commands.hybrid_command(name="ping", description="Get the bot's ping.")
    async def ping(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        embed = Embed(
            title="🏓 Pong!",
            description=(
                f"{self.websocket_emoji_select(self.bot.latency)} **Websocket latency:** `{self.bot.latency * 1000:.2f}ms`\n"
                f"{self.api_emoji_select(self.bot.api_latency)} **Discord API latency:** `{f'{self.bot.api_latency * 1000:.2f}ms' if self.bot.api_latency > 0 else 'Unavailable'}`"
                "\n\nIs ping high or is the bot running slow? Check the [status page](https://titanium.fyi/status) or join the [support server](https://titanium.fyi/server) for help."
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
    async def info(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        embed = Embed(
            title="About",
            description="Titanium is **your** multipurpose, open source Discord bot developed by **Restart**. "
            "It can operate as a traditional server bot, and as a user app, so your Discord experience can be enhanced in any server. "
            "Titanium includes the following powerful features (and more!) for free:\n\n"
            "- powerful moderation, automod and logging tools\n"
            "- bouncer system to monitor user profiles\n"
            "- leaderboard, starboard and confession systems to improve engagement\n"
            "- server wide quick response tags, or user specific tags that work in any server\n"
            "- web dashboard for easy management of your server's Titanium settings\n"
            "- utility, web search, image manipulation, fun and more commands that work in any server when you add Titanium to your account\n\n"
            "To add Titanium to your server or account, press the `Add App` button on Titanium's profile, or use the Add Bot link on Titanium's website!",
            colour=Colour.light_grey(),
        )
        embed.set_author(
            name="Titanium",
            url="https://titanium.fyi",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else "",
        )
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )
        embed.add_field(
            name="Links",
            value="**Website:** https://titanium.fyi\n**Dashboard:** https://dash.titanium.fyi\n**Support Server:** https://titanium.fyi/server\n**Privacy Policy:** https://titanium.fyi/privacy\n**Terms of Use:** https://titanium.fyi/terms",
        )

        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="invite", description="Get an invite link for the bot.")
    async def invite(self, ctx: commands.Context["TitaniumBot"]):
        embed = Embed(
            title=f"{ctx.bot.info_emoji} Invite",
            description="Use this invite to add Titanium to your account or server.",
            colour=Colour.light_grey(),
        )
        embed.add_field(name="Invite", value="https://titanium.fyi/invite")

        view = View()
        view.add_item(
            Button(
                label="Add Bot",
                style=ButtonStyle.url,
                url=f"https://discord.com/oauth2/authorize?client_id={ctx.me.id}",
            )
        )

        await ctx.reply(
            embed=embed,
            view=view
        )

    # Host Info command
    @commands.hybrid_command(
        name="host-info", aliases=["hostinfo"], description="Info about the bot host."
    )
    @commands.cooldown(1, 5)
    async def host_info(self, ctx: commands.Context["TitaniumBot"]):
        await ctx.defer()

        embed = Embed(title="Host Info")

        uptime_seconds = int(time.time() - psutil.boot_time())
        sec = timedelta(seconds=uptime_seconds)
        d = datetime.datetime(1, 1, 1) + sec

        sysinfo = cpuinfo.get_cpu_info()

        embed.add_field(name="Python Version", value=f"`{sysinfo['python_version']}`")
        embed.add_field(name="discord.py Version", value=f"`{__version__}`")
        embed.add_field(
            name="Operating System", value=f"`{platform.system()} {platform.release()}`"
        )

        embed.add_field(
            name="System Uptime",
            value=f"`{(d.day - 1):02d}:{d.hour:02d}:{d.minute:02d}:{d.second:02d}`",
        )
        embed.add_field(name="CPU Name", value=f"`{sysinfo['brand_raw']}`")
        embed.add_field(name="CPU Usage", value=f"`{psutil.cpu_percent()}%`")

        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        process_ram_mb = mem_info.rss / (1024 * 1024)

        embed.add_field(
            name="Process RAM Usage",
            value=f"`{process_ram_mb:.2f}MB`",
        )
        embed.add_field(
            name="System RAM Usage",
            value=f"`{psutil.virtual_memory().percent}%` (`{psutil.virtual_memory().used / (1024 * 1024):.2f}MB` used, `{psutil.virtual_memory().total / (1024 * 1024):.2f}MB` total)",
        )

        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    @commands.hybrid_command(
        name="prefixes", aliases=["prefix"], description="Get the bot's command prefixes."
    )
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def prefixes(self, ctx: commands.Context["TitaniumBot"]) -> None:
        if (
            not ctx.guild
            or not self.bot.user
            or (ctx.interaction and not ctx.interaction.is_guild_integration())
        ):
            return

        await ctx.defer()

        prefix_str = ""
        config = await self.bot.fetch_guild_config(ctx.guild.id)
        if not config:
            raise ValueError("No guild config found")

        if not config.allow_prefix:
            embed = Embed(
                title=f"{self.bot.error_emoji} Disabled",
                description="Prefix commands are disabled in this server.",
                colour=Colour.red(),
            )
            embed.set_author(
                name=ctx.guild.name,
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
            )
            embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

            await ctx.reply(embed=embed)
            return

        for i, prefix in enumerate(config.prefixes):
            if i == 0:
                prefix_str = f"`{prefix}`"
                continue

            prefix_str += f", `{prefix}`"

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
