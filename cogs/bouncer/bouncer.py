import logging
import re
import unicodedata
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord.utils import utcnow

from lib.classes.case_manager import GuildModCaseManager
from lib.classes.guild_logger import GuildLogger
from lib.enums.bouncer import BouncerActionType, BouncerCriteriaType, BouncerEventType
from lib.enums.moderation import CaseSource, CaseType
from lib.helpers.log_error import log_error
from lib.sql.sql import BouncerAction, BouncerRule, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


# FIXME: create a migration for existing single role_id to list of role_ids


class BouncerMonitorCog(commands.Cog):
    """Monitors joiners and member updates for bouncer triggers and creates cases/punishments"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("bouncer")

    def normalise_automod_text(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        return "".join(char for char in text if unicodedata.category(char) != "Cf")

    async def handle_event(
        self,
        member: discord.Member,
        event_type: BouncerEventType,
        payload_time: datetime | None = None,
    ):
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

        bouncer_config = config.bouncer_settings

        triggered_rules: list[BouncerRule] = []
        triggered_actions: list[BouncerAction] = []

        rules = bouncer_config.rules.copy()
        rules.sort(key=lambda r: r.order)

        self.logger.debug(f"Bouncer enabled: {config.bouncer_enabled}")

        if not config.bouncer_enabled or not config.moderation_enabled:
            self.logger.debug("Bouncer is disabled, skipping member")
            return

        self.logger.debug(f"Will evaluate {len(rules)} rules")
        for rule in rules:
            self.logger.debug(f"({rule.id}) Evaluating...")

            if not rule.enabled:
                self.logger.debug(f"({rule.id}) Rule disabled")
                continue

            if event_type == BouncerEventType.UPDATE and not rule.evaluate_for_existing_members:
                self.logger.debug(f"({rule.id}) Not evaluating user update")
                continue

            criterion_matched = 0
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
                            words_matched = 0
                            for word in criteria.words:
                                normalised_word = self.normalise_automod_text(word)

                                pattern = r"\b" + re.escape(normalised_word) + r"\b"
                                if not criteria.match_whole_word:
                                    pattern = pattern.lstrip(r"\b").rstrip(r"\b")

                                matches = re.findall(
                                    pattern,
                                    self.normalise_automod_text(content_to_check),
                                    flags=(0 if criteria.case_sensitive else re.IGNORECASE),
                                )
                                if matches:
                                    words_matched += 1

                            if (
                                criteria.match_all_words
                                and words_matched == len(criteria.words)
                                or (not criteria.match_all_words and words_matched > 0)
                            ):
                                criteria_met = True
                                break

                        if criteria_met:
                            self.logger.debug("Username match found")
                            criterion_matched += 1
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
                            criterion_matched += 1
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
                        criterion_matched += 1
                elif criteria.type == BouncerCriteriaType.AVATAR and not member.avatar:
                    self.logger.debug("No avatar match found")
                    criterion_matched += 1
                elif (
                    criteria.type == BouncerCriteriaType.REACTION
                    and event_type == BouncerEventType.REACTION
                    and member.joined_at
                ):
                    if not payload_time:
                        continue

                    if payload_time - member.joined_at > timedelta(seconds=3):
                        continue

                    self.logger.debug("Suspicious bot reaction behaviour found")
                    criterion_matched += 1

            if (rule.match_all_criteria and criterion_matched == len(rule.criteria)) or (
                not rule.match_all_criteria and criterion_matched > 0
            ):
                self.logger.debug(f"({rule.id}) Rule met")
                triggered_rules.append(rule)
                triggered_actions.extend(rule.actions)

                if rule.stop_if_triggered:
                    break
            else:
                self.logger.debug(f"({rule.id}) Rule not met")

        processed_actions = [
            action
            for action in triggered_actions
            if action.type
            not in [BouncerActionType.MUTE, BouncerActionType.KICK, BouncerActionType.BAN]
        ]

        kicks = [action for action in triggered_actions if action.type == BouncerActionType.KICK]
        if kicks:
            processed_actions.append(kicks[0])

        mutes = [action for action in triggered_actions if action.type == BouncerActionType.MUTE]
        if mutes:
            mute_added = False

            for mute in mutes:
                if not mute.duration:
                    processed_actions.append(mute)
                    mute_added = True
                    break

            if not mute_added:
                mutes.sort(key=lambda m: m.duration if m.duration else 0, reverse=True)
                processed_actions.append(mutes[0])

        bans = [action for action in triggered_actions if action.type == BouncerActionType.BAN]
        if bans:
            ban_added = False

            for ban in bans:
                if not ban.duration:
                    processed_actions.append(ban)
                    ban_added = True
                    break

            if not ban_added:
                bans.sort(key=lambda b: b.duration if b.duration else 0, reverse=True)
                processed_actions.append(bans[0])

        successful_actions: list[BouncerAction] = []
        failed_actions: dict[BouncerAction, str] = {}

        async with get_session() as session:
            manager = GuildModCaseManager(self.bot, member.guild, session)

            self.logger.debug(f"Will process {len(processed_actions)} actions")

            for action in processed_actions:
                self.logger.debug(f"({action.id}) Processing {action.type} action...")

                try:
                    if action.type == BouncerActionType.WARN:
                        case, _, _ = await manager.create_case(
                            action=CaseType.WARN,
                            user=member,
                            creator_user=self.bot.user,
                            reason=action.reason,
                            source=CaseSource.AUTOMOD,
                        )
                    elif action.type == BouncerActionType.MUTE:
                        # fmt: off
                        if member.top_role >= member.guild.me.top_role:
                            failed_actions[action] = "No permission to mute this user (Titanium's role not higher than user's top role)"
                            continue
                        elif not member.guild.me.guild_permissions.moderate_members:
                            failed_actions[action] = "No mute permissions"
                            continue
                        # fmt: on

                        await member.timeout(
                            (
                                timedelta(seconds=action.duration)
                                if action.duration and action.duration <= 2419200
                                else timedelta(seconds=2419200)
                            ),
                            reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                        )

                        case, _, _ = await manager.create_case(
                            action=CaseType.MUTE,
                            user=member,
                            creator_user=self.bot.user,
                            reason=action.reason,
                            duration=timedelta(seconds=action.duration)
                            if action.duration
                            else None,
                            source=CaseSource.AUTOMOD,
                        )
                    elif action.type == BouncerActionType.KICK:
                        # fmt: off
                        if member.top_role >= member.guild.me.top_role:
                            failed_actions[action] = "No permission to kick this user (Titanium's role not higher than user's top role)"
                            continue
                        elif not member.guild.me.guild_permissions.kick_members:
                            failed_actions[action] = "No kick permissions"
                            continue
                        # fmt: on

                        case, _, _ = await manager.create_case(
                            action=CaseType.KICK,
                            user=member,
                            creator_user=self.bot.user,
                            reason=action.reason,
                            source=CaseSource.AUTOMOD,
                        )

                        try:
                            await member.kick(
                                reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                            )
                        except Exception:
                            await manager.delete_case(case.id, raise_not_found=False)
                            raise
                    elif action.type == BouncerActionType.BAN:
                        # fmt: off
                        if member.top_role >= member.guild.me.top_role:
                            failed_actions[action] = "No permission to ban this user (Titanium's role not higher than user's top role)"
                            continue
                        elif not member.guild.me.guild_permissions.ban_members:
                            failed_actions[action] = "No ban permissions"
                            continue
                        # fmt: on

                        case, _, _ = await manager.create_case(
                            action=CaseType.BAN,
                            user=member,
                            creator_user=self.bot.user,
                            reason=action.reason,
                            duration=timedelta(seconds=action.duration)
                            if action.duration
                            else None,
                            source=CaseSource.AUTOMOD,
                        )

                        try:
                            await member.ban(
                                delete_message_seconds=config.moderation_settings.ban_days * 86400,
                                reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                            )
                        except Exception:
                            await manager.delete_case(case.id, raise_not_found=False)
                            raise
                    elif action.type == BouncerActionType.ADD_ROLE:
                        # fmt: off
                        if member.top_role >= member.guild.me.top_role:
                            failed_actions[action] = "No permission to manage this user (Titanium's role below user's top role)"
                            continue
                        elif not member.guild.me.guild_permissions.manage_roles:
                            failed_actions[action] = "No manage role permissions"
                            continue
                        # fmt: on

                        roles: list[discord.Role] = []
                        for role_id in set(action.role_ids):
                            role = member.guild.get_role(role_id)
                            if role and member.guild.me.top_role > role:
                                roles.append(role)

                        await member.add_roles(
                            *roles,
                            reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                            atomic=False,
                        )
                    elif action.type == BouncerActionType.REMOVE_ROLE:
                        # fmt: off
                        if member.top_role >= member.guild.me.top_role:
                            failed_actions[action] = "No permission to manage this user (Titanium's role below user's top role)"
                            continue
                        elif not member.guild.me.guild_permissions.manage_roles:
                            failed_actions[action] = "No manage role permissions"
                            continue
                        # fmt: on

                        roles: list[discord.Role] = []
                        for role_id in set(action.role_ids):
                            role = member.guild.get_role(role_id)
                            if role and member.guild.me.top_role > role:
                                roles.append(role)

                        await member.remove_roles(
                            *roles,
                            reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                            atomic=False,
                        )
                    elif action.type == BouncerActionType.TOGGLE_ROLE:
                        # fmt: off
                        if member.top_role >= member.guild.me.top_role:
                            failed_actions[action] = "No permission to manage this user (Titanium's role below user's top role)"
                            continue
                        elif not member.guild.me.guild_permissions.manage_roles:
                            failed_actions[action] = "No manage role permissions"
                            continue
                        # fmt: on

                        roles_to_add: list[discord.Role] = []
                        roles_to_remove: list[discord.Role] = []

                        for role_id in set(action.role_ids):
                            role = member.guild.get_role(role_id)
                            if not role or member.guild.me.top_role <= role:
                                continue

                            if role in member.roles:
                                roles_to_remove.append(role)
                            else:
                                roles_to_add.append(role)

                        if roles_to_add:
                            await member.add_roles(
                                *roles_to_add,
                                reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                                atomic=False,
                            )

                        if roles_to_remove:
                            await member.remove_roles(
                                *roles_to_remove,
                                reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                                atomic=False,
                            )
                    else:
                        self.logger.warning(
                            f"({action.id}) Unknown action type: {action.type.value}"
                        )
                        continue

                    successful_actions.append(action)
                    self.logger.debug(f"({action.id}) Processed.")
                except discord.Forbidden as e:
                    failed_actions[action] = e.text
                    await log_error(
                        bot=self.bot,
                        module="Automod",
                        guild_id=member.guild.id,
                        error=f"Titanium was not allowed to perform the {action.type.value} action against @{member.name} ({member.id})",
                        details=e.text,
                        exc=e,
                    )
                except discord.HTTPException as e:
                    failed_actions[action] = "Unknown Discord error occurred"
                    await log_error(
                        bot=self.bot,
                        module="Automod",
                        guild_id=member.guild.id,
                        error=f"Unknown Discord error occurred while processing {action.type.value} against @{member.name} ({member.id})",
                        details=e.text,
                        exc=e,
                    )
                except Exception as e:
                    failed_actions[action] = "Unexpected error occurred"
                    await log_error(
                        bot=self.bot,
                        module="Automod",
                        guild_id=member.guild.id,
                        error=f"Unexpected error occurred while processing {action.type.value} against @{member.name} ({member.id})",
                        exc=e,
                    )

        if triggered_rules:
            guild_logger = GuildLogger(self.bot, member.guild)
            await guild_logger.titanium_bouncer_trigger(
                rules=triggered_rules,
                successful_actions=successful_actions,
                failed_actions=failed_actions,
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

    # Listen for reactions added
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # only available if this is a reaction add event, and in a guild
        # this doesn't rely on the member cache so this is safe to use
        if not payload.member:
            return

        try:
            payload_time = utcnow()
            await self.handle_event(payload.member, BouncerEventType.REACTION, payload_time)
        except Exception as e:
            await log_error(
                bot=self.bot,
                module="Bouncer",
                guild_id=payload.guild_id,
                error=f"An unknown error occurred while processing a user update for @{payload.member.name} ({payload.member.id})",
                exc=e,
            )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(BouncerMonitorCog(bot))
