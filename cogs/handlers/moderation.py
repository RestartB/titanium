from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from lib.cases.case_manager import GuildModCaseManager
from lib.sql import get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class ModMonitorCog(commands.Cog):
    """Monitors external moderation actions and creates Titanium cases for them"""
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    # Listen for mutes
    @commands.Cog.listener()
    async def on_mmeber_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        if not self.bot.user:
            return

        if before.id == self.bot.user.id:
            return

        if not before.is_timed_out() and after.is_timed_out():
            # Grab logs
            logs = after.guild.audit_logs(
                limit=1, action=discord.AuditLogAction.member_update
            )
            async for entry in logs:
                if (
                    not entry.target
                    or not self.bot.user
                    or not entry.user_id
                    or not entry.user
                ):
                    return

                if entry.target.id != after.id:
                    return

                if entry.user_id == self.bot.user.id:
                    return

                async with get_session() as session:
                    case_manager = GuildModCaseManager(after.guild, session)

                    # Create a case
                    case = await case_manager.create_case(
                        type="mute",
                        user_id=after.id,
                        creator_user_id=entry.user_id,
                        reason=entry.reason,
                        duration=after.timed_out_until - before.timed_out_until
                        if after.timed_out_until and before.timed_out_until
                        else None,
                        external=True,
                    )

    # Listen for kicks
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if not self.bot.user:
            return

        if self.bot.user and member.id == self.bot.user.id:
            return

        # Grab logs
        logs = member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick)
        async for entry in logs:
            if (
                not entry.target
                or not self.bot.user
                or not entry.user_id
                or not entry.user
            ):
                return

            if entry.target.id != member.id:
                return

            if entry.user_id == self.bot.user.id:
                return

            async with get_session() as session:
                case_manager = GuildModCaseManager(member.guild, session)

                # Create a case
                case = await case_manager.create_case(
                    type="kick",
                    user_id=member.id,
                    creator_user_id=entry.user_id,
                    reason=entry.reason,
                    external=True,
                )

    # Listen for bans
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        if not self.bot.user:
            return

        if self.bot.user and user.id == self.bot.user.id:
            return

        # Grab logs
        logs = guild.audit_logs(limit=1, action=discord.AuditLogAction.ban)
        async for entry in logs:
            if (
                not entry.target
                or not self.bot.user
                or not entry.user_id
                or not entry.user
            ):
                return

            if entry.target.id != user.id:
                return

            if entry.user_id == self.bot.user.id:
                return

            async with get_session() as session:
                case_manager = GuildModCaseManager(guild, session)

                # Create a case
                case = await case_manager.create_case(
                    type="ban",
                    user_id=user.id,
                    creator_user_id=entry.user_id,
                    reason=entry.reason,
                    external=True,
                )

    # Listen for unbans
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        if not self.bot.user:
            return

        if self.bot.user and user.id == self.bot.user.id:
            return

        # Grab logs
        logs = guild.audit_logs(limit=1, action=discord.AuditLogAction.unban)
        async for entry in logs:
            if (
                not entry.target
                or not self.bot.user
                or not entry.user_id
                or not entry.user
            ):
                return

            if entry.target.id != user.id:
                return

            if entry.user_id == self.bot.user.id:
                return

            async with get_session() as session:
                case_manager = GuildModCaseManager(guild, session)

                # Get the latest not resolved ban case for this user
                cases = await case_manager.get_cases_by_user(user.id)
                ban_case = next(
                    (c for c in cases if c.type == "ban" and not c.resolved),
                    None,
                )

                if not ban_case:
                    return

                # Close case
                await case_manager.close_case(ban_case.id)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(ModMonitorCog(bot))
