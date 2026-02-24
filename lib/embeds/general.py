from typing import TYPE_CHECKING

from discord import Colour, Embed, Member, User

if TYPE_CHECKING:
    from main import TitaniumBot


def guild_only(bot: TitaniumBot) -> Embed:
    return Embed(
        title=f"{bot.error_emoji} Server Only Command",
        description="This command can only be used in servers.",
        colour=Colour.red(),
    )


def not_in_guild(bot: TitaniumBot, user: Member | User) -> Embed:
    return Embed(
        title=f"{bot.error_emoji} Error",
        description=f"@{user.name} is not in this server.",
        colour=Colour.red(),
    )


def cancelled(bot: TitaniumBot) -> Embed:
    return Embed(
        title=f"{bot.error_emoji} Cancelled.",
        colour=Colour.red(),
    )
