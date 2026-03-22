from typing import TYPE_CHECKING, Optional

from discord import ButtonStyle, Colour, Embed, Guild, Member, Message
from discord.ext import commands
from discord.ui import Button

if TYPE_CHECKING:
    from main import TitaniumBot


def warned_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
    reason: Optional[str],
) -> Embed:
    return Embed(
        title=f"{bot.warn_emoji} Warned",
        description=f"A moderator has warned you in **{ctx.guild.name if ctx.guild else ''}.**\n**Reason:** {reason or 'No reason provided.'}",
        colour=Colour.red(),
    )


def muted_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
    duration: str,
    reason: Optional[str],
) -> Embed:
    return Embed(
        title=f"{bot.warn_emoji} Muted",
        description=f"A moderator has muted you in **{ctx.guild.name if ctx.guild else ''}.**\n**Duration:** {duration}\n**Reason:** {reason or 'No reason provided.'}",
        colour=Colour.red(),
    )


def unmuted_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
) -> Embed:
    return Embed(
        title=f"{bot.success_emoji} Unmuted",
        description=f"A moderator has unmuted you in **{ctx.guild.name if ctx.guild else ''}!**",
        colour=Colour.green(),
    )


def kicked_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
    reason: Optional[str],
) -> Embed:
    return Embed(
        title=f"{bot.warn_emoji} Kicked",
        description=f"A moderator has kicked you from **{ctx.guild.name if ctx.guild else ''}.**\n**Reason:** {reason or 'No reason provided.'}",
        colour=Colour.red(),
    )


def banned_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
    duration: str,
    reason: Optional[str],
) -> Embed:
    return Embed(
        title=f"{bot.warn_emoji} Banned",
        description=f"A moderator has banned you from **{ctx.guild.name if ctx.guild else ''}.**\n**Duration:** {duration}\n**Reason:** {reason or 'No reason provided.'}",
        colour=Colour.red(),
    )


def unbanned_dm(
    bot: TitaniumBot,
    ctx: commands.Context["TitaniumBot"] | Message | Member,
) -> Embed:
    return Embed(
        title=f"{bot.success_emoji} Unbanned",
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
