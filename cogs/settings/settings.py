from typing import TYPE_CHECKING

from discord import Color, Embed, Interaction, app_commands
from discord.ext import commands
from sqlalchemy.orm.attributes import flag_modified

from lib.sql import ServerPrefixes, ServerSettings, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ServerSettingsCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    @commands.command(name="settings", description="Manage server settings.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def settings_prefix(self, ctx: commands.Context[commands.Bot]) -> None:
        await ctx.reply(
            embed=Embed(
                title="Server Settings",
                description="To change bot settings, please use slash commands.",
                color=Color.blue(),
            )
        )

    settings_group = app_commands.Group(
        name="settings", description="Manage server settings."
    )
    prefix_group = app_commands.Group(
        name="prefix",
        description="Manage command prefixes.",
        parent=settings_group,
    )
    mod_group = app_commands.Group(
        name="mod",
        description="Manage moderation settings.",
        parent=settings_group,
    )
    automod_group = app_commands.Group(
        name="automod",
        description="Manage auto moderation settings.",
        parent=settings_group,
    )

    @settings_group.command(
        name="overview",
        description="View an overview of this server's settings.",
    )
    async def overview(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        server_settings: ServerSettings = self.bot.server_configs.get(
            interaction.guild_id
        )

        embed = Embed(
            title="Settings",
            description=f"""
- **Moderation Module:** {f"{str(self.bot.success_emoji)} Enabled" if server_settings.moderation_enabled else f"{str(self.bot.error_emoji)} Disabled"}
- **Auto Moderation Module:** {f"{str(self.bot.success_emoji)} Enabled" if server_settings.automod_enabled else f"{str(self.bot.error_emoji)} Disabled"}
            """,
            color=Color.blue(),
        )

        prefix_str = ""
        if self.bot.server_prefixes.get(interaction.guild.id):
            for i, prefix in enumerate(
                self.bot.server_prefixes[interaction.guild.id].prefixes
            ):
                if i == 0:
                    prefix_str += f"`{prefix}`"
                else:
                    prefix_str += f", `{prefix}`"
        else:
            prefix_str = "`t!`"
        prefix_str = prefix_str + (
            f", {self.bot.user.mention}" if prefix_str else self.bot.user.mention
        )

        embed.add_field(
            name="Prefixes",
            value=prefix_str,
            inline=False,
        )

        embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )

        embed.set_thumbnail(
            url=interaction.guild.icon.url if interaction.guild.icon else None
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @prefix_group.command(name="add", description="Add a command prefix.")
    async def add_prefix(
        self, interaction: Interaction, prefix: app_commands.Range[str, 1, 5]
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if len(prefix) > 5:
            return await interaction.followup.send(
                embed=Embed(
                    title=f"{str(self.bot.error_emoji)} Invalid Prefix",
                    description="The prefix must be between 1 and 5 characters long.",
                    color=Color.red(),
                ),
                ephemeral=True,
            )

        async with get_session() as session:
            prefixes = await session.get(ServerPrefixes, interaction.guild_id)

            if not prefixes:
                prefixes = ServerPrefixes(guild_id=interaction.guild_id)
                session.add(prefixes)

            if prefixes.prefixes is None:
                prefixes.prefixes = ["t!"]

            if prefix.lower() in prefixes.prefixes:
                return await interaction.followup.send(
                    embed=Embed(
                        title=f"{str(self.bot.error_emoji)} Already Exists",
                        description=f"The `{prefix.lower()}` prefix has already been added.",
                        color=Color.red(),
                    ),
                    ephemeral=True,
                )

            prefixes.prefixes.append(prefix.lower())
            flag_modified(prefixes, "prefixes")
            await session.commit()

            self.bot.server_prefixes[interaction.guild_id] = prefixes

        await interaction.followup.send(
            embed=Embed(
                title=f"{str(self.bot.success_emoji)} Added",
                description=f"Added the `{prefix.lower()}` prefix.",
                color=Color.green(),
            ),
            ephemeral=True,
        )

    async def prefix_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        prefixes = self.bot.server_prefixes.get(interaction.guild_id)
        if prefixes and prefixes.prefixes is not None:
            return [
                app_commands.Choice(name=prefix, value=prefix)
                for prefix in prefixes.prefixes
            ]
        else:
            return [app_commands.Choice(name="t!", value="t!")]

    @prefix_group.command(
        name="remove",
        description="Remove a command prefix.",
    )
    @app_commands.autocomplete(prefix=prefix_autocomplete)
    async def remove_prefix(
        self, interaction: Interaction, prefix: app_commands.Range[str, 1, 5]
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if len(prefix) > 5:
            return await interaction.followup.send(
                embed=Embed(
                    title=f"{str(self.bot.error_emoji)} Invalid Prefix",
                    description="The prefix must be between 1 and 5 characters long.",
                    color=Color.red(),
                ),
                ephemeral=True,
            )

        async with get_session() as session:
            prefixes = await session.get(ServerPrefixes, interaction.guild_id)

            if not prefixes:
                prefixes = ServerPrefixes(guild_id=interaction.guild_id)
                session.add(prefixes)

            if prefixes.prefixes is None:
                prefixes.prefixes = ["t!"]

            if prefix.lower() not in prefixes.prefixes:
                return await interaction.followup.send(
                    embed=Embed(
                        title=f"{str(self.bot.error_emoji)} Not Found",
                        description=f"The `{prefix.lower()}` prefix does not exist.",
                        color=Color.red(),
                    ),
                    ephemeral=True,
                )

            prefixes.prefixes.remove(prefix.lower())
            flag_modified(prefixes, "prefixes")
            await session.commit()

            self.bot.server_prefixes[interaction.guild_id] = prefixes

        await interaction.followup.send(
            embed=Embed(
                title=f"{str(self.bot.success_emoji)} Removed",
                description=f"Removed the `{prefix.lower()}` prefix.",
                color=Color.green(),
            ),
            ephemeral=True,
        )

    @mod_group.command(name="enable", description="Enable the moderation module.")
    async def enable_moderation(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        async with get_session() as session:
            server_settings = await session.get(ServerSettings, interaction.guild_id)

            if not server_settings:
                server_settings = ServerSettings(guild_id=interaction.guild_id)
                session.add(server_settings)

            if server_settings.moderation_enabled:
                await interaction.followup.send(
                    embed=Embed(
                        title=f"{str(self.bot.error_emoji)} Already Enabled",
                        description="Moderation module is already enabled.",
                        color=Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            server_settings.moderation_enabled = True
            await session.commit()

            self.bot.server_configs[interaction.guild_id] = server_settings

        await interaction.followup.send(
            embed=Embed(
                title=f"{str(self.bot.success_emoji)} Enabled",
                description="Moderation module has been enabled.",
                color=Color.green(),
            ),
            ephemeral=True,
        )

    @mod_group.command(name="disable", description="Disable the moderation module.")
    async def disable_moderation(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        async with get_session() as session:
            server_settings = await session.get(ServerSettings, interaction.guild_id)

            if not server_settings:
                server_settings = ServerSettings(guild_id=interaction.guild_id)
                session.add(server_settings)

            if not server_settings.moderation_enabled:
                await interaction.followup.send(
                    embed=Embed(
                        title=f"{str(self.bot.error_emoji)} Already Disabled",
                        description="Moderation module is already disabled.",
                        color=Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            server_settings.moderation_enabled = False
            await session.commit()

            self.bot.server_configs[interaction.guild_id] = server_settings

        await interaction.followup.send(
            embed=Embed(
                title=f"{str(self.bot.success_emoji)} Disabled",
                description="Moderation module has been disabled.",
                color=Color.green(),
            ),
            ephemeral=True,
        )


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(ServerSettingsCog(bot))
