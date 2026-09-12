from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from lib.helpers.strings import dashboard_url
from lib.views.pagination import PaginationView

if TYPE_CHECKING:
    from main import TitaniumBot


class HelpCommandCog(commands.Cog):
    """Help commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @commands.hybrid_group(
        name="help", description="Show help information for Titanium.", fallback="info"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    async def help_group(
        self,
        ctx: commands.Context["TitaniumBot"],
        ephemeral: bool = False,
    ) -> None:
        await ctx.defer(ephemeral=ephemeral)

        embed = discord.Embed(
            title=f"{self.bot.info_emoji} Help",
            description="`/help info` - this command (basic information)\n"
            "`/help commands` - get a list of all Titanium commands\n"
            "`/settings` - manage Titanium settings\n",
            colour=discord.Colour.light_grey(),
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        embed.add_field(
            name="Using Titanium",
            value="To use Titanium's commands, use **slash commands.** Type `/` to begin and select a command from the list, or select the Apps icon on the message bar.",
            inline=False,
        )

        if self.bot.user:
            embed.set_author(
                name=self.bot.user.display_name, icon_url=self.bot.user.display_avatar.url
            )

        if (ctx.interaction and ctx.interaction.is_guild_integration() and ctx.guild) or ctx.guild:
            guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
            if isinstance(ctx.author, discord.Member) and (
                ctx.author.guild_permissions.administrator
                or (
                    guild_settings
                    and any(
                        role.id in guild_settings.dashboard_managers for role in ctx.author.roles
                    )
                )
            ):
                embed.add_field(
                    name="Manage Settings",
                    value=f"Use `/settings` or the **{dashboard_url(ctx.guild.id)}** to manage Titanium's settings for this server.",
                    inline=False,
                )

        embed.add_field(
            name="Need more help?",
            value="Join the **[Support Server](https://titanium.fyi/server)** for feature and status updates, support, and more.",
            inline=False,
        )

        await ctx.reply(embed=embed, ephemeral=ephemeral)

    @help_group.command(name="commands", description="Get a list of all Titanium commands.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def all_commands(
        self, ctx: commands.Context["TitaniumBot"], ephemeral: bool = False
    ) -> None:
        await ctx.defer(ephemeral=ephemeral)

        command_list = []
        for command in ctx.bot.tree.walk_commands():
            if isinstance(command, app_commands.Group):
                continue
            command_list.append(f"`/{command.qualified_name}`")

        command_list.sort()

        command_pages: list[discord.Embed] = []
        current_page_commands: list[str] = []

        for command in command_list:
            current_page_commands.append(command)

            if len(current_page_commands) == 15:
                command_pages.append(
                    discord.Embed(
                        title=f"{self.bot.info_emoji} All Commands",
                        description=f"There are `{len(command_list)}` commands.\n\n"
                        + "\n".join(current_page_commands),
                        colour=discord.Colour.light_grey(),
                    )
                )
                current_page_commands = []

        if len(current_page_commands) > 0:
            command_pages.append(
                discord.Embed(
                    title=f"{self.bot.info_emoji} All Commands",
                    description=f"There are `{len(command_list)}` commands.\n\n"
                    + "\n".join(current_page_commands),
                    colour=discord.Colour.light_grey(),
                )
            )

        if len(command_pages) > 1:
            view = PaginationView(embeds=command_pages, timeout=1200)
            await ctx.reply(embed=command_pages[0], view=view, ephemeral=ephemeral)
        else:
            await ctx.reply(
                embed=command_pages[0].set_footer(
                    text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar
                ),
                ephemeral=ephemeral,
            )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(HelpCommandCog(bot))
