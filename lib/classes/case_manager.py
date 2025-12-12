import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Optional, Sequence

import discord
from discord import Guild
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lib.classes.guild_logger import GuildLogger
from lib.embeds.dm_notifs import banned_dm, kicked_dm, muted_dm, unbanned_dm, unmuted_dm, warned_dm
from lib.enums.moderation import CaseSource, CaseType
from lib.enums.scheduled_events import EventType
from lib.helpers.send_dm import send_dm

from ..duration import DurationConverter
from ..sql.sql import ModCase, ScheduledTask

if TYPE_CHECKING:
    from main import TitaniumBot


class CaseNotFoundException(Exception):
    """Exception raised when a case is not found."""


class ExternalCasesDisabledException(Exception):
    """Exception raised when external cases are disabled."""


class GuildModCaseManager:
    def __init__(self, bot: TitaniumBot, guild: Guild, session: AsyncSession) -> None:
        self.bot = bot
        self.guild = guild
        self.session = session
        self.logger = logging.getLogger("cases")

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
        action: CaseType,
        user: discord.User | discord.Member,
        creator_user: discord.User | discord.Member | discord.ClientUser,
        reason: Optional[str],
        duration: Annotated[timedelta, DurationConverter] | None = None,
        source: CaseSource = CaseSource.MODERATION,
        external: bool = False,
    ) -> tuple[ModCase, bool, str]:
        if external:
            guild_settings = await self.bot.fetch_guild_config(self.guild.id)

            # Check if external cases are enabled
            if guild_settings and not guild_settings.moderation_settings.external_cases:
                raise ExternalCasesDisabledException

        case = ModCase(
            guild_id=self.guild.id,
            type=action,
            user_id=user.id,
            creator_user_id=creator_user.id,
            time_created=datetime.now(),
            description=reason,
            external=external,
            resolved=True if action == CaseType.KICK else False,
        )

        if duration:
            case.time_expires = datetime.now() + duration

        self.session.add(case)
        await self.session.commit()

        if not external:
            if action == CaseType.MUTE:
                # Delete old scheduled mute refresh tasks
                await self.delete_scheduled_tasks_for_user(user.id, EventType.PERMA_MUTE_REFRESH)

            if duration and action == CaseType.MUTE:
                # Schedule mute refreshes
                await self._schedule_mute_refreshes(case, duration)
            elif duration is None and action == CaseType.MUTE:
                # Permanent mute, schedule refresh every 27 days
                self.session.add(
                    ScheduledTask(
                        guild_id=self.guild.id,
                        user_id=user.id,
                        case_id=case.id,
                        type=EventType.PERMA_MUTE_REFRESH,
                        time_scheduled=datetime.now() + timedelta(days=27),
                    )
                )
                await self.session.commit()
            elif duration and action == CaseType.BAN:
                # Delete old scheduled unban tasks
                await self.delete_scheduled_tasks_for_user(user.id, EventType.UNBAN)

                # Schedule unban
                self.session.add(
                    ScheduledTask(
                        guild_id=self.guild.id,
                        user_id=user.id,
                        case_id=case.id,
                        type=EventType.UNBAN,
                        time_scheduled=datetime.now() + duration,
                    )
                )
                await self.session.commit()

        dm_success = True
        dm_error = ""

        if not external or (
            external and guild_settings and guild_settings.moderation_settings.external_case_dms
        ):
            if not isinstance(user, discord.Member):
                try:
                    member = await self.guild.fetch_member(user.id)
                except Exception as e:
                    self.logger.error(
                        f"Failed to fetch user {user.id} for DM notification", exc_info=e
                    )
                    return case, False, "Failed to fetch member for DM notification"

            if action == CaseType.BAN:
                embed = banned_dm(self.bot, member, case)
            elif action == CaseType.KICK:
                embed = kicked_dm(self.bot, member, case)
            elif action == CaseType.MUTE:
                embed = muted_dm(self.bot, member, case)
            elif action == CaseType.WARN:
                embed = warned_dm(self.bot, member, case)
            else:
                embed = None

            if embed:
                dm_success, dm_error = await send_dm(
                    embed=embed,
                    user=member,
                    source_guild=self.guild,
                    module="Moderation"
                    if source == CaseSource.MODERATION
                    else "Automod"
                    if source == CaseSource.AUTOMOD
                    else "Bouncer"
                    if source == CaseSource.BOUNCER
                    else "External Action"
                    if external
                    else "Unknown",
                )

        guild_logger = GuildLogger(self.bot, self.guild)
        if action == CaseType.WARN:
            await guild_logger.titanium_warn(
                target=user,
                creator=creator_user,
                case=case,
                dm_success=dm_success,
                dm_error=dm_error,
            )
        elif action == CaseType.MUTE:
            await guild_logger.titanium_mute(
                target=user,
                creator=creator_user,
                case=case,
                dm_success=dm_success,
                dm_error=dm_error,
            )
        elif action == CaseType.KICK:
            await guild_logger.titanium_kick(
                target=user,
                creator=creator_user,
                case=case,
                dm_success=dm_success,
                dm_error=dm_error,
            )
        elif action == CaseType.BAN:
            await guild_logger.titanium_ban(
                target=user,
                creator=creator_user,
                case=case,
                dm_success=dm_success,
                dm_error=dm_error,
            )

        return case, dm_success, dm_error

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

    async def close_case(self, case_id: str) -> tuple[ModCase, bool, str]:
        case = await self.get_case_by_id(case_id)

        if not case:
            raise CaseNotFoundException("Case not found")

        case.resolved = True
        case.time_updated = datetime.now()

        if case.type == CaseType.MUTE:
            await self.delete_scheduled_tasks_for_user(case.user_id, EventType.PERMA_MUTE_REFRESH)
            await self.delete_scheduled_tasks_for_user(case.user_id, EventType.MUTE_REFRESH)
        elif case.type == CaseType.BAN:
            await self.delete_scheduled_tasks_for_user(case.user_id, EventType.UNBAN)

        await self.session.commit()

        if case.external:
            guild_settings = await self.bot.fetch_guild_config(self.guild.id)

            # Check if external cases are enabled
            if guild_settings and (
                not guild_settings.moderation_settings.external_cases
                or not guild_settings.moderation_settings.external_case_dms
            ):
                return case, True, ""

        if case.type == CaseType.MUTE:
            try:
                member = await self.guild.fetch_member(case.user_id)
            except Exception as e:
                self.logger.error(
                    f"Failed to fetch user {case.user_id} for DM notification", exc_info=e
                )
                return case, False, "Failed to fetch member for DM notification"

            embed = unmuted_dm(self.bot, member, case)

            dm_success, dm_error = await send_dm(
                embed=embed,
                user=member,
                source_guild=self.guild,
                module="External Action" if case.external else "Moderation",
            )
        elif case.type == CaseType.BAN:
            try:
                member = await self.guild.fetch_member(case.user_id)
            except Exception as e:
                self.logger.error(
                    f"Failed to fetch user {case.user_id} for DM notification", exc_info=e
                )
                return case, False, "Failed to fetch member for DM notification"

            embed = unbanned_dm(self.bot, member, case)

            dm_success, dm_error = await send_dm(
                embed=embed,
                user=member,
                source_guild=self.guild,
                module="External Action" if case.external else "Moderation",
            )

        return case, dm_success, dm_error

    async def delete_case(self, case_id: str) -> None:
        case = await self.get_case_by_id(case_id)

        if not case:
            raise CaseNotFoundException("Case not found")

        await self.close_case(case_id)

        await self.session.delete(case)
        await self.session.commit()

    async def delete_scheduled_tasks_for_user(self, user_id: int, type: EventType) -> None:
        """Delete scheduled tasks for a user of a specific type"""
        await self.session.execute(
            delete(ScheduledTask).where(
                ScheduledTask.guild_id == self.guild.id,
                ScheduledTask.user_id == user_id,
                ScheduledTask.type == type,
            )
        )
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
                    type=EventType.MUTE_REFRESH,
                    time_scheduled=refresh_time,
                    duration=int(refresh_duration),
                )
            )

            # Schedule next refresh 27 days after
            refresh_time += timedelta(seconds=refresh_interval)
            remaining_seconds -= period_duration

        await self.session.commit()
