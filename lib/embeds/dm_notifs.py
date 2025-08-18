from typing import TYPE_CHECKING

from discord import ButtonStyle, Color, Embed
from discord.ext import commands
from discord.ui import Button

from ..duration import duration_to_timestring
from ..sql import ModCase

if TYPE_CHECKING:
    from main import TitaniumBot


def warned_dm(
    bot: "TitaniumBot", ctx: commands.Context[commands.Bot], case: ModCase
) -> Embed:
    return Embed(
        title=f"{str(bot.warn_emoji)} You got warned • {case.id}",
        description=f"A moderator has warned you in **{ctx.guild.name if ctx.guild else ''}.**\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.red(),
    )


def muted_dm(
    bot: "TitaniumBot", ctx: commands.Context[commands.Bot], case: ModCase
) -> Embed:
    return Embed(
        title=f"{str(bot.warn_emoji)} You got muted • {case.id}",
        description=f"A moderator has muted you in **{ctx.guild.name if ctx.guild else ''}.**\n**Duration:** {duration_to_timestring(case.time_created, case.time_expires) if case.time_expires else 'Permanent'}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.red(),
    )


def unmuted_dm(
    bot: "TitaniumBot", ctx: commands.Context[commands.Bot], case: ModCase
) -> Embed:
    return Embed(
        title=f"{str(bot.success_emoji)} You got unmuted • {case.id}",
        description=f"A moderator has unmuted you in **{ctx.guild.name if ctx.guild else ''}!",
        color=Color.green(),
    )


def kicked_dm(
    bot: "TitaniumBot", ctx: commands.Context[commands.Bot], case: ModCase
) -> Embed:
    return Embed(
        title=f"{str(bot.warn_emoji)} You got kicked • {case.id}",
        description=f"A moderator has kicked you from **{ctx.guild.name if ctx.guild else ''}.**\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.red(),
    )


def banned_dm(
    bot: "TitaniumBot", ctx: commands.Context[commands.Bot], case: ModCase
) -> Embed:
    return Embed(
        title=f"{str(bot.warn_emoji)} You got banned • {case.id}",
        description=f"A moderator has banned you from **{ctx.guild.name if ctx.guild else ''}.**\n**Duration:** {duration_to_timestring(case.time_created, case.time_expires) if case.time_expires else 'Permanent'}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.red(),
    )


def unbanned_dm(
    bot: "TitaniumBot", ctx: commands.Context[commands.Bot], case: ModCase
) -> Embed:
    return Embed(
        title=f"{str(bot.success_emoji)} You got unbanned • {case.id}",
        description=f"A moderator has unbanned you from **{ctx.guild.name if ctx.guild else ''}!",
        color=Color.green(),
    )


def jump_button(ctx: commands.Context[commands.Bot]) -> Button:
    if ctx.guild is None:
        return Button(
            style=ButtonStyle.gray,
            disabled=True,
            label="Server Link Unavailable",
        )

    string = f"Sent from {ctx.guild.name}"

    return Button(
        style=ButtonStyle.url,
        label=(string if len(string) <= 80 else string[:77] + "..."),
        url=f"https://discord.com/channels/{ctx.guild.id}",
    )
