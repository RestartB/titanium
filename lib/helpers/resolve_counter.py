from typing import Optional

import discord
import humanize

from lib.enums.server_counters import ServerCounterType


def resolve_counter(
    guild: discord.Guild, type: ServerCounterType, name: str, target_activity: Optional[str] = None
) -> str:
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
    elif type == ServerCounterType.MEMBERS_STATUS_ONLINE:
        updated_value = 0

        for member in guild.members:
            if member.status == discord.Status.online:
                updated_value += 1
    elif type == ServerCounterType.MEMBERS_STATUS_IDLE:
        updated_value = 0

        for member in guild.members:
            if member.status == discord.Status.idle:
                updated_value += 1
    elif type == ServerCounterType.MEMBERS_STATUS_DND:
        updated_value = 0

        for member in guild.members:
            if member.status == discord.Status.dnd:
                updated_value += 1
    elif type == ServerCounterType.MEMBERS_ACTIVITY:
        updated_value = 0

        for member in guild.members:
            if member.activity is not None:
                for activity in member.activities:
                    if activity.type != discord.ActivityType.custom:
                        updated_value += 1
                        break
    elif type == ServerCounterType.MEMBERS_CUSTOM_STATUS:
        updated_value = 0

        for member in guild.members:
            if member.activity is not None:
                for activity in member.activities:
                    if activity.type == discord.ActivityType.custom:
                        updated_value += 1
                        break
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
    elif type == ServerCounterType.ACTIVITY:
        updated_value = 0

        if target_activity is not None:
            for member in guild.members:
                for activity in member.activities:
                    if (
                        activity.name is not None
                        and activity.name.lower() == target_activity.lower()
                    ):
                        updated_value += 1
                        break
    else:
        return ""

    return name.replace("{value}", humanize.intcomma(updated_value))
