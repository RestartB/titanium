from typing import TYPE_CHECKING

from discord import ClientUser, Colour, Embed, Member, User

from ..duration import duration_to_timestring
from ..sql.sql import ModCase

if TYPE_CHECKING:
    from main import TitaniumBot


def warned(
    bot: TitaniumBot,
    user: Member | User,
    creator: Member | User | ClientUser,
    case: ModCase,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Warned • `{case.id}`",
        description=f"**Target:** {user.mention}\n**Reason:** {case.description or 'No reason provided.'}",
        colour=Colour.green(),
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
    bot: TitaniumBot,
    user: Member | User,
    creator: Member | User | ClientUser,
    case: ModCase,
    dm_success: bool = True,
    dm_error: str = "",
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Muted • `{case.id}`",
        description=f"**Target:** {user.mention}\n**Duration:** {duration_to_timestring(case.time_created, case.time_expires) if case.time_expires else 'Permanent'}\n**Reason:** {case.description or 'No reason provided.'}",
        colour=Colour.green(),
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
    bot: TitaniumBot,
    user: Member | User | ClientUser,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"{user.mention} is already muted.",
        colour=Colour.red(),
    )
    return embed


def unmuted(
    bot: TitaniumBot,
    user: Member | User,
    creator: Member | User | ClientUser,
    case: ModCase,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Unmuted • `{case.id}`",
        description=f"**Target:** {user.mention}",
        colour=Colour.green(),
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
    bot: TitaniumBot,
    user: Member | User | ClientUser,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"{user.mention} is not muted.",
        colour=Colour.red(),
    )
    return embed


def kicked(
    bot: TitaniumBot,
    user: Member | User,
    creator: Member | User | ClientUser,
    case: ModCase,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Kicked • `{case.id}`",
        description=f"**Target:** @{user.name} (`{user.id}`)\n**Reason:** {case.description or 'No reason provided.'}",
        colour=Colour.green(),
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
    bot: TitaniumBot,
    user: Member | User,
    creator: Member | User | ClientUser,
    case: ModCase,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Banned • `{case.id}`",
        description=f"**Target:** @{user.name} (`{user.id}`)\n**Duration:** {duration_to_timestring(case.time_created, case.time_expires) if case.time_expires else 'Permanent'}\n**Reason:** {case.description or 'No reason provided.'}",
        colour=Colour.green(),
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
    bot: TitaniumBot,
    user: Member | User,
    creator: Member | User | ClientUser,
    case: ModCase,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)}",
        description=f"**Target:** @{user.name} (`{user.id}`)",
        colour=Colour.green(),
    )

    embed.set_footer(text=f"@{creator.name}", icon_url=creator.display_avatar.url)

    if not dm_success:
        embed.add_field(
            name="Errors",
            value=f"Failed to send DM: {dm_error}",
            inline=False,
        )

    return embed


# Purged
def purged(
    bot: TitaniumBot,
    creator: Member | User | ClientUser,
    messages: int,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Purged",
        description=f"Purged {messages} messages.",
        colour=Colour.green(),
    )

    embed.set_footer(text=f"@{creator.name}", icon_url=creator.display_avatar.url)

    return embed


# Fallback done
def done(
    bot: TitaniumBot,
    user: Member | User,
    creator: Member | User | ClientUser,
    dm_success: bool,
    dm_error: str,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.success_emoji)} Done",
        colour=Colour.green(),
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
    bot: TitaniumBot,
    user: Member | User | ClientUser,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"{user.mention} is already banned.",
        colour=Colour.red(),
    )
    return embed


def already_unbanned(
    bot: TitaniumBot,
    user: Member | User | ClientUser,
) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"{user.mention} is not banned.",
        colour=Colour.red(),
    )
    return embed


def already_punishing(bot: TitaniumBot, user: Member | User | ClientUser) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"{user.mention} is already being punished. Please wait.",
        colour=Colour.red(),
    )
    return embed


def cannot_purge(bot: TitaniumBot) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description="Messages in this channel cannot be purged.",
        colour=Colour.red(),
    )
    return embed


def cant_mod_self(bot: TitaniumBot) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description="You cannot moderate yourself.",
        colour=Colour.red(),
    )
    return embed


def not_allowed(bot: TitaniumBot, user: Member | User | ClientUser) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"You do not have permission to perform this action on {user.mention}.",
        colour=Colour.red(),
    )
    return embed


def forbidden(bot: TitaniumBot, user: Member | User | ClientUser) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"Titanium does not have permission to perform this action on {user.mention}.",
        colour=Colour.red(),
    )
    return embed


def http_exception(bot: TitaniumBot, user: Member | User | ClientUser) -> Embed:
    embed = Embed(
        title=f"{str(bot.error_emoji)} Error",
        description=f"An error occurred while trying to perform this action on {user.mention}.",
        colour=Colour.red(),
    )
    return embed
