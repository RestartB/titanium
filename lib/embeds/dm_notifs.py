from typing import TYPE_CHECKING

from discord import ButtonStyle, Colour, Embed, Guild, Member, Message
from discord.ext import commands
from discord.ui import Button

from ..duration import duration_to_timestring
from ..sql.sql import ModCase

if TYPE_CHECKING:
    from main import TitaniumBot


def warned_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
    case: ModCase,
) -> Embed:
    return Embed(
        title=f"{bot.warn_emoji} You got warned • `{case.id}`",
        description=f"A moderator has warned you in **{ctx.guild.name if ctx.guild else ''}.**\n**Reason:** {case.description or 'No reason provided.'}",
        colour=Colour.red(),
    )


def muted_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
    case: ModCase,
) -> Embed:
    return Embed(
        title=f"{bot.warn_emoji} You got muted • `{case.id}`",
        description=f"A moderator has muted you in **{ctx.guild.name if ctx.guild else ''}.**\n**Duration:** {duration_to_timestring(case.time_created, case.time_expires) if case.time_expires else 'Permanent'}\n**Reason:** {case.description or 'No reason provided.'}",
        colour=Colour.red(),
    )


def unmuted_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
    case: ModCase,
) -> Embed:
    return Embed(
        title=f"{bot.success_emoji} You got unmuted • `{case.id}`",
        description=f"A moderator has unmuted you in **{ctx.guild.name if ctx.guild else ''}!**",
        colour=Colour.green(),
    )


def kicked_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
    case: ModCase,
) -> Embed:
    return Embed(
        title=f"{bot.warn_emoji} You got kicked • `{case.id}`",
        description=f"A moderator has kicked you from **{ctx.guild.name if ctx.guild else ''}.**\n**Reason:** {case.description or 'No reason provided.'}",
        colour=Colour.red(),
    )


def banned_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
    case: ModCase,
) -> Embed:
    return Embed(
        title=f"{bot.warn_emoji} You got banned • `{case.id}`",
        description=f"A moderator has banned you from **{ctx.guild.name if ctx.guild else ''}.**\n**Duration:** {duration_to_timestring(case.time_created, case.time_expires) if case.time_expires else 'Permanent'}\n**Reason:** {case.description or 'No reason provided.'}",
        colour=Colour.red(),
    )


def unbanned_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
    case: ModCase | None,
) -> Embed:
    return Embed(
        title=f"{bot.success_emoji} You got unbanned{f' • `{case.id}`' if case else ''}",
        description=f"A moderator has unbanned you from **{ctx.guild.name if ctx.guild else ''}!**",
        colour=Colour.green(),
    )


def jump_button(guild: Guild) -> Button:
    string = f"Sent from {guild.name}"

    return Button(
        style=ButtonStyle.url,
        label=(string if len(string) <= 80 else string[:77] + "..."),
        url=f"https://discord.com/channels/{guild.id}",
    )
