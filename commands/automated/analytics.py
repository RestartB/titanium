import logging
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
            # Ignore if there is no werbhook
            if (
                self.bot.options["analytics-webhook"] is not None
                and self.bot.options["analytics-webhook"] != ""
            ):
                try:
                    embed = discord.Embed(
                        title=f"@{interaction.user.name} ran a command",
                        color=Color.green(),
                    )

                    # Check if the command is a context menu command
                    if isinstance(command, app_commands.ContextMenu):
                        embed.description = f"`{command.name}`"
                    else:
                        embed.description = f"`/{f'{command.parent.name} ' if command.parent is not None else ''}{command.name}`"

                    embed.timestamp = interaction.created_at
                    embed.set_author(
                        name=str(self.bot.user),
                        icon_url=self.bot.user.display_avatar.url,
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
                except Exception as e:
                    logging.error(f"[ANALYTICS] Failed to send analytics webhook - {e}")
        except KeyError:
            pass

    # Analytics for raw interactions
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            # Ignore if there is no werbhook
            if (
                self.bot.options["raw-analytics-webhook"] is not None
                and self.bot.options["raw-analytics-webhook"] != ""
            ):
                try:
                    async with aiohttp.ClientSession() as session:
                        embed = discord.Embed(
                            title=f"@{interaction.user.name} started an interaction",
                            color=Color.green(),
                        )

                        # Check if the command is a context menu command
                        try:
                            if isinstance(
                                interaction.command, app_commands.ContextMenu
                            ):
                                embed.description = f"`{interaction.command.name}`"
                            else:
                                try:
                                    embed.description = f"`/{f'{interaction.command.parent.name} ' if interaction.command.parent is not None else ''}{interaction.command.name}`"
                                except AttributeError:
                                    embed.description = f"`{interaction.command.name}`"
                        except AttributeError:
                            embed.description = f"`{interaction.type}`"

                        embed.timestamp = interaction.created_at
                        embed.set_author(
                            name=str(self.bot.user),
                            icon_url=self.bot.user.display_avatar.url,
                        )

                        embed.add_field(
                            name="User",
                            value=f"{interaction.user.mention} ({interaction.user.id})",
                        )

                        async with aiohttp.ClientSession() as session:
                            webhook = discord.Webhook.from_url(
                                self.bot.options["raw-analytics-webhook"],
                                session=session,
                            )
                            await webhook.send(embed=embed)
                except Exception as e:
                    logging.error(
                        f"[ANALYTICS] Failed to send raw analytics webhook - {e}"
                    )
        except KeyError:
            pass


async def setup(bot: "TitaniumBot") -> None:
    try:
        # Only load if webhook URL is present
        if (
            bot.options["analytics-webhook"] is not None
            and bot.options["analytics-webhook"] != ""
        ):
            normal = True
        else:
            normal = False
    except KeyError:
        normal = False

    try:
        if (
            bot.options["raw-analytics-webhook"] is not None
            and bot.options["raw-analytics-webhook"] != ""
        ):
            raw = True
        else:
            raw = False
    except KeyError:
        raw = False

    if normal or raw:
        await bot.add_cog(Analytics(bot))
    else:
        return
