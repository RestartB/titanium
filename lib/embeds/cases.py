from typing import TYPE_CHECKING, Sequence

from discord import Colour, Embed, Member, User
from sqlalchemy import Column

from ..duration import duration_to_timestring
from ..sql.sql import ModCase

if TYPE_CHECKING:
    from main import TitaniumBot


def cases(
    bot: TitaniumBot,
    cases: list[ModCase] | Sequence[ModCase],
    total: int,
    current_page: int,
    total_pages: int,
    target: User | Member,
    user: User | Member,
) -> Embed:
    embed = Embed(
        title="Cases",
        description=f"You have **{total} cases** against your user."
        if target.id == user.id
        else f"Found **{total} cases** for this user.",
        colour=Colour.blue(),
    )

    embed.set_author(
        name=f"@{target.name}",
        icon_url=target.display_avatar.url,
    )

    for case in cases:
        embed.add_field(
            name=f"`{case.id}` • {str(bot.error_emoji) if bool(case.resolved) else str(bot.success_emoji)} {'Closed' if case.resolved else 'Open'}",
            value=f"-# Created <t:{int(case.time_created.timestamp())}:f>\n{case.description}",
            inline=False,
        )

    embed.set_footer(
        text=f"@{user.name}{f' • Page {current_page}/{total_pages}' if total_pages > 1 else ''}",
        icon_url=user.display_avatar.url,
    )

    return embed


def case_embed(
    bot: TitaniumBot,
    case: ModCase,
    creator: User | int | Column[int],
    target: User | int | Column[int],
) -> Embed:
    description_lines = [
        f"**Status:** {str(bot.error_emoji) if bool(case.resolved) else str(bot.success_emoji)} {'Closed' if bool(case.resolved) else 'Open'}",
        f"**Type:** {case.type}",
        f"**Target:** {f'<@{target}> (`{target}`)' if isinstance(target, int) or isinstance(target, Column) else f'{target.mention} (`{target.id}`)'}",
        f"**Time Created:** <t:{int(case.time_created.timestamp())}:f>",
    ]

    if case.time_updated:
        description_lines.append(f"**Time Updated:** <t:{int(case.time_updated.timestamp())}:f>")

    description_lines.extend(
        [
            f"**Duration:** {duration_to_timestring(case.time_created, case.time_expires) if case.time_expires else 'Permanent'}",
            f"**Reason:** {case.description or 'No reason provided.'}",
        ]
    )

    embed = Embed(
        title=f"Case `{case.id}`",
        description="\n".join(description_lines),
        colour=Colour.blue(),
    )

    if isinstance(creator, int) or isinstance(creator, Column):
        embed.set_footer(text=creator)
    else:
        embed.set_footer(
            text=f"@{creator.name} ({creator.id})",
            icon_url=creator.display_avatar.url,
        )

    embed.timestamp = case.time_created  # pyright: ignore[reportAttributeAccessIssue]
    return embed


def case_not_found(bot: TitaniumBot, case: str) -> Embed:
    return Embed(
        title=f"{str(bot.error_emoji)} Case Not Found",
        description=f"Couldn't find a case with the ID `{case}` in this server.",
        colour=Colour.red(),
    )


def case_deleted(bot: TitaniumBot, case_id: str) -> Embed:
    return Embed(
        title=f"{str(bot.success_emoji)} Case Deleted",
        description=f"Case `{case_id}` has been successfully deleted.",
        colour=Colour.green(),
    )
