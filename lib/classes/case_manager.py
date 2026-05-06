import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated, Literal, Optional, Sequence

import discord
from discord import Guild
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lib.classes.guild_logger import GuildLogger
from lib.duration import DurationConverter, duration_to_timestring
from lib.embeds.dm_notifs import banned_dm, kicked_dm, muted_dm, unbanned_dm, unmuted_dm, warned_dm
from lib.enums.moderation import CaseSource, CaseType
from lib.enums.scheduled_events import EventType
from lib.helpers.cache import get_or_fetch_member
from lib.helpers.log_error import log_error
from lib.helpers.send_dm import send_dm
from lib.sql.sql import ModCase, ScheduledTask

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

    async def get_cases(self, load_comments: bool = True) -> Sequence[ModCase]:
        stmt = select(ModCase).where(ModCase.guild_id == self.guild.id)

        if load_comments:
            stmt = stmt.options(selectinload(ModCase.comments))

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
        time_created: Optional[datetime] = None,
        duration: Annotated[timedelta, DurationConverter] | None = None,
        until: datetime | None = None,
        source: CaseSource = CaseSource.MODERATION,
        external: bool = False,
    ) -> tuple[ModCase, bool, str]:
        if time_created:
            time_created = time_created.astimezone(timezone.utc)
        else:
            time_created = datetime.now(timezone.utc)

        if external:
            guild_settings = await self.bot.fetch_guild_config(self.guild.id)

            # Check if external cases are enabled
            if guild_settings and not guild_settings.moderation_settings.external_cases:
                raise ExternalCasesDisabledException

        case = ModCase(
            guild_id=self.guild.id,
            type=action,
            time_created=time_created,
            user_id=user.id,
            creator_user_id=creator_user.id,
            description=reason,
            external=external,
            resolved=action == CaseType.KICK,
        )

        if until:
            case.time_expires = until.astimezone(timezone.utc)
        elif duration:
            case.time_expires = time_created + duration

        # close old cases
        if action == CaseType.MUTE:
            # set all previous mutes to resolved
            cases = await self.get_cases_by_user(user.id)
            mute_cases = [c for c in cases if c.type == CaseType.MUTE and not c.resolved]

            for mute_case in mute_cases:
                mute_case.resolved = True
                mute_case.time_updated = datetime.now(timezone.utc)
        elif action == CaseType.BAN:
            # set all previous bans to resolved
            cases = await self.get_cases_by_user(user.id)
            ban_cases = [c for c in cases if c.type == CaseType.BAN and not c.resolved]

            for ban_case in ban_cases:
                ban_case.resolved = True
                ban_case.time_updated = datetime.now(timezone.utc)

        self.session.add(case)
        await self.session.flush()

        if action == CaseType.MUTE:
            # Delete old mute tasks
            await self.delete_scheduled_tasks_for_user(user.id, EventType.PERMA_MUTE_REFRESH)
            await self.delete_scheduled_tasks_for_user(user.id, EventType.MUTE_REFRESH)
            await self.delete_scheduled_tasks_for_user(user.id, EventType.CLOSE_MUTE)

            if case.time_expires:
                # create close mute task
                self.session.add(
                    ScheduledTask(
                        guild_id=self.guild.id,
                        user_id=user.id,
                        case_id=case.id,
                        type=EventType.CLOSE_MUTE,
                        time_scheduled=case.time_expires,
                    )
                )
        elif action == CaseType.BAN:
            # Delete old scheduled unban tasks
            await self.delete_scheduled_tasks_for_user(user.id, EventType.UNBAN)

        dm_success = True
        dm_error = ""

        if external:
            return case, dm_success, dm_error

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
                    time_scheduled=time_created + timedelta(days=27),
                )
            )
        elif duration and action == CaseType.BAN:
            # Schedule unban
            self.session.add(
                ScheduledTask(
                    guild_id=self.guild.id,
                    user_id=user.id,
                    case_id=case.id,
                    type=EventType.UNBAN,
                    time_scheduled=time_created + duration,
                )
            )

        if not isinstance(user, discord.Member):
            try:
                result = await get_or_fetch_member(self.bot, self.guild, user.id)
                if not result:
                    raise Exception("Impossible: member not found")

                user = result
            except Exception as e:
                self.logger.error(f"Failed to fetch user {user.id} for DM notification", exc_info=e)
                return case, False, "Failed to fetch member for DM notification"

        if action == CaseType.BAN:
            # FIXME: DM can't be sent if user isn't in server
            embed = banned_dm(
                bot=self.bot,
                ctx=user,
                duration=duration_to_timestring(case.time_created, case.time_expires)
                if case.time_expires
                else "Permanent",
                reason=case.description,
            )
        elif action == CaseType.KICK:
            # FIXME: DM can't be sent if user isn't in server
            embed = kicked_dm(bot=self.bot, ctx=user, reason=case.description)
        elif action == CaseType.MUTE:
            embed = muted_dm(
                bot=self.bot,
                ctx=user,
                duration=duration_to_timestring(case.time_created, case.time_expires)
                if case.time_expires
                else "Permanent",
                reason=case.description,
            )
        elif action == CaseType.WARN:
            embed = warned_dm(self.bot, user, case)
        else:
            embed = None

        if embed:
            dm_success, dm_error = await send_dm(
                bot=self.bot,
                embed=embed,
                user=user,
                source_guild=self.guild,
                module="Moderation"
                if source == CaseSource.MODERATION
                else "Automod"
                if source == CaseSource.AUTOMOD
                else "Bouncer"
                if source == CaseSource.BOUNCER
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
            case.time_expires = datetime.now(timezone.utc) + duration

        case.time_updated = datetime.now(timezone.utc)

        return case

    async def close_case(self, case_id: str) -> tuple[ModCase, bool, str]:
        case = await self.get_case_by_id(case_id)

        if not case:
            raise CaseNotFoundException("Case not found")

        case.resolved = True
        case.time_updated = datetime.now(timezone.utc)

        if case.type == CaseType.MUTE:
            await self.delete_scheduled_tasks_for_user(case.user_id, EventType.PERMA_MUTE_REFRESH)
            await self.delete_scheduled_tasks_for_user(case.user_id, EventType.MUTE_REFRESH)
            await self.delete_scheduled_tasks_for_user(case.user_id, EventType.CLOSE_MUTE)
        elif case.type == CaseType.BAN:
            await self.delete_scheduled_tasks_for_user(case.user_id, EventType.UNBAN)

        if case.external:
            return case, True, ""

        if case.type == CaseType.MUTE:
            try:
                result = await get_or_fetch_member(self.bot, self.guild, case.user_id)
                if not result:
                    raise Exception("Impossible: member not found")

                member = result
            except Exception as e:
                self.logger.error(
                    f"Failed to fetch user {case.user_id} for DM notification", exc_info=e
                )
                return case, False, "Failed to fetch member for DM notification"

            embed = unmuted_dm(self.bot, member)
            dm_success, dm_error = await send_dm(
                bot=self.bot,
                embed=embed,
                user=member,
                source_guild=self.guild,
                module="Moderation",
            )

            if self.bot.user:
                guild_logger = GuildLogger(self.bot, self.guild)
                await guild_logger.titanium_unmute(
                    creator=self.bot.user,
                    target=member,
                    case=case,
                    dm_success=dm_success,
                    dm_error=dm_error,
                )
        elif case.type == CaseType.BAN:
            try:
                result = await get_or_fetch_member(self.bot, self.guild, case.user_id)
                if not result:
                    raise Exception("Impossible: member not found")

                member = result
            except Exception as e:
                self.logger.error(
                    f"Failed to fetch user {case.user_id} for DM notification", exc_info=e
                )
                return case, False, "Failed to fetch member for DM notification"

            # FIXME: DM can't be sent if user isn't in server
            embed = unbanned_dm(self.bot, member)
            dm_success, dm_error = await send_dm(
                bot=self.bot,
                embed=embed,
                user=member,
                source_guild=self.guild,
                module="Moderation",
            )

            if self.bot.user:
                guild_logger = GuildLogger(self.bot, self.guild)
                await guild_logger.titanium_unban(
                    creator=self.bot.user,
                    target=member,
                    case=case,
                    dm_success=dm_success,
                    dm_error=dm_error,
                )

        return case, dm_success, dm_error

    async def delete_case(self, case_id: str) -> None:
        case = await self.get_case_by_id(case_id)

        if not case:
            raise CaseNotFoundException("Case not found")

        if not case.resolved:
            await self.close_case(case_id)

        await self.session.delete(case)

        guild_logger = GuildLogger(self.bot, self.guild)
        await guild_logger.titanium_case_delete(case)

    async def clean_user_cases(self, user_id: int) -> dict[Literal["completed", "errors"], int]:
        await asyncio.sleep(10)
        cases = await self.get_cases_by_user(user_id)
        result: dict[Literal["completed", "errors"], int] = {"completed": 0, "errors": 0}

        if not cases:
            return result

        for case in cases:
            if not case.resolved:
                continue

            try:
                await self.delete_case(case.id)
                result["completed"] += 1
            except Exception as e:
                await log_error(
                    bot=self.bot,
                    module="Moderation",
                    guild_id=self.guild.id,
                    error=f"Failed to delete case {case.id} ({case.user_id})",
                    exc=e,
                )
                result["errors"] += 1

        return result

    async def delete_all_resolved_cases(self) -> dict[Literal["completed", "errors"], int]:
        cases = await self.get_cases()
        result: dict[Literal["completed", "errors"], int] = {"completed": 0, "errors": 0}

        if not cases:
            return result

        for case in cases:
            if not case.resolved:
                continue

            try:
                await self.delete_case(case.id)
                result["completed"] += 1
            except Exception as e:
                await log_error(
                    bot=self.bot,
                    module="Moderation",
                    guild_id=self.guild.id,
                    error=f"Failed to delete case {case.id} ({case.user_id})",
                    exc=e,
                )
                result["errors"] += 1

        return result

    async def delete_scheduled_tasks_for_user(self, user_id: int, type: EventType) -> None:
        """Delete scheduled tasks for a user of a specific type"""
        await self.session.execute(
            delete(ScheduledTask).where(
                ScheduledTask.guild_id == self.guild.id,
                ScheduledTask.user_id == user_id,
                ScheduledTask.type == type,
            )
        )

    async def _schedule_mute_refreshes(self, case: ModCase, duration: timedelta) -> None:
        """Schedule refresh tasks for mutes longer than 28 days"""
        if duration.total_seconds() <= 28 * 24 * 60 * 60:
            return

        # 28 day mute, refresh every 27 for safety
        total_seconds = duration.total_seconds()
        period_duration = 28 * 24 * 60 * 60  # 28 days
        refresh_interval = 27 * 24 * 60 * 60  # 27 days

        # First refresh after 27 days
        refresh_time = case.time_created + timedelta(seconds=refresh_interval)
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
