from typing import Sequence

import discord

from lib.sql.sql import LeaderboardUserStats


def generate_lb_embeds(
    guild: discord.Guild | None,
    author: discord.User | discord.Member,
    top_users: Sequence[LeaderboardUserStats],
    title,
    attr: str,
    show_levels: bool = False,
) -> list[discord.Embed]:
    if not guild:
        return []

    pages: Sequence[discord.Embed] = []
    page_size = 15

    embed = discord.Embed(
        title=title,
        colour=discord.Colour.random(),
    )
    embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)

    for i, user_stats in enumerate(top_users, start=1):
        member = guild.get_member(user_stats.user_id)

        if embed.description:
            embed.description += f"\n{i}. {member.mention if member else f'`{user_stats.user_id}`'} - {getattr(user_stats, attr)}XP{f', Level {user_stats.level}' if show_levels else ''}"
        else:
            embed.description = f"{i}. {member.mention if member else f'`{user_stats.user_id}`'} - {getattr(user_stats, attr)}XP{f', Level {user_stats.level}' if show_levels else ''}"

        if i % page_size == 0:
            pages.append(embed)

            embed = discord.Embed(
                title=title,
                colour=discord.Colour.random(),
            )
            embed.set_author(
                name=guild.name,
                icon_url=guild.icon.url if guild.icon else None,
            )

    if embed.description:
        pages.append(embed)

    pages[0].set_footer(
        text=f"Controlling: @{author.name}" if len(pages) > 1 else f"@{author.name}",
        icon_url=author.display_avatar.url,
    )

    return pages
