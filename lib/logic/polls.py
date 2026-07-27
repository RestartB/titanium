import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import discord

from lib.classes.guild_logger import GuildLogger
from lib.enums.scheduled_events import EventType
from lib.sql.sql import AnonymousPoll, ScheduledTask, get_session
from lib.views.polls import PollView

if TYPE_CHECKING:
    from main import TitaniumBot


async def create_anonymous_poll(
    bot: TitaniumBot,
    channel: discord.abc.MessageableChannel,
    creator: discord.User | discord.Member,
    title: str,
    choices: list[str],
    closing_time: datetime,
    show_live_results: bool,
    attachment: discord.Attachment | None = None,
) -> AnonymousPoll:
    if not isinstance(channel, discord.abc.GuildChannel):
        raise TypeError("Channel provided is not a guild channel")

    poll = AnonymousPoll(
        id=uuid.uuid4(),
        guild_id=channel.guild.id,
        channel_id=channel.id,
        creator_id=creator.id,
        content=title,
        choices=choices,
        closing_time=closing_time,
        show_live_results=show_live_results,
        scheduled_task=ScheduledTask(
            type=EventType.POLL_END,
            time_scheduled=closing_time,
            guild_id=channel.guild.id,
            channel_id=channel.id,
            user_id=creator.id,
        ),
    )

    if attachment:
        poll.image_url = attachment.url

    view = PollView(poll=poll, show_live_results=show_live_results)
    msg = await channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())

    poll.message_id = msg.id
    poll.scheduled_task.message_id = msg.id

    async with get_session() as session:
        session.add(poll)

    guild_logger = GuildLogger(bot=bot, guild=channel.guild)
    await guild_logger.titanium_anon_poll(poll, creator, msg, attachment)

    return poll
