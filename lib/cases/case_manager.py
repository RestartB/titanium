from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional, Sequence

from discord import Guild
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..duration import DurationConverter
from ..sql.sql import ModCase, ScheduledTask


class CaseNotFoundException(Exception):
    """Exception raised when a case is not found."""


class GuildModCaseManager:
    def __init__(self, guild: Guild, session: AsyncSession):
        self.guild = guild
        self.session = session

    async def get_cases(self) -> Sequence[ModCase]:
        stmt = (
            select(ModCase)
            .where(ModCase.guild_id == self.guild.id)
            .options(selectinload(ModCase.comments))
        )

        result = await self.session.execute(stmt)
        cases = result.scalars().all()

        return cases

    async def get_case_by_id(self, case_id: str) -> ModCase:
        stmt = (
            select(ModCase)
            .where(ModCase.id == case_id, ModCase.guild_id == self.guild.id)
            .options(selectinload(ModCase.comments))
        )

        result = await self.session.execute(stmt)
        case = result.scalar_one_or_none()

        if not case:
            raise CaseNotFoundException("Case not found")

        return case

    async def get_cases_by_user(self, user_id: int) -> Sequence[ModCase]:
        stmt = (
            select(ModCase)
            .where(ModCase.user_id == user_id, ModCase.guild_id == self.guild.id)
            .options(selectinload(ModCase.comments))
            .order_by(ModCase.time_created.desc())
        )

        result = await self.session.execute(stmt)
        cases = result.scalars().all()

        return cases

    async def create_case(
        self,
        action: Literal["ban", "kick", "mute", "warn"],
        user_id: int,
        creator_user_id: int,
        reason: Optional[str],
        duration: Annotated[timedelta, DurationConverter] | None = None,
        external: bool = False,
    ) -> ModCase:
        case = ModCase(
            guild_id=self.guild.id,
            type=action,
            user_id=user_id,
            creator_user_id=creator_user_id,
            proof_msg_id=None,
            proof_channel_id=None,
            proof_text=None,
            time_created=datetime.now(),
            description=reason,
            external=external,
        )

        if duration:
            case.time_expires = datetime.now() + duration

        self.session.add(case)
        await self.session.commit()

        if duration and action == "mute":
            # Schedule mute refreshes
            await self._schedule_mute_refreshes(case, duration)
        elif duration is None and action == "mute":
            # Permanent mute, schedule refresh every 27 days
            self.session.add(
                ScheduledTask(
                    guild_id=self.guild.id,
                    user_id=user_id,
                    case_id=case.id,
                    type="perma_mute_refresh",
                    time_scheduled=datetime.now() + timedelta(days=27),
                )
            )
            await self.session.commit()
        elif duration and action == "ban":
            # Schedule unban
            self.session.add(
                ScheduledTask(
                    guild_id=self.guild.id,
                    user_id=user_id,
                    case_id=case.id,
                    type="unban",
                    time_scheduled=datetime.now() + duration,
                )
            )
            await self.session.commit()

        return case

    async def update_case(
        self,
        case_id: str,
        reason: Optional[str],
        resolved: Optional[bool],
        duration: Annotated[timedelta, DurationConverter] | None = None,
    ) -> ModCase:
        case = await self.get_case_by_id(case_id)

        if not case:
            raise CaseNotFoundException("Case not found")

        if reason:
            case.description = reason

        if resolved:
            case.resolved = True

        if duration:
            case.time_expires = datetime.now() + duration

        case.time_updated = datetime.now()

        await self.session.commit()
        return case

    async def close_case(self, case_id: str) -> ModCase:
        case = await self.get_case_by_id(case_id)

        if not case:
            raise CaseNotFoundException("Case not found")

        case.resolved = True
        case.time_updated = datetime.now()

        await self.session.commit()
        return case

    async def delete_case(self, case_id: str) -> None:
        case = await self.get_case_by_id(case_id)

        await self.session.delete(case)
        await self.session.commit()

    async def _schedule_mute_refreshes(self, case: ModCase, duration: timedelta) -> None:
        """Schedule refresh tasks for mutes longer than 28 days"""
        if duration.total_seconds() <= 28 * 24 * 60 * 60:
            return

        # 28 day mute, refresh every 27 for safety
        total_seconds = duration.total_seconds()
        period_duration = 28 * 24 * 60 * 60  # 28 days
        refresh_interval = 27 * 24 * 60 * 60  # 27 days

        current_time = datetime.now()

        # First refresh after 27 days
        refresh_time = current_time + timedelta(seconds=refresh_interval)
        remaining_seconds = total_seconds - period_duration

        while remaining_seconds > 0:
            # Calculate duration for this period
            if remaining_seconds >= period_duration:
                refresh_duration = period_duration
            else:
                refresh_duration = remaining_seconds

            self.session.add(
                ScheduledTask(
                    guild_id=self.guild.id,
                    user_id=case.user_id,
                    case_id=case.id,
                    type="refresh_mute",
                    time_scheduled=refresh_time,
                    duration=int(refresh_duration),
                )
            )

            # Schedule next refresh 27 days after
            refresh_time += timedelta(seconds=refresh_interval)
            remaining_seconds -= period_duration

        await self.session.commit()
