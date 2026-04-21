import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from main import TitaniumBot


LOGGER = logging.getLogger("cache")


async def get_or_fetch_message(
    bot: TitaniumBot, channel: discord.abc.Messageable, message_id: int
) -> discord.Message | None:
    # Try to get the message from cache
    message = discord.utils.get(bot.cached_messages, id=message_id)
    if message:
        LOGGER.debug(f"Got message from cache ({message_id})")
        return message

    # If not in cache, fetch from API
    try:
        LOGGER.debug(f"Fetching message from Discord ({message_id})")
        message = await channel.fetch_message(message_id)
        return message
    except discord.NotFound:
        return None


async def get_or_fetch_member(
    bot: TitaniumBot, guild: discord.Guild, user_id: int
) -> discord.Member | None:
    # Try to get the member from cache
    member = guild.get_member(user_id)
    if member:
        LOGGER.debug(f"Got member from cache (guild: {guild.id}, user: {user_id})")
        return member

    # If not in cache, fetch from API
    try:
        LOGGER.debug(f"Fetching member from Discord (guild: {guild.id}, user: {user_id})")
        member = await guild.fetch_member(user_id)
        return member
    except discord.NotFound:
        return None
