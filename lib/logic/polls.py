import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import discord

from lib.enums.scheduled_events import EventType
from lib.sql.sql import AnonymousPoll, ScheduledTask, get_session
from lib.views.polls import PollView

if TYPE_CHECKING:
    from main import TitaniumBot


async def create_anonymous_poll(
    bot: TitaniumBot,
    guild_id: int,
    channel: discord.abc.MessageableChannel,
    creator: discord.User | discord.Member,
    title: str,
    choices: list[str],
    closing_time: datetime,
) -> AnonymousPoll:
    poll = AnonymousPoll(
        id=uuid.uuid4(),
        guild_id=guild_id,
        channel_id=channel.id,
        creator_id=creator.id,
        content=title,
        choices=choices,
        closing_time=closing_time,
        scheduled_task=ScheduledTask(
            type=EventType.POLL_END,
            time_scheduled=closing_time,
            guild_id=guild_id,
            channel_id=channel.id,
            user_id=creator.id,
        ),
    )

    view = PollView(bot=bot, poll=poll)
    msg = await channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())

    poll.message_id = msg.id
    poll.scheduled_task.message_id = msg.id

    async with get_session() as session:
        session.add(poll)

    return poll
