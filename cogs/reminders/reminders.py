import typing
from datetime import timedelta
from typing import TYPE_CHECKING, Literal

import discord
from discord import Colour, app_commands
from discord.ext import commands
from discord.utils import format_dt

from lib.helpers.duration import DurationConverter
from lib.helpers.shorten import shorten_preserve
from lib.logic.reminders import create_reminder

if TYPE_CHECKING:
    from main import TitaniumBot


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class TemplateCog(commands.Cog, description="Create reminders."):
    """Create reminders"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    ConvertedDuration = typing.Annotated[typing.Union[timedelta], DurationConverter]

    @commands.hybrid_group(name="reminder", fallback="create", description="Create a new reminder.")
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
        content: str,
    ) -> None:
        await ctx.defer()
        time_scheduled = ctx.message.created_at + time
        dm = mode == "dm"

        if not dm and not isinstance(ctx.channel, discord.abc.GuildChannel):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="You are trying to create a server channel reminder in DMs. Please set the `DM` option to enabled.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed)
            return

        if not dm and (ctx.interaction and not ctx.interaction.is_guild_integration()):
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="Server channel reminders cannot be created as Titanium is not in the server. Please add Titanium to the server first.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed)
            return

        if not dm and not ctx.permissions.view_channel or not ctx.permissions.send_messages:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Error",
                description="You don't have permission to create server reminders in this channel.",
                colour=Colour.red(),
            )
            await ctx.reply(embed=embed)
            return

        reminder = await create_reminder(
            content=content,
            time=time_scheduled,
            creator=ctx.author,
            dm=dm,
            guild_id=ctx.guild.id if ctx.guild else None,
            channel_id=ctx.channel.id,
            message_id=ctx.message.id if not ctx.interaction else None,
        )

        embed = discord.Embed(
            title=f"{self.bot.success_emoji} Created • `{reminder.id}`",
            description=f"I will remind you **{'in DMs' if dm else 'here'}** {format_dt(time_scheduled, style='R')} ({format_dt(time_scheduled, style='S')}).",
            colour=Colour.green(),
        )
        embed.add_field(name="Content", value=shorten_preserve(content, width=1024))
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        await ctx.reply(embed=embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(TemplateCog(bot))
