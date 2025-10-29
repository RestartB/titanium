from typing import Optional

import discord
import humanize


def resolve_counter(
    guild: discord.Guild, type: str, name: str, target_activity: Optional[str] = None
) -> str:
    """Resolve the server counter name for a channel."""

    if type == "total_members":
        updated_value = 0

        if guild.member_count:
            updated_value = guild.member_count
    elif type == "users":
        updated_value = 0

        for member in guild.members:
            if not member.bot:
                updated_value += 1
    elif type == "bots":
        updated_value = 0

        for member in guild.members:
            if member.bot:
                updated_value += 1
    elif type == "online_members":
        updated_value = 0

        for member in guild.members:
            if member.status != discord.Status.offline:
                updated_value += 1
    elif type == "members_status_online":
        updated_value = 0

        for member in guild.members:
            if member.status == discord.Status.online:
                updated_value += 1
    elif type == "members_status_idle":
        updated_value = 0

        for member in guild.members:
            if member.status == discord.Status.idle:
                updated_value += 1
    elif type == "members_status_dnd":
        updated_value = 0

        for member in guild.members:
            if member.status == discord.Status.dnd:
                updated_value += 1
    elif type == "members_activity":
        updated_value = 0

        for member in guild.members:
            if member.activity is not None:
                for activity in member.activities:
                    if activity.type != discord.ActivityType.custom:
                        updated_value += 1
                        break
    elif type == "members_custom_status":
        updated_value = 0

        for member in guild.members:
            if member.activity is not None:
                for activity in member.activities:
                    if activity.type == discord.ActivityType.custom:
                        updated_value += 1
                        break
    elif type == "offline_members":
        updated_value = 0

        for member in guild.members:
            if member.status == discord.Status.offline:
                updated_value += 1
    elif type == "channels":
        updated_value = (
            len(guild.text_channels)
            + len(guild.voice_channels)
            + len(guild.stage_channels)
            + len(guild.forums)
        )
    elif type == "activity":
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
