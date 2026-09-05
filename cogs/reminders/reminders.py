import typing
from datetime import timedelta
from typing import TYPE_CHECKING, Literal

import discord
from discord import AllowedMentions, Colour, app_commands
from discord.ext import commands
from discord.ui import LayoutView
from discord.utils import format_dt

from lib.embeds.general import invalid_duration
from lib.helpers.duration import DurationConverter
from lib.helpers.shorten import shorten_preserve
from lib.logic.reminders import create_reminder, get_all_reminders, get_reminder_count
from lib.views.pagination import PaginationV2View
from lib.views.reminders import RemindersPageContainer

if TYPE_CHECKING:
    from main import TitaniumBot


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class TemplateCog(commands.GroupCog, group_name="reminder", description="Create reminders."):
    """Create reminders"""

    ConvertedDuration = typing.Annotated[timedelta | None, DurationConverter]

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction["TitaniumBot"]) -> bool:
        if interaction.user.id not in self.bot.opt_out:
            return True

        embed = discord.Embed(
            title=f"{self.bot.error_emoji} Opted Out",
            description="You have opted out of data collection and cannot use reminder features.",
            colour=discord.Colour.red(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return False

    @app_commands.command(name="create", description="Create a new reminder.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @commands.cooldown(1, 3)
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="DM", value="dm"),
            app_commands.Choice(name="Server", value="server"),
        ],
    )
    async def reminder_create(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        mode: Literal["dm", "server"],
        time: ConvertedDuration,
        *,
        content: commands.Range[str, 1, 1000],
        ephemeral: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)

        if not time:
            await interaction.followup.send(embed=invalid_duration(self.bot), ephemeral=ephemeral)
            return

        time_scheduled = interaction.created_at + time
        dm = mode == "dm"

        if not dm and not isinstance(interaction.channel, discord.abc.GuildChannel):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="You are trying to create a server channel reminder in DMs. Please set the `DM` option to enabled.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        if not dm and not interaction.is_guild_integration():
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="Server channel reminders cannot be created as Titanium is not in the server. Please add Titanium to the server first.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        if not dm and (
            not interaction.permissions.view_channel
            or not interaction.permissions.send_messages
            or not interaction.permissions.use_application_commands
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Permissions",
                description="You don't have permission to create server reminders in this channel.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        if not dm and (
            not interaction.guild
            or not interaction.channel
            or not interaction.channel.permissions_for(interaction.guild.me).send_messages
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Permissions",
                description="Titanium doesn't have permissins to send messages in this channel. Your reminder will not send correctly.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        if await get_reminder_count(interaction.user) >= 50:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="You can only create up to 50 reminders. Delete some old reminders using the `/reminder list` command.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        # TODO: get message id if message is not private
        reminder = await create_reminder(
            content=content,
            time=time_scheduled,
            creator=interaction.user,
            dm=dm,
            guild_id=interaction.guild.id if interaction.guild else None,
            channel_id=interaction.channel.id if interaction.channel else None,
            message_id=None,
        )

        if dm:
            dm_embed = discord.Embed(
                title=f"{self.bot.success_emoji} Reminder Created • `{reminder.id}`",
                description=f"I will remind you **here** {format_dt(time_scheduled, style='R')} ({format_dt(time_scheduled, style='S')}).",
                colour=Colour.green(),
            )
            dm_embed.add_field(name="Content", value=shorten_preserve(content, width=1024))
            dm_embed.set_footer(
                text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
            )

            try:
                await interaction.user.send(embed=dm_embed)
            except discord.Forbidden:
                await reminder.delete()
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Error",
                    description="Titanium does not have permission to send you DMs. Please ensure Titanium is not blocked and that the bot is able to DM you, or that Titanium is added to your account as an app.",
                    colour=Colour.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return

        embed = discord.Embed(
            title=f"{self.bot.success_emoji} Created • `{reminder.id}`",
            description=f"I will remind you **{'in DMs' if dm else 'here'}** {format_dt(time_scheduled, style='R')} ({format_dt(time_scheduled, style='S')}).",
            colour=Colour.green(),
        )
        embed.add_field(name="Content", value=shorten_preserve(content, width=1024))
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="list", description="View and manage your created reminders.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @commands.cooldown(1, 5)
    async def reminder_list(
        self, interaction: discord.Interaction["TitaniumBot"], ephemeral: bool = False
    ) -> None:
        await interaction.response.defer(ephemeral=ephemeral)

        reminders = await get_all_reminders(interaction.user)
        reminder_chunks = discord.utils.as_chunks(reminders, 5)

        reminder_pages: list[RemindersPageContainer] = []
        for chunk in reminder_chunks:
            reminder_pages.append(
                RemindersPageContainer(interaction=interaction, reminders=chunk, reminder_count=len(reminders))
            )

        view = LayoutView(timeout=300)
        if not reminder_pages:
            view.add_item(
                RemindersPageContainer(interaction=interaction, reminders=[], reminder_count=len(reminders))
            )
        elif len(reminder_pages) > 1:
            view = PaginationV2View(pages=reminder_pages)
        else:
            view.add_item(reminder_pages[0])

        await interaction.followup.send(
            view=view, allowed_mentions=AllowedMentions.none(), ephemeral=ephemeral
        )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(TemplateCog(bot))
