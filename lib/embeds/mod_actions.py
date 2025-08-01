from discord import Color, Embed, Member, User

from ..duration import duration_to_timestring
from ..sql import ModCases


def warned(user: Member | User, creator: Member, case: ModCases) -> Embed:
    embed = Embed(
        title=f"Warned - {case.id}",
        description=f"Target: {user.mention}\nModerator: {creator.mention}\nDuration: {duration_to_timestring(case.time_expires)}\nReason: {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    return embed


def muted(user: Member | User, creator: Member, case: ModCases) -> Embed:
    embed = Embed(
        title=f"Muted - {case.id}",
        description=f"Target: {user.mention}\nModerator: {creator.mention}\nDuration: {duration_to_timestring(case.time_expires)}\nReason: {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    return embed


def kicked(user: Member | User, creator: Member, case: ModCases) -> Embed:
    embed = Embed(
        title=f"Kicked - {case.id}",
        description=f"Target: {user.mention}\nModerator: {creator.mention}\nReason: {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    return embed


def banned(user: Member | User, creator: Member, case: ModCases) -> Embed:
    embed = Embed(
        title=f"Banned - {case.id}",
        description=f"Target: {user.mention}\nModerator: {creator.mention}\nDuration: {duration_to_timestring(case.time_expires)}\nReason: {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    return embed


def not_in_guild(user: Member | User) -> Embed:
    embed = Embed(
        title="Error",
        description=f"@{user.name} is not in this server.",
        color=Color.red(),
    )
    return embed


def already_punishing(user: Member | User) -> Embed:
    embed = Embed(
        title="Error",
        description=f"{user.mention} is already being punished. Please wait.",
        color=Color.red(),
    )
    return embed
