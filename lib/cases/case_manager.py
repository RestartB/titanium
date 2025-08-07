from datetime import datetime, timedelta
from typing import Annotated, Sequence

from discord import Guild
from sqlalchemy import Column, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..duration import DurationConverter
from ..sql import ModCases


class CaseNotFound(Exception):
    """Exception raised when a case is not found."""


class GuildModCaseManager:
    def __init__(self, guild: Guild, session: AsyncSession):
        self.guild = guild
        self.session = session

    async def get_cases(self) -> Sequence[ModCases]:
        stmt = (
            select(ModCases)
            .where(ModCases.guild_id == self.guild.id)
            .options(selectinload(ModCases.comments))
        )

        result = await self.session.execute(stmt)
        cases = result.scalars().all()

        return cases

    async def get_case_by_id(self, case_id: int | Column[int]) -> ModCases:
        stmt = (
            select(ModCases)
            .where(ModCases.id == case_id, ModCases.guild_id == self.guild.id)
            .options(selectinload(ModCases.comments))
        )

        result = await self.session.execute(stmt)
        case = result.scalar_one_or_none()

        if not case:
            raise CaseNotFound("Case not found")

        return case

    async def get_cases_by_user(self, user_id: int) -> Sequence[ModCases]:
        stmt = (
            select(ModCases)
            .where(ModCases.user_id == user_id, ModCases.guild_id == self.guild.id)
            .options(selectinload(ModCases.comments))
            .order_by(ModCases.time_created.desc())
        )

        result = await self.session.execute(stmt)
        cases = result.scalars().all()

        return cases

    async def create_case(
        self,
        type: str,
        user_id: int,
        creator_user_id: int,
        reason: str,
        duration: Annotated[timedelta, DurationConverter] = timedelta(0),
    ) -> ModCases:
        case = ModCases(
            guild_id=self.guild.id,
            type=type,
            user_id=user_id,
            creator_user_id=creator_user_id,
            proof_msg_id=None,
            proof_channel_id=None,
            proof_text=None,
            time_created=datetime.now(),
            time_updated=datetime.now(),
            time_expires=datetime.now() + duration
            if duration != timedelta(0)
            else None,
            description=reason,
        )

        self.session.add(case)
        await self.session.commit()

        return case

    async def update_case(
        self,
        case_id: int,
        reason: str,
        duration: Annotated[timedelta, DurationConverter] = timedelta(0),
    ) -> ModCases:
        case = await self.get_case_by_id(case_id)

        if not case:
            raise CaseNotFound("Case not found")

        case.description = reason  # pyright: ignore[reportAttributeAccessIssue]

        if duration != timedelta(0):
            case.time_expires = datetime.now() + duration  # pyright: ignore[reportAttributeAccessIssue]

        case.time_updated = datetime.now()  # pyright: ignore[reportAttributeAccessIssue]

        await self.session.commit()
        return case

    async def close_case(self, case_id: int | Column[int]) -> ModCases:
        case = await self.get_case_by_id(case_id)

        if not case:
            raise CaseNotFound("Case not found")

        case.resolved = True  # pyright: ignore[reportAttributeAccessIssue]
        case.time_updated = datetime.now()  # pyright: ignore[reportAttributeAccessIssue]

        await self.session.commit()
        return case

    async def delete_case(self, case_id: int) -> None:
        case = await self.get_case_by_id(case_id)

        await self.session.delete(case)
        await self.session.commit()
