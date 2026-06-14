from textwrap import shorten
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord.utils import format_dt

from lib.embeds.general import guild_only
from lib.embeds.reminders import invalid_duration, reminder_deleted, reminder_edited
from lib.helpers.components import embed_to_v2
from lib.helpers.duration import timestring_to_duration
from lib.sql.sql import Reminder

if TYPE_CHECKING:
    from main import TitaniumBot


class ReminderModal(discord.ui.Modal, title="Edit Reminder"):
    def __init__(self, reminder: Reminder):
        super().__init__(timeout=360)
        self.reminder = reminder

        assert isinstance(self.content_label.component, discord.ui.TextInput)
        self.content_label.component.default = reminder.content

    content_label = discord.ui.Label(
        text="Content",
        description="Enter the reminder content here.",
        component=discord.ui.TextInput(
            style=discord.TextStyle.long,
            min_length=1,
            max_length=1000,
            required=True,
        ),
    )

    duration_label = discord.ui.Label(
        text="Duration",
        description="Enter the new duration of the reminder here. (optional)",
        component=discord.ui.TextInput(
            style=discord.TextStyle.short, required=False, placeholder="(example: 10h5m20s)"
        ),
    )

    async def on_submit(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        assert isinstance(self.content_label.component, discord.ui.TextInput)
        assert isinstance(self.duration_label.component, discord.ui.TextInput)

        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            await interaction.edit_original_response(
                view=embed_to_v2(guild_only(interaction.client))
            )
            return

        time_scheduled = None
        if self.duration_label.component.value:
            try:
                duration = timestring_to_duration(
                    self.duration_label.component.value,
                )
            except OverflowError:
                view = discord.ui.LayoutView()
                await interaction.edit_original_response(
                    view=view.add_item(
                        discord.ui.Container(
                            discord.ui.TextDisplay(
                                f"## {interaction.client.error_emoji} Invalid Duration\nDurations cannot exceed 60 years."
                            ),
                            accent_colour=discord.Colour.red(),
                        )
                    )
                )
                return

            if not duration:
                await interaction.edit_original_response(
                    view=embed_to_v2(invalid_duration(interaction.client))
                )
                return

            time_scheduled = interaction.created_at + duration

        await self.reminder.edit(content=self.content_label.component.value, time=time_scheduled)
        await interaction.edit_original_response(
            view=embed_to_v2(reminder_edited(interaction.client))
        )


class DeleteReminderButton(discord.ui.Button):
    def __init__(self, reminder: Reminder) -> None:
        super().__init__(label="Delete", emoji="🗑️", style=discord.ButtonStyle.red)
        self.reminder = reminder

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        await self.reminder.delete()
        await interaction.edit_original_response(
            view=embed_to_v2(reminder_deleted(interaction.client))
        )


class EditReminderButton(discord.ui.Button):
    def __init__(self, reminder: Reminder) -> None:
        super().__init__(label="Edit", emoji="✏️", style=discord.ButtonStyle.secondary)
        self.reminder = reminder

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        modal = ReminderModal(reminder=self.reminder)
        await interaction.response.send_modal(modal)


class MenuButton(discord.ui.Button):
    def __init__(self, bot: TitaniumBot, reminder: Reminder) -> None:
        super().__init__(emoji=bot.menu_emoji)
        self.reminder = reminder

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        await interaction.response.defer(ephemeral=True)

        view = discord.ui.LayoutView()
        options_row = discord.ui.ActionRow(
            EditReminderButton(self.reminder), DeleteReminderButton(self.reminder)
        )

        await interaction.followup.send(view=view.add_item(options_row), ephemeral=True)


class ReminderRow(discord.ui.Section):
    def __init__(self, bot: TitaniumBot, reminder: Reminder) -> None:
        super().__init__(accessory=MenuButton(bot, reminder))

        guild = None
        if not reminder.dm and reminder.guild_id:
            guild = bot.get_guild(reminder.guild_id)

        guild_name = shorten(guild.name, width=20) if guild else "Unknown Guild"

        self.add_item(
            discord.ui.TextDisplay(
                content=f"-# <@{reminder.user_id}> - {format_dt(reminder.time, style='R')}, `{'DMs' if reminder.dm else guild_name}`\n{discord.utils.escape_markdown(discord.utils.escape_mentions(reminder.content))}"
            )
        )


class RemindersPageContainer(discord.ui.Container):
    def __init__(
        self, ctx: commands.Context["TitaniumBot"], reminders: list[Reminder], reminder_count: int
    ):
        super().__init__(accent_colour=discord.Colour.light_grey())

        command_str = "/reminder create" if ctx.interaction else f"{ctx.clean_prefix}reminder"
        content = "## Your Reminders\n"
        content += (
            f"{ctx.bot.info_emoji} There {'are' if reminder_count > 1 else 'is'} **{reminder_count} reminder{'s' if reminder_count > 1 else ''}** to show."
            if reminder_count > 0
            else f"There are no reminders to show. To create a new reminder, use the `{command_str}` command."
        )

        self.add_item(discord.ui.TextDisplay(content=content))

        if reminder_count > 0:
            self.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
            for reminder in reminders:
                self.add_item(ReminderRow(ctx.bot, reminder))
