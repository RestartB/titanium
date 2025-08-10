from typing import TYPE_CHECKING

from discord import Color, Embed, User
from sqlalchemy import Column

from ..duration import duration_to_timestring
from ..sql import ModCases

if TYPE_CHECKING:
    from main import TitaniumBot


def case_embed(
    bot: "TitaniumBot",
    case: ModCases,
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
