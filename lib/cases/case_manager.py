from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional, Sequence

from discord import Guild
from sqlalchemy import Column, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..duration import DurationConverter
from ..sql import ModCase


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

    async def get_case_by_id(self, case_id: int | Column[int]) -> ModCase:
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
        type: Literal["ban", "kick", "mute", "warn"],
        user_id: int,
        creator_user_id: int,
        reason: Optional[str],
        duration: Annotated[timedelta, DurationConverter] | None = None,
        external: bool = False,
    ) -> ModCase:
        case = ModCase(
            guild_id=self.guild.id,
            type=type,
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

        return case

    async def update_case(
        self,
        case_id: int,
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

    async def close_case(self, case_id: int | Column[int]) -> ModCase:
        case = await self.get_case_by_id(case_id)

        if not case:
            raise CaseNotFoundException("Case not found")

        case.resolved = True
        case.time_updated = datetime.now()

        await self.session.commit()
        return case

    async def delete_case(self, case_id: int) -> None:
        case = await self.get_case_by_id(case_id)

        await self.session.delete(case)
        await self.session.commit()
