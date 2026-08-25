import logging
from typing import TYPE_CHECKING, Literal, overload

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


@overload
async def get_or_fetch_member(
    bot: TitaniumBot,
    guild: discord.Guild,
    user_id: int,
    user_fallback: Literal[False] = False,
    fetch: bool = True,
) -> discord.Member | None: ...


@overload
async def get_or_fetch_member(
    bot: TitaniumBot,
    guild: discord.Guild,
    user_id: int,
    user_fallback: Literal[True],
    fetch: bool = True,
) -> discord.Member | discord.User | None: ...


async def get_or_fetch_member(
    bot: TitaniumBot,
    guild: discord.Guild,
    user_id: int,
    user_fallback: bool = False,
    fetch: bool = True,
) -> discord.Member | discord.User | None:
    # Try to get the member from cache
    member = guild.get_member(user_id)
    if member or not fetch:
        LOGGER.debug(
            f"Got member from cache or fetch is disabled (guild: {guild.id}, user: {user_id})"
        )
        return member

    # If not in cache, fetch from API and cache
    try:
        LOGGER.debug(f"Fetching member from Discord (guild: {guild.id}, user: {user_id})")
        member = await guild.fetch_member(user_id)
        guild._add_member(member)
        LOGGER.debug(f"Cached member (guild: {guild.id}, user: {user_id})")

        return member
    except discord.NotFound:
        if not user_fallback:
            return None

        user = await get_or_fetch_user(bot, user_id)
        return user


async def get_or_fetch_user(
    bot: TitaniumBot, user_id: int, fetch: bool = True
) -> discord.User | None:
    # Try to get the user from cache
    user = bot.get_user(user_id)
    if user or not fetch:
        LOGGER.debug(f"Got user from cache or fetch is disabled (user: {user_id})")
        return user

    # If not in cache, fetch from API
    try:
        LOGGER.debug(f"Fetching user from Discord (user: {user_id})")
        user = await bot.fetch_user(user_id)
        return user
    except discord.NotFound:
        return None
