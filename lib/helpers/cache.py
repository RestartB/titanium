from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from main import TitaniumBot


async def get_or_fetch_message(
    bot: TitaniumBot, channel: discord.abc.Messageable, message_id: int
) -> discord.Message | None:
    # Try to get the message from cache
    message = discord.utils.get(bot.cached_messages, id=message_id)
    if message:
        return message

    # If not in cache, fetch from API
    try:
        message = await channel.fetch_message(message_id)
        return message
    except discord.NotFound:
        return None
