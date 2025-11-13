from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


class HelpCommandCog(commands.Cog):
    """Help commands"""

    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    @commands.hybrid_group(name="help", description="Show help information for commands.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def help_command(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        embed = discord.Embed(
            title=f"{self.bot.info_emoji} Help",
            description=f"`{ctx.clean_prefix}help commands` - get a list of all commands\n"
            f"`{ctx.clean_prefix}help <command>` - get detailed help for a specific command\n"
            f"`{ctx.clean_prefix}help <category>` - get a list of commands in a specific category\n"
            "\n**Need more help? Join our [Support Server](https://titaniumbot.me/server)**",
            color=discord.Color.blue(),
        )

        if self.bot.user:
            embed.set_author(
                name=self.bot.user.display_name, icon_url=self.bot.user.display_avatar.url
            )

        await ctx.reply(embed=embed, ephemeral=True)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(HelpCommandCog(bot))
