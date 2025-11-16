from typing import TYPE_CHECKING

from discord import Colour, Embed, app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


class BasicCommandsCog(commands.Cog, name="Basic", description="General bot commands."):
    """Basic commands."""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Get the bot's ping.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def ping(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        await ctx.reply(
            embed=Embed(
                title="Pong!",
                description=f"Latency: `{self.bot.latency * 1000:.2f}ms`",
                colour=Colour.green(),
            )
        )

    @commands.hybrid_command(
        name="info", description="Get information about the bot.", aliases=["about"]
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def info(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        await ctx.reply(
            embed=Embed(
                title="Titanium",
                description="This is a development version of Titanium. For more information, please go to https://github.com/RestartB/titanium/tree/v2.",
                colour=Colour.light_gray(),
            ).set_thumbnail(url=self.bot.user.display_avatar.url if self.bot.user else None)
        )

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
                    prefix_str += f"`{prefix}`"
                else:
                    prefix_str += f", `{prefix}`"
        else:
            prefix_str = "`t!`"

        prefix_str = prefix_str + (
            f", {self.bot.user.mention}" if prefix_str else self.bot.user.mention
        )

        embed = Embed(
            title="Command Prefixes",
            description=f"**{self.bot.user.name} will respond to the following prefixes in this server:**\n{prefix_str}",
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
