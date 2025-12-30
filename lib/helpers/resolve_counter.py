import discord
import humanize
from sqlalchemy import func, select

from lib.enums.server_counters import ServerCounterType
from lib.sql.sql import LeaderboardUserStats, get_session


async def resolve_counter(guild: discord.Guild, type: ServerCounterType, name: str) -> str:
    """Resolve the server counter name for a channel."""

    if type == ServerCounterType.TOTAL_MEMBERS:
        updated_value = 0

        if guild.member_count:
            updated_value = guild.member_count
    elif type == ServerCounterType.USERS:
        updated_value = 0

        for member in guild.members:
            if not member.bot:
                updated_value += 1
    elif type == ServerCounterType.BOTS:
        updated_value = 0

        for member in guild.members:
            if member.bot:
                updated_value += 1
    elif type == ServerCounterType.ONLINE_MEMBERS:
        updated_value = 0

        for member in guild.members:
            if member.status != discord.Status.offline:
                updated_value += 1
    elif type == ServerCounterType.OFFLINE_MEMBERS:
        updated_value = 0

        for member in guild.members:
            if member.status == discord.Status.offline:
                updated_value += 1
    elif type == ServerCounterType.CHANNELS:
        updated_value = (
            len(guild.text_channels)
            + len(guild.voice_channels)
            + len(guild.stage_channels)
            + len(guild.forums)
        )
    elif type == ServerCounterType.CATEGORIES:
        updated_value = len(guild.categories)
    elif type == ServerCounterType.ROLES:
        updated_value = len(guild.roles) - 1
    elif type == ServerCounterType.TOTAL_XP:
        updated_value = 0

        async with get_session() as session:
            stmt = select(func.sum(LeaderboardUserStats.xp)).where(
                LeaderboardUserStats.guild_id == guild.id
            )

            result = await session.execute(stmt)
            total_xp = result.scalar()

            updated_value = total_xp or 0
    else:
        return ""

    return name.replace("{value}", humanize.intcomma(updated_value))
