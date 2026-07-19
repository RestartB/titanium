from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from lib.views.pagination import PaginationView

if TYPE_CHECKING:
    from main import TitaniumBot


class HelpCommandCog(commands.Cog):
    """Help commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @commands.hybrid_group(
        name="help",
        description="Show help information for Titanium, commands and categories.",
        fallback="info",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        command_or_group="Optional: the command or command group to get information about.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    async def help_group(
        self,
        ctx: commands.Context["TitaniumBot"],
        *,
        command_or_group: str = "",
        ephemeral: bool = False,
    ) -> None:
        await ctx.defer(ephemeral=ephemeral)

        if not command_or_group:
            embed = discord.Embed(
                title=f"{self.bot.info_emoji} Help",
                description=f"`{ctx.clean_prefix}help commands` - get a list of all commands\n"
                f"`{ctx.clean_prefix}help <command | group>` - get info about a command or command group\n",
                colour=discord.Colour.light_grey(),
            )
            embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

            if self.bot.user:
                embed.set_author(
                    name=self.bot.user.display_name, icon_url=self.bot.user.display_avatar.url
                )

            if (
                ctx.guild
                and isinstance(ctx.author, discord.Member)
                and (ctx.interaction and ctx.interaction.is_guild_integration())
                and self.bot.user
            ):
                config = await self.bot.fetch_guild_config(ctx.guild.id)
                if config and config.allow_prefix:
                    if config.prefixes:
                        value = f"`{'`, `'.join(config.prefixes)}`, {self.bot.user.mention}"
                    else:
                        value = self.bot.user.mention

                    embed.add_field(
                        name=f"Prefixes for {ctx.guild.name}", value=value, inline=False
                    )

            embed.add_field(
                name="Need more help?",
                value="Join the **[Support Server](https://titanium.fyi/server)** for feature and status updates, support, and more.",
            )

            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        command = self.bot.get_command(command_or_group)
        if not command:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Not Found",
                description=f"Couldn't find a command or category called `{command_or_group}`.",
                colour=discord.Colour.red(),
            )
            embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        embed = discord.Embed(
            title=f"`{ctx.clean_prefix}{command.qualified_name}`",
            description=f"`{ctx.clean_prefix}{command.qualified_name}{f'|{"|".join(alias for alias in command.aliases) if command.aliases else ""}' if command.aliases else ''}{' ' + command.signature if command.signature else ''}`\n\n{command.description}",
            colour=discord.Colour.light_grey(),
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        if isinstance(command, (commands.Group, commands.HybridGroup, app_commands.Group)):
            embed.add_field(
                name="Subcommands",
                value="\n".join(
                    f"`{ctx.clean_prefix}{subcommand.qualified_name}`"
                    for subcommand in command.commands
                ),
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
        for command in ctx.bot.walk_commands():
            # hidden command
            if command.hidden:
                continue

            # normal group
            if isinstance(command, commands.Group) and not isinstance(
                command, commands.HybridGroup
            ):
                continue

            # hybrid group without a fallback (no cmd on root)
            if isinstance(command, commands.HybridGroup) and not command.fallback:
                continue

            # add string
            if isinstance(command, commands.HybridGroup):
                command_list.append(
                    f"`{ctx.clean_prefix}{command.qualified_name}` (`{command.fallback}`)"
                )
            else:
                command_list.append(f"`{ctx.clean_prefix}{command.qualified_name}`")

        command_list.sort()

        command_pages: list[discord.Embed] = []
        current_page_commands: list[str] = []

        for command in command_list:
            current_page_commands.append(command)

            if len(current_page_commands) == 15:
                command_pages.append(
                    discord.Embed(
                        title="All Commands",
                        description=f"There are `{len(command_list)}` commands. When using prefix commands, entering parts of commands that are in brackets is optional.\n\n"
                        + "\n".join(current_page_commands),
                        colour=discord.Colour.light_grey(),
                    )
                )
                current_page_commands = []

        if len(current_page_commands) > 0:
            command_pages.append(
                discord.Embed(
                    title="All Commands",
                    description=f"There are `{len(command_list)}` commands. When using prefix commands, entering parts of commands that are in brackets is optional.\n\n"
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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self.bot.user or message.content.strip() != self.bot.user.mention:
            return

        ctx = await self.bot.get_context(message)
        await ctx.invoke(self.help_group)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(HelpCommandCog(bot))
