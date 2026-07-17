import logging
from datetime import datetime
from typing import TYPE_CHECKING

import discord
import lib.classes.case_manager as case_managers
from discord.ext import commands
from lib.enums.moderation import CaseType
from lib.sql.sql import get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ModMonitorCog(commands.Cog):
    """Monitors external moderation actions and creates Titanium cases for them"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("ext_cases")

    # Listen to server audit log for moderation events
    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry) -> None:
        if not self.bot.user:
            self.logger.debug("Bot is not ready, returning")
            return

        if entry.user_id == self.bot.user.id:
            self.logger.debug("Creator is bot, ignoring")
            return

        if entry.action == discord.AuditLogAction.member_update:
            self.logger.debug("Member update event received")
            if (
                not entry.target
                or not isinstance(entry.target, discord.Member)
                or not self.bot.user
                or not entry.user_id
                or not entry.user
            ):
                self.logger.debug("Required information missing")
                return

            # Check if the timeout status was specifically changed in this event
            if not hasattr(entry.after, "timed_out_until"):
                self.logger.debug("Not a timeout update")
                return

            timeout_after: datetime | None = entry.after.timed_out_until

            if timeout_after is not None:
                self.logger.debug("User timed out")

                # Handle new mutes / updated mutes
                async with get_session() as session:
                    case_manager = case_managers.GuildModCaseManager(
                        self.bot, entry.guild, session
                    )

                    # Create a case
                    await case_manager.create_case(
                        action=CaseType.MUTE,
                        user=entry.target,
                        creator_user=entry.user,
                        reason=entry.reason,
                        time_created=entry.created_at,
                        until=timeout_after,
                        external=True,
                    )

                self.logger.debug("Created mute case")
            else:
                self.logger.debug("User timeout removed")

                # Handle unmutes
                async with get_session() as session:
                    case_manager = case_managers.GuildModCaseManager(
                        self.bot, entry.guild, session
                    )

                    # Close all open mute cases for this user
                    cases = await case_manager.get_cases_by_user(entry.target.id)
                    mute_cases = [
                        c for c in cases if c.type == CaseType.MUTE and not c.resolved
                    ]

                    # Close cases
                    for mute_case in mute_cases:
                        self.logger.debug(f"Closing case - {mute_case.id}")
                        await case_manager.close_case(mute_case.id)

                self.logger.debug(f"Closed {len(mute_cases)} mute cases")
        elif entry.action == discord.AuditLogAction.kick:
            if (
                not entry.target
                or not isinstance(entry.target, (discord.User, discord.Member))
                or not self.bot.user
                or not entry.user_id
                or not entry.user
            ):
                self.logger.debug("Required information missing")
                return

            async with get_session() as session:
                case_manager = case_managers.GuildModCaseManager(self.bot, entry.guild, session)

                # Create a case
                await case_manager.create_case(
                    action=CaseType.KICK,
                    user=entry.target,
                    creator_user=entry.user,
                    reason=entry.reason,
                    external=True,
                )

            self.logger.debug("Created kick case")
        elif entry.action == discord.AuditLogAction.ban:
            if (
                not entry.target
                or not isinstance(entry.target, (discord.User, discord.Member))
                or not self.bot.user
                or not entry.user_id
                or not entry.user
            ):
                self.logger.debug("Required information missing")
                return

            async with get_session() as session:
                case_manager = case_managers.GuildModCaseManager(self.bot, entry.guild, session)

                # Create a case
                await case_manager.create_case(
                    action=CaseType.BAN,
                    user=entry.target,
                    creator_user=entry.user,
                    reason=entry.reason,
                    external=True,
                )

            self.logger.debug("Created ban case")
        elif entry.action == discord.AuditLogAction.unban:
            if (
                not entry.target
                or not isinstance(entry.target.id, int)
                or not self.bot.user
                or not entry.user_id
                or not entry.user
            ):
                self.logger.debug("Required information missing")
                return

            async with get_session() as session:
                case_manager = case_managers.GuildModCaseManager(self.bot, entry.guild, session)

                # Close all open ban cases for this user
                cases = await case_manager.get_cases_by_user(entry.target.id)
                ban_cases = [c for c in cases if c.type == CaseType.BAN and not c.resolved]

                # Close cases
                for ban_case in ban_cases:
                    self.logger.debug(f"Closing case - {ban_case.id}")
                    await case_manager.close_case(ban_case.id)

            self.logger.debug(f"Closed {len(ban_cases)} ban cases")


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ModMonitorCog(bot))
