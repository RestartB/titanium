import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import discord
from discord import Colour, Interaction, SeparatorSpacing, ui

from lib.sql import GuildConfessionSettings, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


log: logging.Logger = logging.getLogger(__name__)

__all__: tuple[str, ...] = ("ConfessionSettingsLayout", "ConfessionSettings")


@dataclass
class ConfessionSettings:
    user_id: int
    is_conf_enable: bool
    guild_settings: GuildConfessionSettings


class ConfessionToggleButton(ui.Button["ConfessionSettingsLayout"]):
    def __init__(self, settings: ConfessionSettings) -> None:
        super().__init__(label="Enable", style=discord.ButtonStyle.green)
        self.settings: ConfessionSettings = settings
        self.update_button()

    def update_button(self):
        if self.settings.is_conf_enable:
            self.label = "Disable"
            self.style = discord.ButtonStyle.red
        else:
            self.label = "Enable"
            self.style = discord.ButtonStyle.green

    async def callback(self, interaction: Interaction["TitaniumBot"]) -> None:
        self.settings.is_conf_enable = not self.settings.is_conf_enable
        self.update_button()
        await interaction.response.edit_message(view=self.view)


class ChannelSetting(ui.ActionRow["ConfessionSettingsLayout"]):
    def __init__(
        self,
        settings: ConfessionSettings,
        channle_type: Literal["conf_channle", "conf_log"],
    ) -> None:
        super().__init__()
        self.settings: ConfessionSettings = settings
        self.channle_type: str = channle_type

        if (
            channle_type == "conf_channle"
            and settings.guild_settings.confession_channel_id
        ):
            self.select_channel.default_values = [
                discord.SelectDefaultValue(
                    id=settings.guild_settings.confession_channel_id,
                    type=discord.SelectDefaultValueType.channel,
                )
            ]
        elif (
            channle_type == "conf_log"
            and settings.guild_settings.confession_log_channel_id
        ):
            self.select_channel.default_values = [
                discord.SelectDefaultValue(
                    id=settings.guild_settings.confession_log_channel_id,
                    type=discord.SelectDefaultValueType.channel,
                )
            ]

    @ui.select(
        placeholder="Select a channel",
        channel_types=[discord.ChannelType.text],
        max_values=1,
        min_values=0,
        cls=ui.ChannelSelect,
    )
    async def select_channel(
        self, interaction: discord.Interaction["TitaniumBot"], select: ui.ChannelSelect
    ) -> None:
        if select.values:
            channel = select.values[0]
            self.update_channel(channel.id)
            select.default_values = [
                discord.SelectDefaultValue(
                    id=channel.id, type=discord.SelectDefaultValueType.channel
                )
            ]
        else:
            self.update_channel(None)
            select.default_values = []
        await interaction.response.edit_message(view=self.view)

    def update_channel(self, ch_id: int | None) -> None:
        if self.channle_type == "conf_channle":
            self.settings.guild_settings.confession_channel_id = ch_id
        elif self.channle_type == "conf_log":
            self.settings.guild_settings.confession_log_channel_id = ch_id
        else:
            log.warning("[ConfessionLayout] invalid channle_type has been provided")


class ConfessionSettingsLayout(ui.LayoutView):
    row = ui.ActionRow()

    def __init__(
        self,
        settings: ConfessionSettings,
        timeout: float | None = 180,
    ) -> None:
        super().__init__(timeout=timeout)
        self.settings: ConfessionSettings = settings

        container = ui.Container(accent_color=Colour.blue())

        # Header of the settings
        container.add_item(
            ui.TextDisplay(
                "## Confession Settings\n\n"
                "-# Welcome to the confession settings! Here you can enable or disable the confession feature for your server, "
                "and set up the channels where confessions and logs will be sent. "
                "Follow the steps below to complete the setup. Once everything is configured, click the **Finish** button to save."
            )
        )
        container.add_item(ui.Separator(spacing=SeparatorSpacing.large))

        # Settings toggle button
        container.add_item(
            ui.Section(
                ui.TextDisplay(
                    "### 1. Toggle Confession Module\n"
                    "-# Use this option to enable or disable the confession feature for your server."
                ),
                accessory=ConfessionToggleButton(self.settings),
            )
        )

        container.add_item(ui.Separator())

        # Confession Message send channel settings
        container.add_item(
            ui.TextDisplay(
                "### 2. Confession Message Channel\n\n"
                "-# Select the channel where confessions will be posted for everyone to see."
            )
        )
        container.add_item(ChannelSetting(self.settings, channle_type="conf_channle"))

        container.add_item(ui.Separator())

        # Confession mod log send channel settings
        container.add_item(
            ui.TextDisplay(
                "### 3. Confession Log Channel\n\n"
                "-# Select the channel where confession logs will be sent. "
                "This is usually a private channel for moderators to review."
            )
        )
        container.add_item(ChannelSetting(self.settings, channle_type="conf_log"))

        self.add_item(container)

        self.remove_item(self.row)
        self.add_item(self.row)

    async def interaction_check(self, interaction: Interaction["TitaniumBot"]) -> bool:
        return self.settings.user_id == interaction.user.id

    @row.button(label="Finish", style=discord.ButtonStyle.green)
    async def finish_button(
        self, interaction: discord.Interaction["TitaniumBot"], button: ui.Button
    ) -> None:
        await interaction.response.defer()
        if (
            self.settings.is_conf_enable
            and not self.settings.guild_settings.confession_channel_id
        ):
            return await interaction.followup.send(
                "You must select a confession message channel (Step 2) when the confession settings is enabled.",
                ephemeral=True,
            )

        self.diable_components()
        await interaction.message.edit(view=self)  # disable the comonent
        await self.update_settings(interaction)  # update the database
        await interaction.followup.send("Settings has been saved.", ephemeral=True)
        self.stop()

    def diable_components(self) -> None:
        for child in self.walk_children():
            if child.is_dispatchable():
                child.disabled = True

    async def update_settings(self, interaction: discord.Interaction) -> None:
        async with get_session() as session:
            # confession settings update
            guild_config = interaction.client.guild_configs.get(interaction.guild.id)
            guild_config.confession_enabled = self.settings.is_conf_enable
            session.add(guild_config)

            # Fetch existing confession settings
            confession_settings = await session.get(
                GuildConfessionSettings, interaction.guild.id
            )

            if not confession_settings:
                confession_settings = GuildConfessionSettings(
                    guild_id=interaction.guild.id
                )
                session.add(confession_settings)

            confession_settings.confession_channel_id = (
                self.settings.guild_settings.confession_channel_id
            )
            confession_settings.confession_log_channel_id = (
                self.settings.guild_settings.confession_log_channel_id
            )

            await session.commit()

        await interaction.client.refresh_guild_config_cache(interaction.guild.id)
