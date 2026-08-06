import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from lib.classes.case_manager import GuildModCaseManager
from lib.classes.guild_logger import GuildLogger
from lib.enums.bouncer import BouncerActionType, BouncerCriteriaType, BouncerEventType
from lib.enums.moderation import CaseSource, CaseType
from lib.helpers.log_error import log_error
from lib.sql.sql import BouncerAction, BouncerRule, ModCase, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


# TODO: possible idea
# get the events from discord manually, but add a lock for the user id
# then if the lock is active or something like that, ignore the manual event


class BouncerMonitorCog(commands.Cog):
    """Monitors joiners and member updates for bouncer triggers and creates cases/punishments"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("bouncer")

    async def handle_event(self, member: discord.Member, event_type: BouncerEventType):
        self.logger.debug(f"Processing member join/update: {member.id}")
        config = await self.bot.fetch_guild_config(member.guild.id) if member.guild else None

        # Check for server ID in config list
        if (
            not member.guild
            or not config
            or not config.moderation_settings
            or not config.bouncer_settings
            or not member
            or not isinstance(member, discord.Member)
            or member.guild_permissions.administrator
            or not self.bot.user
            or member.id == self.bot.user.id
        ):
            self.logger.debug("Bouncer initial checks failed, skipping member")
            return

        triggers: list[BouncerRule] = []
        punishments: list[BouncerAction] = []

        self.logger.debug(f"Bouncer enabled: {config.bouncer_enabled}")

        if not config.bouncer_enabled or not config.moderation_enabled:
            self.logger.debug("Bouncer is disabled, skipping member")
            return

        bouncer_config = config.bouncer_settings

        for rule in bouncer_config.rules:
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
                if criteria.type == BouncerCriteriaType.USERNAME:
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
                elif criteria.type == BouncerCriteriaType.TAG and member.primary_guild:
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
                    criteria.type == BouncerCriteriaType.AGE
                    and event_type == BouncerEventType.JOIN
                    and member.joined_at
                ):
                    if not criteria.account_age:
                        continue

                    if (
                        member.joined_at - member.created_at
                    ).total_seconds() <= criteria.account_age:
                        self.logger.debug("Account age match found")
                        spotted = True
                        break
                elif criteria.type == BouncerCriteriaType.AVATAR and not member.avatar:
                    self.logger.debug("No avatar match found")
                    spotted = True
                    break

            if spotted:
                triggers.append(rule)
                for action in rule.actions:
                    action: BouncerAction
                    punishments.append(action)

        # Get list of punishment types
        punishment_types = {action.type for action in punishments}

        async with get_session() as session:
            manager = GuildModCaseManager(self.bot, member.guild, session)

            for punishment in punishments:
                if punishment.type == BouncerActionType.RESET_NICK:
                    if not member.nick:
                        continue

                    if (
                        not member.guild.me.guild_permissions.manage_nicknames
                        or member.top_role >= member.guild.me.top_role
                    ):
                        continue

                    try:
                        await member.edit(nick=None, reason=f"Bouncer: {punishment.reason}")
                    except discord.Forbidden as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to reset the nickname of {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while resetting nickname of {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )
                elif punishment.type == BouncerActionType.ADD_ROLE:
                    if not punishment.role_id:
                        continue

                    role = member.guild.get_role(punishment.role_id)
                    if not role or role in member.roles:
                        continue

                    if (
                        not member.guild.me.guild_permissions.manage_roles
                        or role >= member.guild.me.top_role
                    ):
                        continue

                    try:
                        await member.add_roles(role, reason=f"Bouncer: {punishment.reason}")
                    except discord.Forbidden as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to add the {role.name} ({role.id}) role to {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while adding role {role.name} ({role.id}) to {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )
                elif punishment.type == BouncerActionType.REMOVE_ROLE:
                    if not punishment.role_id:
                        continue

                    role = member.guild.get_role(punishment.role_id)
                    if not role or role not in member.roles:
                        continue

                    if (
                        not member.guild.me.guild_permissions.manage_roles
                        or role >= member.guild.me.top_role
                    ):
                        continue

                    try:
                        await member.remove_roles(role, reason=f"Bouncer: {punishment.reason}")
                    except discord.Forbidden as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to remove the {role.name} ({role.id}) role from {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while removing role {role.name} ({role.id}) from {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )
                elif punishment.type == BouncerActionType.TOGGLE_ROLE:
                    if not punishment.role_id:
                        continue

                    role = member.guild.get_role(punishment.role_id)
                    if not role:
                        continue

                    if (
                        not member.guild.me.guild_permissions.manage_roles
                        or role >= member.guild.me.top_role
                    ):
                        continue

                    try:
                        if role in member.roles:
                            await member.remove_roles(role, reason=f"Bouncer: {punishment.reason}")
                        else:
                            await member.add_roles(role, reason=f"Bouncer: {punishment.reason}")
                    except discord.Forbidden as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to toggle the {role.name} ({role.id}) role for {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while toggling role {role.name} ({role.id}) for {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )
                elif punishment.type == BouncerActionType.WARN:
                    await manager.create_case(
                        action=CaseType.WARN,
                        user=member,
                        creator_user=self.bot.user,
                        reason=f"Bouncer: {punishment.reason}",
                        source=CaseSource.BOUNCER,
                    )
                elif punishment.type == BouncerActionType.MUTE:
                    # Check if user is already timed out
                    if member.is_timed_out():
                        continue

                    if (
                        not member.guild.me.guild_permissions.moderate_members
                        or member.top_role >= member.guild.me.top_role
                    ):
                        continue

                    # Time out user
                    try:
                        await member.timeout(
                            (
                                timedelta(seconds=punishment.duration)
                                if punishment.duration
                                and punishment.duration > 0
                                and timedelta(seconds=punishment.duration).total_seconds()
                                <= 2419200
                                else timedelta(seconds=2419200)
                            ),
                            reason=f"Bouncer: {punishment.reason}",
                        )

                        await manager.create_case(
                            action=CaseType.MUTE,
                            user=member,
                            creator_user=self.bot.user,
                            reason=f"Bouncer: {punishment.reason}",
                            duration=(
                                timedelta(seconds=punishment.duration)
                                if punishment.duration and punishment.duration > 0
                                else None
                            ),
                            source=CaseSource.BOUNCER,
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to mute {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while muting {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )
                elif (
                    punishment.type == BouncerActionType.KICK
                    and BouncerActionType.BAN not in punishment_types
                ):
                    if (
                        not member.guild.me.guild_permissions.kick_members
                        or member.top_role >= member.guild.me.top_role
                    ):
                        continue

                    # Kick user
                    case: ModCase
                    try:
                        case, _, _ = await manager.create_case(
                            action=CaseType.KICK,
                            user=member,
                            creator_user=self.bot.user,
                            reason=f"Bouncer: {punishment.reason}",
                            source=CaseSource.BOUNCER,
                        )
                        await member.kick(
                            reason=f"Bouncer: {punishment.reason}",
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to kick {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )

                        if case:
                            await manager.delete_case(case.id)
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while kicking {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )

                        if case:
                            await manager.delete_case(case.id)
                    except Exception:
                        if case:
                            await manager.delete_case(case.id)
                        raise
                elif punishment.type == BouncerActionType.BAN:
                    if (
                        not member.guild.me.guild_permissions.ban_members
                        or member.top_role >= member.guild.me.top_role
                    ):
                        continue

                    # Ban user
                    case: ModCase
                    try:
                        case, _, _ = await manager.create_case(
                            action=CaseType.BAN,
                            user=member,
                            creator_user=self.bot.user,
                            reason=f"Bouncer: {punishment.reason}",
                            duration=(
                                timedelta(seconds=punishment.duration)
                                if punishment.duration and punishment.duration > 0
                                else None
                            ),
                            source=CaseSource.BOUNCER,
                        )
                        await member.ban(
                            reason=f"Bouncer: {punishment.reason}",
                            delete_message_seconds=config.moderation_settings.ban_days * 86400,
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to ban {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )

                        if case:
                            await manager.delete_case(case.id)
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while banning {member.name} ({member.id})",
                            details=e.text,
                            exc=e,
                        )

                        if case:
                            await manager.delete_case(case.id)
                    except Exception:
                        if case:
                            await manager.delete_case(case.id)
                        raise
                else:
                    await log_error(
                        bot=self.bot,
                        module="Bouncer",
                        guild_id=member.guild.id,
                        error=f"An internal error occurred while processing bouncer punishments for @{member.name} ({member.id})",
                        details=f"Punishment action type does not exist: {punishment.type}",
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
            await self.handle_event(member, BouncerEventType.JOIN)
        except Exception as e:
            await log_error(
                bot=self.bot,
                module="Bouncer",
                guild_id=member.guild.id,
                error=f"An unknown error occurred while processing joining member @{member.name} ({member.id})",
                exc=e,
            )

    # Listen for member updates
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if (
            before.name == after.name
            and before.display_name == after.display_name
            and before.global_name == after.global_name
            and before.nick == after.nick
            and before.primary_guild.tag == after.primary_guild.tag
        ):
            return

        try:
            await self.handle_event(after, BouncerEventType.UPDATE)
        except Exception as e:
            await log_error(
                bot=self.bot,
                module="Bouncer",
                guild_id=after.guild.id,
                error=f"An unknown error occurred while processing a user update for @{after.name} ({after.id})",
                exc=e,
            )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(BouncerMonitorCog(bot))
