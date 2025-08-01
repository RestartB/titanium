from discord import Guild
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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

    async def delete_case(self, case_id: int):
        case = await self.get_case_by_id(case_id)

        if case:
            await self.session.delete(case)
            await self.session.commit()

            return True

        return False
