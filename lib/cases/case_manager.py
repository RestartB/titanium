from datetime import datetime, timedelta, timezone
from typing import Annotated

from discord import Guild
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..duration import DurationConverter
from ..sql import ModCases


class GuildModCaseManager:
    def __init__(self, guild: Guild, session: AsyncSession):
        self.guild = guild
        self.session = session

    async def get_cases(self):
        stmt = (
            select(ModCases)
            .where(ModCases.guild_id == self.guild.id)
            .options(selectinload(ModCases.comments))
        )

        result = await self.session.execute(stmt)
        cases = result.scalars().all()

        return cases

    async def get_case_by_id(self, case_id: int):
        stmt = (
            select(ModCases)
            .where(ModCases.id == case_id, ModCases.guild_id == self.guild.id)
            .options(selectinload(ModCases.comments))
        )

        result = await self.session.execute(stmt)
        case = result.scalar_one_or_none()

        return case

    async def create_case(
        self,
        type,
        user_id: int,
        reason: str,
        duration: Annotated[timedelta, DurationConverter] = timedelta(0),
    ):
        case = ModCases(
            guild_id=self.guild.id,
            user_id=user_id,
            proof_msg_id=None,
            proof_channel_id=None,
            proof_text=None,
            time_created=datetime.now(),
            time_expires=datetime.now() + duration
            if duration != timedelta(0)
            else None,
            description=reason,
        )

        self.session.add(case)
        await self.session.commit()

        return case

    async def delete_case(self, case_id: int):
        case = await self.get_case_by_id(case_id)

        if case:
            await self.session.delete(case)
            await self.session.commit()

            return True

        return False
