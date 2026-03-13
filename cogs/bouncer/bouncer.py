import importlib
import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

import lib.classes.case_manager as case_managers
from lib.classes.guild_logger import GuildLogger
from lib.enums.bouncer import BouncerActionType, BouncerCriteriaType, BouncerEventType
from lib.enums.moderation import CaseSource, CaseType
from lib.helpers.log_error import log_error
from lib.sql.sql import BouncerAction, BouncerRule, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


# TODO: fully test


class BouncerMonitorCog(commands.Cog):
    """Monitors joiners and member updates for bouncer triggers and creates cases/punishments"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("bouncer")

    async def cog_load(self) -> None:
        importlib.reload(case_managers)

    async def handle_event(self, member: discord.Member, event_type: BouncerEventType):
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
            or member.id == self.bot.user.id
        ):
            self.logger.debug("Bouncer initial checks failed, skipping member")
            return

        triggers: list[BouncerRule] = []
        punishments: list[BouncerAction] = []

        self.logger.debug(f"Bouncer enabled: {config.bouncer_enabled}")

        if not config.bouncer_enabled or not config.moderation_enabled:
            self.logger.debug("Bouncer is not enabled, skipping member")
            return

        bouncer_config = config.bouncer_settings

        for rule in bouncer_config.rules:
            spotted = False

            if not rule.enabled:
                self.logger.debug(f"Bouncer rule {rule.id} is disabled, skipping")
                continue

            if (
                event_type.name == BouncerEventType.UPDATE.name
                and not rule.evaluate_for_existing_members
            ):
                self.logger.debug(
                    f"Bouncer rule {rule.id} is not set to evaluate existing members, skipping"
                )
                continue

            for criteria in rule.criteria:
                if criteria.criteria_type.name == BouncerCriteriaType.USERNAME.name:
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
                elif (
                    criteria.criteria_type.name == BouncerCriteriaType.TAG.name
                    and member.primary_guild
                ):
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
                    criteria.criteria_type.name == BouncerCriteriaType.AGE.name
                    and event_type.name == BouncerEventType.JOIN.name
                ):
                    if (discord.utils.utcnow() - member.created_at).seconds <= criteria.account_age:
                        self.logger.debug("Account age match found")
                        spotted = True
                        break
                elif criteria.criteria_type.name == BouncerCriteriaType.AVATAR.name:
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
        punishment_types = list(set(action.action_type.name for action in punishments))

        async with get_session() as session:
            manager = case_managers.GuildModCaseManager(self.bot, member.guild, session)

            for punishment in punishments:
                if punishment.action_type.name == BouncerActionType.RESET_NICK.name:
                    if not member.nick:
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
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while resetting nickname of {member.name} ({member.id})",
                            details=e.text,
                        )
                elif punishment.action_type.name == BouncerActionType.ADD_ROLE.name:
                    role = member.guild.get_role(punishment.role_id)

                    if role and role not in member.roles:
                        try:
                            await member.add_roles(role, reason=f"Bouncer: {punishment.reason}")
                        except discord.Forbidden as e:
                            await log_error(
                                bot=self.bot,
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Titanium was not allowed to add the {role.name} ({role.id}) role to {member.name} ({member.id})",
                                details=e.text,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                bot=self.bot,
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Unknown Discord error while adding role {role.name} ({role.id}) to {member.name} ({member.id})",
                                details=e.text,
                            )
                elif punishment.action_type.name == BouncerActionType.REMOVE_ROLE.name:
                    role = member.guild.get_role(punishment.role_id)

                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason=f"Bouncer: {punishment.reason}")
                        except discord.Forbidden as e:
                            await log_error(
                                bot=self.bot,
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Titanium was not allowed to remove the {role.name} ({role.id}) role from {member.name} ({member.id})",
                                details=e.text,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                bot=self.bot,
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Unknown Discord error while removing role {role.name} ({role.id}) from {member.name} ({member.id})",
                                details=e.text,
                            )
                elif punishment.action_type.name == BouncerActionType.TOGGLE_ROLE.name:
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
                                bot=self.bot,
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Titanium was not allowed to toggle the {role.name} ({role.id}) role for {member.name} ({member.id})",
                                details=e.text,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                bot=self.bot,
                                module="Bouncer",
                                guild_id=member.guild.id,
                                error=f"Unknown Discord error while toggling role {role.name} ({role.id}) for {member.name} ({member.id})",
                                details=e.text,
                            )
                elif punishment.action_type.name == BouncerActionType.WARN.name:
                    await manager.create_case(
                        action=CaseType.WARN,
                        user=member,
                        creator_user=self.bot.user,
                        reason=f"Bouncer: {punishment.reason}",
                        source=CaseSource.BOUNCER,
                    )
                elif punishment.action_type.name == BouncerActionType.MUTE.name:
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

                        await manager.create_case(
                            action=CaseType.MUTE,
                            user=member,
                            creator_user=self.bot.user,
                            reason=f"Bouncer: {punishment.reason}",
                            duration=(
                                timedelta(seconds=punishment.duration)
                                if punishment.duration > 0
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
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while muting {member.name} ({member.id})",
                            details=e.text,
                        )

                elif (
                    punishment.action_type.name == BouncerActionType.KICK.name
                    and BouncerActionType.BAN.name not in punishment_types
                ):
                    # Kick user
                    try:
                        await member.kick(
                            reason=f"Bouncer: {punishment.reason}",
                        )

                        await manager.create_case(
                            action=CaseType.KICK,
                            user=member,
                            creator_user=self.bot.user,
                            reason=f"Bouncer: {punishment.reason}",
                            source=CaseSource.BOUNCER,
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to kick {member.name} ({member.id})",
                            details=e.text,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Unknown Discord error while kicking {member.name} ({member.id})",
                            details=e.text,
                        )

                elif punishment.action_type.name == BouncerActionType.BAN.name:
                    # Ban user
                    try:
                        await member.ban(
                            reason=f"Bouncer: {punishment.reason}",
                            delete_message_seconds=config.moderation_settings.ban_days * 86400,
                        )

                        await manager.create_case(
                            action=CaseType.BAN,
                            user=member,
                            creator_user=self.bot.user,
                            reason=f"Bouncer: {punishment.reason}",
                            duration=(
                                timedelta(seconds=punishment.duration)
                                if punishment.duration > 0
                                else None
                            ),
                            source=CaseSource.BOUNCER,
                        )
                    except discord.Forbidden as e:
                        await log_error(
                            bot=self.bot,
                            module="Bouncer",
                            guild_id=member.guild.id,
                            error=f"Titanium was not allowed to ban {member.name} ({member.id})",
                            details=e.text,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
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
