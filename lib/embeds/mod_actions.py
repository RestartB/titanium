from typing import TYPE_CHECKING

from discord import Color, Embed, Member, User

from ..duration import duration_to_timestring
from ..sql import ModCases

if TYPE_CHECKING:
    from main import TitaniumBot


def warned(
    bot: "TitaniumBot",
    user: Member | User,
    creator: Member | User,
    case: ModCases,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Warned - `{case.id}`",
        description=f"**Target:** {user.mention}\n**Duration:** {duration_to_timestring(case.time_expires)}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    embed.set_footer(text=f"@{creator.name}", icon_url=creator.display_avatar.url)

    if not dm_success:
        embed.add_field(
            name="Errors",
            value=f"Failed to send DM: {dm_error}",
            inline=False,
        )

    return embed


def muted(
    bot: "TitaniumBot",
    user: Member | User,
    creator: Member | User,
    case: ModCases,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Muted - `{case.id}`",
        description=f"**Target:** {user.mention}\n**Duration:** {duration_to_timestring(case.time_expires)}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    embed.set_footer(text=f"@{creator.name}", icon_url=creator.display_avatar.url)

    if not dm_success:
        embed.add_field(
            name="Errors",
            value=f"Failed to send DM: {dm_error}",
            inline=False,
        )

    return embed


def already_muted(
    bot: "TitaniumBot",
    user: Member | User,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"{user.mention} is already muted.",
        color=Color.red(),
    )
    return embed


def unmuted(
    bot: "TitaniumBot",
    user: Member | User,
    creator: Member | User,
    case: ModCases,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Unmuted - `{case.id}`",
        description=f"**Target:** {user.mention}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    embed.set_footer(text=f"@{creator.name}", icon_url=creator.display_avatar.url)

    if not dm_success:
        embed.add_field(
            name="Errors",
            value=f"Failed to send DM: {dm_error}",
            inline=False,
        )

    return embed


def already_unmuted(
    bot: "TitaniumBot",
    user: Member | User,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"{user.mention} is not muted.",
        color=Color.red(),
    )
    return embed


def kicked(
    bot: "TitaniumBot",
    user: Member | User,
    creator: Member | User,
    case: ModCases,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Kicked - `{case.id}`",
        description=f"**Target:** {user.mention}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    embed.set_footer(text=f"@{creator.name}", icon_url=creator.display_avatar.url)

    if not dm_success:
        embed.add_field(
            name="Errors",
            value=f"Failed to send DM: {dm_error}",
            inline=False,
        )

    return embed


def banned(
    bot: "TitaniumBot",
    user: Member | User,
    creator: Member | User,
    case: ModCases,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Banned - `{case.id}`",
        description=f"**Target:** {user.mention}\n**Duration:** {duration_to_timestring(case.time_expires)}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    embed.set_footer(text=f"@{creator.name}", icon_url=creator.display_avatar.url)

    if not dm_success:
        embed.add_field(
            name="Errors",
            value=f"Failed to send DM: {dm_error}",
            inline=False,
        )

    return embed


def unbanned(
    bot: "TitaniumBot",
    user: Member | User,
    creator: Member | User,
    case: ModCases,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Unbanned - `{case.id}`",
        description=f"**Target:** {user.mention}\n**Reason:** {case.description or 'No reason provided.'}",
        color=Color.green(),
    )

    embed.set_footer(text=f"@{creator.name}", icon_url=creator.display_avatar.url)

    if not dm_success:
        embed.add_field(
            name="Errors",
            value=f"Failed to send DM: {dm_error}",
            inline=False,
        )

    return embed


# Fallback done
def done(
    bot: "TitaniumBot",
    user: Member | User,
    creator: Member | User,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Done",
        color=Color.green(),
    )

    embed.set_footer(text=f"@{creator.name}", icon_url=creator.display_avatar.url)

    if not dm_success:
        embed.add_field(
            name="Errors",
            value=f"Failed to send DM: {dm_error}",
            inline=False,
        )

    return embed


def already_banned(
    bot: "TitaniumBot",
    user: Member | User,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"{user.mention} is already banned.",
        color=Color.red(),
    )
    return embed


def not_in_guild(bot: "TitaniumBot", user: Member | User) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"@{user.name} is not in this server.",
        color=Color.red(),
    )
    return embed


def already_punishing(bot: "TitaniumBot", user: Member | User) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"{user.mention} is already being punished. Please wait.",
        color=Color.red(),
    )
    return embed


def forbidden(bot: "TitaniumBot", user: Member | User) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"Titanium does not have permission to perform this action on {user.mention}.",
        color=Color.red(),
    )
    return embed


def http_exception(bot: "TitaniumBot", user: Member | User) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"An error occurred while trying to perform this action on {user.mention}.",
        color=Color.red(),
    )
    return embed
