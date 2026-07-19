import typing
from datetime import timedelta
from typing import TYPE_CHECKING, Literal, Optional

import discord
from discord import AllowedMentions, Colour, app_commands
from discord.ext import commands
from discord.ui import LayoutView
from discord.utils import format_dt

from lib.embeds.general import invalid_duration
from lib.helpers.duration import DurationConverter
from lib.helpers.global_alias import add_global_aliases, global_alias, remove_global_aliases
from lib.helpers.shorten import shorten_preserve
from lib.logic.reminders import create_reminder, get_all_reminders, get_reminder_count
from lib.views.pagination import PaginationV2View
from lib.views.reminders import RemindersPageContainer

if TYPE_CHECKING:
    from main import TitaniumBot


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class TemplateCog(commands.Cog, description="Create reminders."):
    """Create reminders"""

    ConvertedDuration = typing.Annotated[typing.Union[Optional[timedelta]], DurationConverter]

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        add_global_aliases(self, self.bot)

    async def cog_unload(self) -> None:
        remove_global_aliases(self, self.bot)

    async def cog_check(self, ctx: commands.Context["TitaniumBot"]) -> bool:
        if ctx.author.id not in self.bot.opt_out:
            return True

        embed = discord.Embed(
            title=f"{self.bot.error_emoji} Opted Out",
            description="You have opted out of data collection and cannot use reminder features.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)
        return False

    @commands.hybrid_group(name="reminder", fallback="create", description="Create a new reminder.")
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
    async def reminder_group(
        self,
        ctx: commands.Context["TitaniumBot"],
        mode: Literal["dm", "server"],
        time: ConvertedDuration,
        *,
        content: commands.Range[str, 1, 1000],
        ephemeral: bool = False,
    ) -> None:
        await ctx.defer(ephemeral=ephemeral)

        if not time:
            await ctx.reply(embed=invalid_duration(self.bot), ephemeral=ephemeral)
            return

        time_scheduled = ctx.message.created_at + time
        dm = mode == "dm"

        if not dm and not isinstance(ctx.channel, discord.abc.GuildChannel):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="You are trying to create a server channel reminder in DMs. Please set the `DM` option to enabled.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        if not dm and (ctx.interaction and not ctx.interaction.is_guild_integration()):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="Server channel reminders cannot be created as Titanium is not in the server. Please add Titanium to the server first.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        if not dm and (
            not ctx.permissions.view_channel
            or not ctx.permissions.send_messages
            or (ctx.interaction and not ctx.permissions.use_application_commands)
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Permissions",
                description="You don't have permission to create server reminders in this channel.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        if not dm and (
            not ctx.guild or not ctx.channel.permissions_for(ctx.guild.me).send_messages
        ):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Permissions",
                description="Titanium doesn't have permissins to send messages in this channel. Your reminder will not send correctly.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        if await get_reminder_count(ctx.author) >= 50:
            command_str = (
                "`/reminder list`" if ctx.interaction else f"`{ctx.clean_prefix}reminders`"
            )
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description=f"You can only create up to 50 reminders. Delete some old reminders using the {command_str} command.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        reminder = await create_reminder(
            content=content,
            time=time_scheduled,
            creator=ctx.author,
            dm=dm,
            guild_id=ctx.guild.id if ctx.guild else None,
            channel_id=ctx.channel.id,
            message_id=ctx.message.id if not dm and not ctx.interaction else None,
        )

        embed = discord.Embed(
            title=f"{self.bot.success_emoji} Created • `{reminder.id}`",
            description=f"I will remind you **{'in DMs' if dm else 'here'}** {format_dt(time_scheduled, style='R')} ({format_dt(time_scheduled, style='S')}).",
            colour=Colour.green(),
        )
        embed.add_field(name="Content", value=shorten_preserve(content, width=1024))
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        await ctx.reply(embed=embed, ephemeral=ephemeral)

    @reminder_group.command(name="list", description="View and manage your created reminders.")
    @global_alias("reminders")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @commands.cooldown(1, 5)
    async def reminder_list(
        self, ctx: commands.Context["TitaniumBot"], ephemeral: bool = False
    ) -> None:
        await ctx.defer(ephemeral=ephemeral)

        reminders = await get_all_reminders(ctx.author)
        reminder_chunks = discord.utils.as_chunks(reminders, 5)

        reminder_pages: list[RemindersPageContainer] = []
        for chunk in reminder_chunks:
            reminder_pages.append(
                RemindersPageContainer(ctx=ctx, reminders=chunk, reminder_count=len(reminders))
            )

        view = LayoutView(timeout=300)
        if not reminder_pages:
            view.add_item(
                RemindersPageContainer(ctx=ctx, reminders=[], reminder_count=len(reminders))
            )
        elif len(reminder_pages) > 1:
            view = PaginationV2View(pages=reminder_pages)
        else:
            view.add_item(reminder_pages[0])

        await ctx.reply(view=view, allowed_mentions=AllowedMentions.none(), ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(TemplateCog(bot))
