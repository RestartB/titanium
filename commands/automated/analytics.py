from typing import TYPE_CHECKING, Union

import aiohttp
import discord
from discord import Color, app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


class Analytics(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    # Analytics for slash commands
    @commands.Cog.listener()
    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: Union[app_commands.Command, app_commands.ContextMenu],
    ) -> None:
        try:
            embed = discord.Embed(
                title=f"@{interaction.user.name} ran a command", color=Color.green()
            )
            embed.description = f"`/{f'{command.parent.name} ' if command.parent is not None else ''}{command.name}`"

            embed.timestamp = interaction.created_at
            embed.set_author(
                name=str(self.bot.user), icon_url=self.bot.user.display_avatar.url
            )

            embed.add_field(
                name="User",
                value=f"{interaction.user.mention} ({interaction.user.id})",
            )

            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(
                    self.bot.options["analytics-webhook"], session=session
                )
                await webhook.send(embed=embed)
        except Exception:
            pass


async def setup(bot: "TitaniumBot") -> None:
    # Only load if webhook URL is present
    try:
        if bot.options["analytics-webhook"] is not None:
            if bot.options["analytics-webhook"] != "":
                await bot.add_cog(Analytics(bot))
    except KeyError:
        pass
