import asyncio
import logging
import re
from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from lib.classes.case_manager import GuildModCaseManager
from lib.classes.guild_logger import GuildLogger
from lib.embeds.dm_notifs import banned_dm, kicked_dm, muted_dm, warned_dm
from lib.enums.bouncer import BouncerActionType, BouncerCriteriaType
from lib.enums.moderation import CaseType
from lib.helpers.log_error import log_error
from lib.helpers.send_dm import send_dm
from lib.sql.sql import BouncerAction, BouncerRule, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class BouncerEventType(Enum):
    JOIN = 0
    UPDATE = 1


class BouncerMonitorCog(commands.Cog):
    """Monitors joiners and member updates for bouncer triggers and creates cases/punishments"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("bouncer")
        self.event_queue: asyncio.Queue[tuple[discord.Member, BouncerEventType]] = asyncio.Queue()
        self.event_queue_task = self.bot.loop.create_task(self.queue_worker())

    def cog_unload(self) -> None:
        self.event_queue.shutdown(immediate=True)

    async def queue_worker(self):
        self.logger.info("Bouncer handler started.")
        while True:
            try:
                await self.bot.wait_until_ready()
                event = await self.event_queue.get()
            except asyncio.QueueShutDown:
                return

            try:
                await self.event_handler(event[0], event[1])
            except Exception as e:
                await log_error(
                    module="Bouncer",
                    guild_id=event[0].guild.id if event[0].guild else None,
                    error=f"An unknown error occurred while processing bouncer for member @{event[0].name} ({event[0].id})",
                    exc=e,
                )
            finally:
                self.event_queue.task_done()

    async def event_handler(self, member: discord.Member, event_type: BouncerEventType):
        self.logger.debug(f"Processing member join/update: {member.id}")
        config = await self.bot.fetch_guild_config(member.guild.id) if member.guild else None

        # Check for server ID in config list
        if (
            not member.guild
            or member.guild.id not in self.bot.guild_configs
            or not config
            or not config.bouncer_settings
            or not member
            or not isinstance(member, discord.Member)
            or member.guild_permissions.administrator
            or not self.bot.user
        ):
            self.logger.debug("Bouncer initial checks failed, skipping member")
            return

        triggers: list[BouncerRule] = []
        punishments: list[BouncerAction] = []

        self.logger.debug(f"Bouncer enabled: {config.bouncer_enabled}")

        if not config.bouncer_enabled:
            self.logger.debug("Bouncer is not enabled, skipping member")
            return

        config = config.bouncer_settings

        for rule in config.rules:
            spotted = False

            if not rule.enabled:
                self.logger.debug(f"Bouncer rule {rule.id} is disabled, skipping")
                continue

            if event_type == BouncerEventType.UPDATE and not rule.evaluate_for_existing_members:
                self.logger.debug(
                    f"Bouncer rule {rule.id} is not set to evaluate existing members, skipping"
                )
                continue

            for criteria in rule.criteria:
                if criteria.criteria_type == BouncerCriteriaType.USERNAME:
                    for word in criteria.words:
                        check_word = word.lower() if not criteria.case_sensitive else word
                        matches = []
                        contents_to_check: list[str] = [member.name, member.display_name]

                        if member.global_name:
                            contents_to_check.append(member.global_name)

                        if member.nick:
                            contents_to_check.append(member.nick)

                        for content_to_check in contents_to_check:
                            if not criteria.case_sensitive:
                                content_to_check = content_to_check.lower()

                            if criteria.match_whole_word:
                                pattern = r"\b" + re.escape(check_word) + r"\b"
                                matches = re.findall(pattern, content_to_check)
                            else:
                                pattern = re.escape(check_word)
                                matches = re.findall(pattern, content_to_check)

                        if matches:
                            self.logger.debug("Username match found")
                            spotted = True
                            break
                elif criteria.criteria_type == BouncerCriteriaType.TAG and member.primary_guild:
                    if not member.primary_guild.tag:
                        continue

                    for word in criteria.words:
                        check_word = word.lower() if not criteria.case_sensitive else word

                        if criteria.match_whole_word:
                            pattern = r"\b" + re.escape(check_word) + r"\b"
                            matches = re.findall(pattern, member.primary_guild.tag)
                        else:
                            pattern = re.escape(check_word)
                            matches = re.findall(pattern, member.primary_guild.tag)

                        if matches:
                            self.logger.debug("Tag match found")
                            spotted = True
                            break
                elif (
                    criteria.criteria_type == BouncerCriteriaType.AGE
                    and event_type == BouncerEventType.JOIN
                ):
                    if (discord.utils.utcnow() - member.created_at).seconds <= criteria.account_age:
                        self.logger.debug("Account age match found")
                        spotted = True
                        break
                elif criteria.criteria_type == BouncerCriteriaType.AVATAR:
                    if not member.avatar:
                        self.logger.debug("No avatar match found")
                        spotted = True
                        break

            if spotted:
                triggers.append(rule)
                for action in rule.actions:
                    action: BouncerAction
                    punishments.append(action)

        # Get list of punishment types
        punishment_types = list(set(action.action_type for action in punishments))

        async with get_session() as session:
            manager = GuildModCaseManager(self.bot, member.guild, session)

            for punishment in punishments:
                if punishment.action_type == BouncerActionType.RESET_NICK:
                    if not member.nick:
                        continue

                    try:
                        await member.edit(nick=None, reason=f"Bouncer: {punishment.reason}")
                    except discord.Forbidden as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to reset the nickname of {member.name} ({member.id})",
                            details=e.text,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while resetting nickname of {member.name} ({member.id})",
                            details=e.text,
                        )
                elif punishment.action_type == BouncerActionType.ADD_ROLE:
                    role = member.guild.get_role(punishment.role_id)

                    if role and role not in member.roles:
                        try:
                            await member.add_roles(role, reason=f"Bouncer: {punishment.reason}")
                        except discord.Forbidden as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Titanium was not allowed to add the {role.name} ({role.id}) role to {member.name} ({member.id})",
                                details=e.text,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Unknown Discord error while adding role {role.name} ({role.id}) to {member.name} ({member.id})",
                                details=e.text,
                            )
                elif punishment.action_type == BouncerActionType.REMOVE_ROLE:
                    role = member.guild.get_role(punishment.role_id)

                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason=f"Bouncer: {punishment.reason}")
                        except discord.Forbidden as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Titanium was not allowed to remove the {role.name} ({role.id}) role from {member.name} ({member.id})",
                                details=e.text,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Unknown Discord error while removing role {role.name} ({role.id}) from {member.name} ({member.id})",
                                details=e.text,
                            )
                elif punishment.action_type == BouncerActionType.TOGGLE_ROLE:
                    role = member.guild.get_role(punishment.role_id)

                    if role:
                        try:
                            if role in member.roles:
                                await member.remove_roles(
                                    role, reason=f"Bouncer: {punishment.reason}"
                                )
                            else:
                                await member.add_roles(role, reason=f"Bouncer: {punishment.reason}")
                        except discord.Forbidden as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Titanium was not allowed to toggle the {role.name} ({role.id}) role for {member.name} ({member.id})",
                                details=e.text,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Unknown Discord error while toggling role {role.name} ({role.id}) for {member.name} ({member.id})",
                                details=e.text,
                            )
                elif punishment.action_type == BouncerActionType.WARN:
                    case = await manager.create_case(
                        action=CaseType.WARN,
                        user_id=member.id,
                        creator_user_id=self.bot.user.id,
                        reason=f"Bouncer: {punishment.reason}",
                    )

                    await send_dm(
                        embed=warned_dm(self.bot, member, case),
                        user=member,
                        source_guild=member.guild,
                        module="Bouncer",
                        action="warning",
                    )
                elif punishment.action_type == BouncerActionType.MUTE:
                    # Check if user is already timed out
                    if member.is_timed_out():
                        continue

                    # Time out user
                    try:
                        await member.timeout(
                            (
                                timedelta(seconds=punishment.duration)
                                if punishment.duration > 0
                                and timedelta(seconds=punishment.duration).total_seconds()
                                <= 2419200
                                else timedelta(seconds=2419200)
                            ),
                            reason=f"Bouncer: {punishment.reason}",
                        )

                        case = await manager.create_case(
                            action=CaseType.MUTE,
                            user_id=member.id,
                            creator_user_id=self.bot.user.id,
                            reason=f"Bouncer: {punishment.reason}",
                            duration=(
                                timedelta(seconds=punishment.duration)
                                if punishment.duration > 0
                                else None
                            ),
                        )

                        await send_dm(
                            embed=muted_dm(self.bot, member, case),
                            user=member,
                            source_guild=member.guild,
                            module="Bouncer",
                            action="muting",
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to mute {member.name} ({member.id})",
                            details=e.text,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while muting {member.name} ({member.id})",
                            details=e.text,
                        )

                elif (
                    punishment.action_type == BouncerActionType.KICK
                    and BouncerActionType.BAN not in punishment_types
                ):
                    # Kick user
                    try:
                        await member.kick(
                            reason=f"Bouncer: {punishment.reason}",
                        )

                        case = await manager.create_case(
                            action=CaseType.KICK,
                            user_id=member.id,
                            creator_user_id=self.bot.user.id,
                            reason=f"Bouncer: {punishment.reason}",
                        )

                        await send_dm(
                            embed=kicked_dm(self.bot, member, case),
                            user=member,
                            source_guild=member.guild,
                            module="Bouncer",
                            action="kicking",
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to kick {member.name} ({member.id})",
                            details=e.text,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while kicking {member.name} ({member.id})",
                            details=e.text,
                        )

                elif punishment.action_type == BouncerActionType.BAN:
                    # Ban user
                    try:
                        await member.ban(
                            reason=f"Bouncer: {punishment.reason}",
                        )

                        case = await manager.create_case(
                            action=CaseType.BAN,
                            user_id=member.id,
                            creator_user_id=self.bot.user.id,
                            reason=f"Bouncer: {punishment.reason}",
                            duration=(
                                timedelta(seconds=punishment.duration)
                                if punishment.duration > 0
                                else None
                            ),
                        )

                        await send_dm(
                            embed=banned_dm(self.bot, member, case),
                            user=member,
                            source_guild=member.guild,
                            module="Bouncer",
                            action="banning",
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to ban {member.name} ({member.id})",
                            details=e.text,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while banning {member.name} ({member.id})",
                            details=e.text,
                        )

        if triggers:
            guild_logger = GuildLogger(self.bot, member.guild)
            await guild_logger.titanium_bouncer_trigger(
                rules=triggers,
                actions=punishments,
                member=member,
            )

        self.logger.debug(f"Processed member event from {member.guild.id}: {member.id}")

    # Listen for member joins
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            await self.event_queue.put((member, BouncerEventType.JOIN))
        except asyncio.QueueShutDown:
            return

    # Listen for member updates
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        try:
            await self.event_queue.put((after, BouncerEventType.UPDATE))
        except asyncio.QueueShutDown:
            return


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(BouncerMonitorCog(bot))
