from discord import Button, ButtonStyle, Color, Embed
from discord.ext import commands

from ..duration import duration_to_timestring
from ..sql import ModCases


def warned_dm(ctx: commands.Context[commands.Bot], case: ModCases) -> Embed:
    embed = Embed(
        title=f"You got warned - {case.id}",
        description=f"A moderator has warned you in **{ctx.guild.name}.**\nDuration: {duration_to_timestring(case.time_expires)}\nReason: {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    return embed


def muted_dm(ctx: commands.Context[commands.Bot], case: ModCases) -> Embed:
    embed = Embed(
        title=f"You got muted - {case.id}",
        description=f"A moderator has muted you in **{ctx.guild.name}.**\nDuration: {duration_to_timestring(case.time_expires)}\nReason: {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    return embed


def kicked_dm(ctx: commands.Context[commands.Bot], case: ModCases) -> Embed:
    embed = Embed(
        title=f"You got kicked - {case.id}",
        description=f"A moderator has kicked you from **{ctx.guild.name}.**\nDuration: {duration_to_timestring(case.time_expires)}\nReason: {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    return embed


def banned_dm(ctx: commands.Context[commands.Bot], case: ModCases) -> Embed:
    embed = Embed(
        title=f"You got banned - {case.id}",
        description=f"A moderator has banned you from **{ctx.guild.name}.**\nDuration: {duration_to_timestring(case.time_expires)}\nReason: {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    return embed


def jump_button(ctx: commands.Context[commands.Bot]) -> Button:
    string = f"Sent from {ctx.guild.name}"

    return Button(
        style=ButtonStyle.url,
        label=(string if len(string) <= 80 else string[:77] + "..."),
        url=f"https://discord.com/channels/{ctx.guild.id}",
    )
