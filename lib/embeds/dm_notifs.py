from typing import TYPE_CHECKING

from discord import ButtonStyle, Color, Embed
from discord.ext import commands
from discord.ui import Button

from ..duration import duration_to_timestring
from ..sql import ModCases

if TYPE_CHECKING:
    from main import TitaniumBot


def warned_dm(
    bot: "TitaniumBot", ctx: commands.Context[commands.Bot], case: ModCases
) -> Embed:
    embed = Embed(
        title=f"{str(bot.warn_emoji)} You got warned - {case.id}",
        description=f"A moderator has warned you in **{ctx.guild.name if ctx.guild else ''}.**\n**Duration:** {duration_to_timestring(case.time_expires)}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.red(),
    )

    return embed


def muted_dm(
    bot: "TitaniumBot", ctx: commands.Context[commands.Bot], case: ModCases
) -> Embed:
    embed = Embed(
        title=f"{str(bot.warn_emoji)} You got muted - {case.id}",
        description=f"A moderator has muted you in **{ctx.guild.name if ctx.guild else ''}.**\n**Duration:** {duration_to_timestring(case.time_expires)}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.red(),
    )

    return embed


def kicked_dm(
    bot: "TitaniumBot", ctx: commands.Context[commands.Bot], case: ModCases
) -> Embed:
    embed = Embed(
        title=f"{str(bot.warn_emoji)} You got kicked - {case.id}",
        description=f"A moderator has kicked you from **{ctx.guild.name if ctx.guild else ''}.**\n**Duration:** {duration_to_timestring(case.time_expires)}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.red(),
    )

    return embed


def banned_dm(
    bot: "TitaniumBot", ctx: commands.Context[commands.Bot], case: ModCases
) -> Embed:
    embed = Embed(
        title=f"{str(bot.warn_emoji)} You got banned - {case.id}",
        description=f"A moderator has banned you from **{ctx.guild.name if ctx.guild else ''}.**\n**Duration:** {duration_to_timestring(case.time_expires)}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.red(),
    )

    return embed


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
