from collections.abc import Sequence
from typing import TYPE_CHECKING

from discord import Colour, Embed, Member, User
from discord.utils import format_dt
from sqlalchemy import Column

from lib.helpers.duration import duration_to_timestring
from lib.sql.sql import ModCase

if TYPE_CHECKING:
    from main import TitaniumBot


def cases(
    bot: TitaniumBot,
    cases: list[ModCase] | Sequence[ModCase],
    total: int,
    target: User | Member,
    user: User | Member,
) -> Embed:
    embed = Embed(
        title="Cases",
        description=f"You have **{total} cases** against your user."
        if target.id == user.id
        else f"Found **{total} cases** for this user.",
        colour=Colour.light_grey(),
    )

    embed.set_author(
        name=f"@{target.name}",
        icon_url=target.display_avatar.url,
    )

    for case in cases:
        embed.add_field(
            name=f"`{case.id}` • {bot.success_emoji if bool(case.resolved) else bot.warn_emoji} {'Resolved' if case.resolved else 'Open'}",
            value=f"-# Created {format_dt(case.time_created)}\n{case.description}",
            inline=False,
        )

    return embed


def case_embed(
    bot: TitaniumBot,
    case: ModCase,
    creator: User | int | Column[int],
    target: User | int | Column[int],
) -> Embed:
    description_lines = [
        f"**Status:** {bot.success_emoji if bool(case.resolved) else bot.warn_emoji} {'Resolved' if bool(case.resolved) else 'Open'}",
        f"**Type:** {case.type.name.capitalize()}",
        f"**Target:** {f'<@{target}> (`{target}`)' if isinstance(target, int) or isinstance(target, Column) else f'{target.mention} (`{target.id}`)'}\n",
        f"**Time Created:** {format_dt(case.time_created)}",
    ]

    if case.time_updated:
        description_lines.append(f"**Time Updated:** {format_dt(case.time_updated)}")

    description_lines.extend(
        [
            f"**Duration:** {duration_to_timestring(case.time_created, case.time_expires) if case.time_expires else 'Permanent'}\n",
            f"**Reason:** {case.description or 'No reason provided.'}",
            f"**Comments:** {len(case.comments)} comment{'s' if len(case.comments) > 1 else ''}",
        ]
    )

    embed = Embed(
        title=f"`{case.id}`",
        description="\n".join(description_lines),
        colour=Colour.light_grey(),
    )

    if isinstance(creator, int) or isinstance(creator, Column):
        embed.set_author(name=creator)
    else:
        embed.set_author(
            name=f"@{creator.name} ({creator.id})",
            icon_url=creator.display_avatar.url,
        )

    embed.timestamp = case.time_created
    return embed


def case_not_found(bot: TitaniumBot, case: str) -> Embed:
    return Embed(
        title=f"{bot.error_emoji} Not Found",
        description=f"Couldn't find a case with the ID `{case}` in this server.",
        colour=Colour.red(),
    )


def case_deleted(bot: TitaniumBot, case_id: str) -> Embed:
    return Embed(
        title=f"{bot.success_emoji} Case Deleted",
        description=f"Case `{case_id}` has been successfully deleted.",
        colour=Colour.green(),
    )


def comment_deleted(bot: TitaniumBot) -> Embed:
    return Embed(
        title=f"{bot.success_emoji} Comment Deleted",
        description="The comment has been successfully deleted.",
        colour=Colour.green(),
    )


def comment_edited(bot: TitaniumBot) -> Embed:
    return Embed(
        title=f"{bot.success_emoji} Comment Edited",
        description="The comment has been successfully edited.",
        colour=Colour.green(),
    )


def not_your_comment(bot: TitaniumBot) -> Embed:
    return Embed(
        title=f"{bot.error_emoji} Not Allowed",
        description="This is not your comment. Only the comment creator can modify it.",
        colour=Colour.red(),
    )
