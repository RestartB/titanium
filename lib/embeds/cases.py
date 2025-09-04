from typing import TYPE_CHECKING, Sequence

from discord import Color, Embed, Member, User
from sqlalchemy import Column

from ..duration import duration_to_timestring
from ..sql import ModCase

if TYPE_CHECKING:
    from main import TitaniumBot


def cases(
    bot: "TitaniumBot",
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
        color=Color.blue(),
    )

    embed.set_author(
        name=target.name,
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
    bot: "TitaniumBot",
    case: ModCase,
    creator: User | int | Column[int],
    target: User | int | Column[int],
) -> Embed:
    embed = Embed(
        title=f"Case `{case.id}`",
        description=f"""
        **Status:** {str(bot.error_emoji) if bool(case.resolved) else str(bot.success_emoji)} {"Closed" if bool(case.resolved) else "Open"}
        **Type:** {case.type}
        **Target:** {f"<@{target}> (`{target}`)" if isinstance(target, int) or isinstance(target, Column) else f"{target.mention} (`{target.id}`)"}
        **Time Created:** <t:{int(case.time_created.timestamp())}:f>
        {f"**Time Updated:** <t:{int(case.time_updated.timestamp())}:f>" if case.time_updated else ""}
        **Duration:** {duration_to_timestring(case.time_created, case.time_expires) if case.time_expires else "Permanent"}
        **Reason:** {case.description or "No reason provided."}
        """,
        color=Color.blue(),
    )

    if isinstance(creator, int) or isinstance(creator, Column):
        embed.set_footer(text=f"by {creator}")
    else:
        embed.set_footer(
            text=f"by @{creator.name} ({creator.id})",
            icon_url=creator.display_avatar.url,
        )

    embed.timestamp = case.time_created  # pyright: ignore[reportAttributeAccessIssue]
    return embed


def case_not_found(bot: "TitaniumBot", case: str) -> Embed:
    return Embed(
        title=f"{str(bot.error_emoji)} Case Not Found",
        description=f"Couldn't find a case with the ID `{case}` in this server.",
        color=Color.red(),
    )


def case_deleted(bot: "TitaniumBot", case_id: int) -> Embed:
    return Embed(
        title=f"{str(bot.success_emoji)} Case Deleted",
        description=f"Case `{case_id}` has been successfully deleted.",
        color=Color.green(),
    )
