from typing import TYPE_CHECKING

from discord import Color, Embed, Member, User

if TYPE_CHECKING:
    from main import TitaniumBot


def not_in_guild(bot: "TitaniumBot", user: Member | User) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"@{user.name} is not in this server.",
        color=Color.red(),
    )
    return embed


def cancelled(bot: "TitaniumBot") -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Cancelled.",
        color=Color.red(),
    )
    return embed
