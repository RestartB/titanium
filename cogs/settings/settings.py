from typing import TYPE_CHECKING

from discord import (
    ButtonStyle,
    Colour,
    Embed,
    Interaction,
    SeparatorSpacing,
    app_commands,
)
from discord.ext import commands
from discord.ui import (
    Button,
    Container,
    LayoutView,
    Section,
    Separator,
    TextDisplay,
    Thumbnail,
)
from sqlalchemy.orm.attributes import flag_modified

from lib.helpers.hybrid_adapters import SlashCommandOnly
from lib.sql.sql import (
    GuildPrefixes,
    GuildSettings,
    get_session,
)

if TYPE_CHECKING:
    from main import TitaniumBot


class ModToggleButton(Button["SettingsView"]):
    def __init__(self, bot: "TitaniumBot", settings: GuildSettings) -> None:
        super().__init__(label="\N{BELL}", style=ButtonStyle.green)

        self.bot = bot
        self.settings = settings

        self.update_button()

    def update_button(self):
        if self.settings.moderation_enabled:
            self.label = "Enabled"
            self.emoji = self.bot.success_emoji
            self.style = ButtonStyle.green
        else:
            self.label = "Disabled"
            self.emoji = self.bot.error_emoji
            self.style = ButtonStyle.red

    async def callback(self, interaction: Interaction) -> None:
        if not interaction.guild_id:
            return

        self.settings.moderation_enabled = not self.settings.moderation_enabled

        async with get_session() as session:
            guild_settings = await session.get(GuildSettings, interaction.guild_id)

            if not guild_settings:
                guild_settings = GuildSettings(guild_id=interaction.guild_id)
                session.add(guild_settings)

            guild_settings.moderation_enabled = self.settings.moderation_enabled

        await self.bot.refresh_guild_config_cache(interaction.guild_id)
        self.update_button()
        await interaction.response.edit_message(view=self.view)


class AutomodToggleButton(Button["SettingsView"]):
    def __init__(self, bot: "TitaniumBot", settings: GuildSettings) -> None:
        super().__init__(label="\N{BELL}", style=ButtonStyle.green)

        self.bot = bot
        self.settings = settings

        self.update_button()

    def update_button(self):
        if self.settings.automod_enabled:
            self.label = "Enabled"
            self.emoji = self.bot.success_emoji
            self.style = ButtonStyle.green
        else:
            self.label = "Disabled"
            self.emoji = self.bot.error_emoji
            self.style = ButtonStyle.red

    async def callback(self, interaction: Interaction) -> None:
        if not interaction.guild_id:
            return

        self.settings.automod_enabled = not self.settings.automod_enabled

        async with get_session() as session:
            guild_settings = await session.get(GuildSettings, interaction.guild_id)

            if not guild_settings:
                guild_settings = GuildSettings(guild_id=interaction.guild_id)
                session.add(guild_settings)

            guild_settings.automod_enabled = self.settings.automod_enabled

        await self.bot.refresh_guild_config_cache(interaction.guild_id)
        self.update_button()
        await interaction.response.edit_message(view=self.view)


class LoggingToggleButton(Button["SettingsView"]):
    def __init__(self, bot: "TitaniumBot", settings: GuildSettings) -> None:
        super().__init__(label="\N{BELL}", style=ButtonStyle.green)

        self.bot = bot
        self.settings = settings

        self.update_button()

    def update_button(self):
        if self.settings.logging_enabled:
            self.label = "Enabled"
            self.emoji = self.bot.success_emoji
            self.style = ButtonStyle.green
        else:
            self.label = "Disabled"
            self.emoji = self.bot.error_emoji
            self.style = ButtonStyle.red

    async def callback(self, interaction: Interaction) -> None:
        if not interaction.guild_id:
            return

        self.settings.logging_enabled = not self.settings.logging_enabled

        async with get_session() as session:
            guild_settings = await session.get(GuildSettings, interaction.guild_id)

            if not guild_settings:
                guild_settings = GuildSettings(guild_id=interaction.guild_id)
                session.add(guild_settings)

            guild_settings.logging_enabled = self.settings.logging_enabled

        await self.bot.refresh_guild_config_cache(interaction.guild_id)
        self.update_button()
        await interaction.response.edit_message(view=self.view)


class SettingsView(LayoutView):
    """Settings quick option commands"""

    def __init__(
        self, interaction: Interaction, bot: "TitaniumBot", settings: GuildSettings
    ) -> None:
        super().__init__()

        if interaction.guild is None:
            return

        container = Container()

        if interaction.guild.icon:
            top_section = Section(accessory=Thumbnail(media=interaction.guild.icon.url))
            top_section.add_item(
                TextDisplay(
                    f"## Server Settings\nFor the **{interaction.guild.name}** server. To manage more settings, please go to the Titanium Dashboard."
                )
            )
        else:
            top_section = TextDisplay(
                f"## Server Settings\nFor the **{interaction.guild.name}** server. To manage more settings, please go to the Titanium Dashboard."
            )

        container.add_item(top_section)
        container.add_item(Separator(spacing=SeparatorSpacing.large))

        mod_section = Section(accessory=ModToggleButton(bot, settings))
        mod_section.add_item(
            TextDisplay("### Moderation\nModerate your server members and create cases.")
        )
        container.add_item(mod_section)

        automod_section = Section(accessory=ModToggleButton(bot, settings))
        automod_section.add_item(
            TextDisplay("### Auto Moderation\nAllow Titanium to moderate your server for you.")
        )
        container.add_item(automod_section)

        logging_section = Section(accessory=LoggingToggleButton(bot, settings))
        logging_section.add_item(
            TextDisplay("### Logging\nLog various events that happen in your server.")
        )
        container.add_item(logging_section)

        self.add_item(container)


