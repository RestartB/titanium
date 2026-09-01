from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from lib.helpers.strings import dashboard_url

if TYPE_CHECKING:
    from main import TitaniumBot


class HelpCommandCog(commands.Cog):
    """Help commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    # TODO: redo help command
    @commands.hybrid_group(
        name="help",
        description="Show help information for Titanium.",
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
                ctx.interaction and ctx.interaction.is_guild_integration() and ctx.guild
            ) or ctx.guild:
                guild_settings = await self.bot.fetch_guild_config(ctx.guild.id)
                if isinstance(ctx.author, discord.Member) and (
                    ctx.author.guild_permissions.administrator
                    or (
                        guild_settings
                        and any(
                            role.id in guild_settings.dashboard_managers
                            for role in ctx.author.roles
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


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(HelpCommandCog(bot))
