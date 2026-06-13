from datetime import datetime
from typing import Optional

import discord
from sqlalchemy import func, select

from lib.enums.scheduled_events import EventType
from lib.sql.sql import Reminder, ScheduledTask, get_session


async def create_reminder(
    content: str,
    time: datetime,
    creator: discord.User | discord.Member,
    dm: bool,
    guild_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> Reminder:
    reminder = Reminder(
        guild_id=guild_id,
        channel_id=channel_id,
        user_id=creator.id,
        dm=dm,
        time=time,
        content=content,
        scheduled_task=ScheduledTask(
            type=EventType.REMINDER,
            time_scheduled=time,
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=creator.id,
            message_id=message_id,
        ),
    )

    async with get_session() as session:
        session.add(reminder)

    return reminder


async def get_all_reminders(creator: discord.User | discord.Member) -> list[Reminder]:
    async with get_session() as session:
        stmt = select(Reminder).where(Reminder.user_id == creator.id)
        result = await session.execute(stmt)

    return list(result.scalars().all())


async def get_reminder_count(creator: discord.User | discord.Member) -> int:
    async with get_session() as session:
        stmt = select(func.count()).select_from(Reminder).where(Reminder.user_id == creator.id)
        result = await session.execute(stmt)

    return result.scalar() or 0


async def get_reminder(
    reminder_id: str, creator: discord.User | discord.Member
) -> Optional[Reminder]:
    async with get_session() as session:
        stmt = select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == creator.id)
        return (await session.execute(stmt)).scalar_one_or_none()