class GuildSettingsCog(commands.Cog, name="Settings", description="Manage server settings."):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    @commands.command(name="settings", description="Please use the slash command version instead.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def settings_prefix(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise SlashCommandOnly

    settings_group = app_commands.Group(
        name="settings", description="Manage server settings.", guild_only=True
    )
    prefix_group = app_commands.Group(
        name="prefix",
        description="Manage command prefixes.",
        parent=settings_group,
    )

    @settings_group.command(
        name="overview",
        description="View an overview of this server's settings.",
    )
    async def overview(self, interaction: Interaction) -> None:
        if not interaction.guild or not interaction.guild_id or not self.bot.user:
            return

        await interaction.response.defer(ephemeral=True)

        await self.bot.refresh_guild_config_cache(interaction.guild_id)
        guild_settings = self.bot.guild_configs.get(interaction.guild_id)

        if not guild_settings:
            guild_settings = await self.bot.init_guild(interaction.guild_id)

        view = SettingsView(interaction, self.bot, guild_settings)

        await interaction.followup.send(view=view, ephemeral=True)

    @prefix_group.command(name="add", description="Add a command prefix.")
    @app_commands.guild_only()
    async def add_prefix(
        self, interaction: Interaction, prefix: app_commands.Range[str, 1, 5]
    ) -> None:
        if not interaction.guild or not interaction.guild_id or not self.bot.user:
            return

        await interaction.response.defer(ephemeral=True)

        if len(prefix) > 5:
            return await interaction.followup.send(
                embed=Embed(
                    title=f"{str(self.bot.error_emoji)} Invalid Prefix",
                    description="The prefix must be between 1 and 5 characters long.",
                    colour=Colour.red(),
                ),
                ephemeral=True,
            )

        async with get_session() as session:
            prefixes = await session.get(GuildPrefixes, interaction.guild_id)

            if not prefixes:
                prefixes = GuildPrefixes(guild_id=interaction.guild_id)
                session.add(prefixes)

            if prefixes.prefixes is None:
                prefixes.prefixes = ["t!"]

            if prefix.lower() in prefixes.prefixes:
                return await interaction.followup.send(
                    embed=Embed(
                        title=f"{str(self.bot.error_emoji)} Already Exists",
                        description=f"The `{prefix.lower()}` prefix has already been added.",
                        colour=Colour.red(),
                    ),
                    ephemeral=True,
                )

            prefixes.prefixes.append(prefix.lower())
            flag_modified(prefixes, "prefixes")

            self.bot.guild_prefixes[interaction.guild_id] = prefixes

        await interaction.followup.send(
            embed=Embed(
                title=f"{str(self.bot.success_emoji)} Added",
                description=f"Added the `{prefix.lower()}` prefix.",
                colour=Colour.green(),
            ),
            ephemeral=True,
        )

    async def prefix_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []

        prefixes = self.bot.guild_prefixes.get(interaction.guild_id)
        if prefixes and prefixes.prefixes is not None:
            return [app_commands.Choice(name=prefix, value=prefix) for prefix in prefixes.prefixes]
        else:
            return [app_commands.Choice(name="t!", value="t!")]

    @prefix_group.command(
        name="remove",
        description="Remove a command prefix.",
    )
    @app_commands.guild_only()
    @app_commands.autocomplete(prefix=prefix_autocomplete)
    async def remove_prefix(
        self, interaction: Interaction, prefix: app_commands.Range[str, 1, 5]
    ) -> None:
        if not interaction.guild or not interaction.guild_id or not self.bot.user:
            return

        await interaction.response.defer(ephemeral=True)

        if len(prefix) > 5:
            return await interaction.followup.send(
                embed=Embed(
                    title=f"{str(self.bot.error_emoji)} Invalid Prefix",
                    description="The prefix must be between 1 and 5 characters long.",
                    colour=Colour.red(),
                ),
                ephemeral=True,
            )

        async with get_session() as session:
            prefixes = await session.get(GuildPrefixes, interaction.guild_id)

            if not prefixes:
                prefixes = GuildPrefixes(guild_id=interaction.guild_id)
                session.add(prefixes)

            if prefixes.prefixes is None:
                prefixes.prefixes = ["t!"]

            if prefix.lower() not in prefixes.prefixes:
                return await interaction.followup.send(
                    embed=Embed(
                        title=f"{str(self.bot.error_emoji)} Not Found",
                        description=f"The `{prefix.lower()}` prefix does not exist.",
                        colour=Colour.red(),
                    ),
                    ephemeral=True,
                )

            prefixes.prefixes.remove(prefix.lower())
            flag_modified(prefixes, "prefixes")

            self.bot.guild_prefixes[interaction.guild_id] = prefixes

        await interaction.followup.send(
            embed=Embed(
                title=f"{str(self.bot.success_emoji)} Removed",
                description=f"Removed the `{prefix.lower()}` prefix.",
                colour=Colour.green(),
            ),
            ephemeral=True,
        )


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(GuildSettingsCog(bot))
