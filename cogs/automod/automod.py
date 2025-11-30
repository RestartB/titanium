import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING, Literal

import discord
import emoji
from discord.ext import commands

from lib.classes.automod_message import AutomodMessage
from lib.classes.case_manager import GuildModCaseManager
from lib.classes.guild_logger import GuildLogger
from lib.embeds.dm_notifs import banned_dm, kicked_dm, muted_dm, warned_dm
from lib.embeds.mod_actions import (
    banned,
    forbidden,
    http_exception,
    kicked,
    muted,
    warned,
)
from lib.enums.automod import AutomodActionType, AutomodAntispamType
from lib.helpers.log_error import log_error
from lib.helpers.send_dm import send_dm
from lib.sql.sql import AutomodAction, AutomodRule, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class AutomodMonitorCog(commands.Cog):
    """Monitors new messages for automod triggers and creates cases/punishments"""

    # -------------------------
    # New messages: new messages will be added to the queue for spam checks
    # Edited messages: only the edited message will be checked for triggers
    # -------------------------

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("automod")

    async def handle_message(
        self, message: discord.Message, event_type: Literal["new", "edit"] = "new"
    ):
        self.logger.debug(f"Processing message from {message.author}: {message.id}")

        try:
            # Check for server ID in config list
            if (
                not message.guild
                or message.guild.id not in self.bot.guild_configs
                or not self.bot.guild_configs[message.guild.id].automod_settings
                or not message.author
                or not isinstance(message.author, discord.Member)
                or not self.bot.user
            ):
                self.logger.debug("Automod initial checks failed, skipping message")
                return

            triggers: list[AutomodRule] = []
            punishments: list[AutomodAction] = []

            if not self.bot.guild_configs[message.guild.id].automod_enabled:
                self.logger.debug("Automod is not enabled, skipping message")
                return

            config = self.bot.guild_configs[message.guild.id].automod_settings

            triggered_word_rule_amount = {}
            malicious_link_count = 0
            phishing_link_count = 0

            for rule in config.badword_detection_rules:
                triggered_word_rule_amount[rule.id] = 0
                content_to_check = (
                    message.content.lower() if not rule.case_sensitive else message.content
                )

                for word in rule.words:
                    check_word = word.lower() if not rule.case_sensitive else word

                    if rule.match_whole_word:
                        pattern = r"\b" + re.escape(check_word) + r"\b"
                        matches = re.findall(pattern, content_to_check)
                    else:
                        pattern = re.escape(check_word)
                        matches = re.findall(pattern, content_to_check)

                    triggered_word_rule_amount[rule.id] += len(matches)

            for link in self.bot.malicious_links:
                if link in message.content:
                    malicious_link_count += 1

            for link in self.bot.phishing_links:
                if link in message.content:
                    phishing_link_count += 1

            if event_type == "new":
                self.bot.automod_messages.setdefault(message.guild.id, {}).setdefault(
                    message.author.id, []
                ).append(
                    AutomodMessage(
                        user_id=message.author.id,
                        message_id=message.id,
                        channel_id=message.channel.id,
                        triggered_word_rule_amount=triggered_word_rule_amount,
                        malicious_link_count=malicious_link_count,
                        phishing_link_count=phishing_link_count,
                        mention_count=len(message.mentions)
                        + len(message.role_mentions)
                        + (1 if message.mention_everyone else 0),
                        word_count=len(message.clean_content.split()),
                        newline_count=len(message.clean_content.splitlines()),
                        link_count=len(
                            re.findall(
                                r"(http|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])",
                                message.content,
                            )
                        ),
                        attachment_count=len(message.attachments),
                        emoji_count=len(emoji.emoji_list(message.content))
                        + len(re.findall(r"(<a?)?:\w+:(\d{18}>)?", message.content)),
                        timestamp=message.created_at,
                    )
                )

                # Limit to 100 messages
                self.bot.automod_messages[message.guild.id][message.author.id] = (
                    self.bot.automod_messages[message.guild.id][message.author.id][-100:]
                )

                current_state = self.bot.automod_messages[message.guild.id][
                    message.author.id
                ].copy()
                current_state.reverse()
            else:
                current_state = [
                    AutomodMessage(
                        user_id=message.author.id,
                        message_id=message.id,
                        channel_id=message.channel.id,
                        triggered_word_rule_amount=triggered_word_rule_amount,
                        malicious_link_count=malicious_link_count,
                        phishing_link_count=phishing_link_count,
                        mention_count=len(message.mentions)
                        + len(message.role_mentions)
                        + (1 if message.mention_everyone else 0),
                        word_count=len(message.clean_content.split()),
                        newline_count=len(message.clean_content.splitlines()),
                        link_count=len(
                            re.findall(
                                r"(http|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])",
                                message.content,
                            )
                        ),
                        attachment_count=len(message.attachments),
                        emoji_count=len(emoji.emoji_list(message.content))
                        + len(re.findall(r"(<a?)?:\w+:(\d{18}>)?", message.content)),
                        timestamp=message.created_at,
                    )
                ]

            # Check for any spam detection
            if len(config.spam_detection_rules) > 0:
                for rule in config.spam_detection_rules:
                    latest_timestamp = current_state[0].timestamp
                    filtered_messages = [
                        m
                        for m in current_state
                        if (latest_timestamp - m.timestamp).total_seconds() < rule.duration
                    ]

                    if rule.antispam_type == AutomodAntispamType.MESSAGE:
                        count = len(list(filtered_messages))
                    elif rule.antispam_type == AutomodAntispamType.MENTION:
                        count = sum(m.mention_count for m in filtered_messages)
                    elif rule.antispam_type == AutomodAntispamType.WORD:
                        count = sum(m.word_count for m in filtered_messages)
                    elif rule.antispam_type == AutomodAntispamType.NEWLINE:
                        count = sum(m.newline_count for m in filtered_messages)
                    elif rule.antispam_type == AutomodAntispamType.LINK:
                        count = sum(m.link_count for m in filtered_messages)
                    elif rule.antispam_type == AutomodAntispamType.ATTACHMENT:
                        count = sum(m.attachment_count for m in filtered_messages)
                    elif rule.antispam_type == AutomodAntispamType.EMOJI:
                        count = sum(m.emoji_count for m in filtered_messages)
                    else:
                        continue

                    if count >= rule.threshold:
                        triggers.append(rule)
                        for action in rule.actions:
                            punishments.append(action)

            # Malicious link check
            for rule in config.malicious_link_rules:
                latest_timestamp = current_state[0].timestamp
                filtered_messages = [
                    m
                    for m in current_state
                    if (latest_timestamp - m.timestamp).total_seconds() < rule.duration
                ]

                if sum(msg.malicious_link_count for msg in filtered_messages) >= rule.threshold:
                    triggers.append(rule)
                    for action in rule.actions:
                        punishments.append(action)

            # Phishing link check
            for rule in config.phishing_link_rules:
                latest_timestamp = current_state[0].timestamp
                filtered_messages = [
                    m
                    for m in current_state
                    if (latest_timestamp - m.timestamp).total_seconds() < rule.duration
                ]

                if sum(msg.phishing_link_count for msg in filtered_messages) >= rule.threshold:
                    triggers.append(rule)
                    for action in rule.actions:
                        punishments.append(action)

            # Bad word detection
            for rule in config.badword_detection_rules:
                if not rule.words:
                    continue

                latest_timestamp = current_state[0].timestamp
                filtered_messages = [
                    m
                    for m in current_state
                    if (latest_timestamp - m.timestamp).total_seconds() < rule.duration
                ]

                if (
                    sum(msg.triggered_word_rule_amount.get(rule.id, 0) for msg in filtered_messages)
                    >= rule.threshold
                ):
                    triggers.append(rule)
                    for action in rule.actions:
                        punishments.append(action)

            # Get list of punishment types
            punishment_types = list(set(action.action_type for action in punishments))
            embeds: list[discord.Embed] = []

            async with get_session() as session:
                manager = GuildModCaseManager(self.bot, message.guild, session)

                for punishment in punishments:
                    if punishment.action_type == AutomodActionType.DELETE:
                        await message.delete()
                    elif punishment.action_type == AutomodActionType.WARN:
                        case = await manager.create_case(
                            action="warn",
                            user_id=message.author.id,
                            creator_user_id=self.bot.user.id,
                            reason=f"Automod: {punishment.reason if punishment.reason else 'No reason provided'}",
                        )

                        dm_success, dm_error = await send_dm(
                            embed=warned_dm(self.bot, message, case),
                            user=message.author,
                            source_guild=message.guild,
                            module="Automod",
                            action="warning",
                        )

                        embeds.append(
                            warned(
                                self.bot,
                                message.author,
                                self.bot.user,
                                case,
                                dm_success=dm_success,
                                dm_error=dm_error,
                            )
                        )
                    elif punishment.action_type == AutomodActionType.MUTE:
                        # Check if user is already timed out
                        if message.author.is_timed_out():
                            continue

                        # Time out user
                        try:
                            await message.author.timeout(
                                (
                                    timedelta(seconds=punishment.duration)
                                    if punishment.duration > 0
                                    and timedelta(seconds=punishment.duration).total_seconds()
                                    <= 2419200
                                    else timedelta(seconds=2419200)
                                ),
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                            )

                            case = await manager.create_case(
                                action="mute",
                                user_id=message.author.id,
                                creator_user_id=self.bot.user.id,
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                                duration=(
                                    timedelta(seconds=punishment.duration)
                                    if punishment.duration > 0
                                    else None
                                ),
                            )

                            dm_success, dm_error = await send_dm(
                                embed=muted_dm(self.bot, message, case),
                                user=message.author,
                                source_guild=message.guild,
                                module="Automod",
                                action="muting",
                            )

                            embeds.append(
                                muted(
                                    self.bot,
                                    message.author,
                                    self.bot.user,
                                    case,
                                    dm_success=dm_success,
                                    dm_error=dm_error,
                                )
                            )
                        except discord.Forbidden as e:
                            await log_error(
                                module="Automod",
                                guild_id=message.guild.id,
                                error=f"Titanium was not allowed to mute @{message.author.name} ({message.author.id})",
                                details=e.text,
                            )
                            embeds.append(forbidden(self.bot, message.author))
                        except discord.HTTPException as e:
                            await log_error(
                                module="Automod",
                                guild_id=message.guild.id,
                                error=f"Unknown Discord error while muting @{message.author.name} ({message.author.id})",
                                details=e.text,
                            )
                            embeds.append(http_exception(self.bot, message.author))

                    elif (
                        punishment.action_type == AutomodActionType.KICK
                        and AutomodActionType.BAN not in punishment_types
                    ):
                        # Kick user
                        try:
                            await message.author.kick(
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                            )

                            case = await manager.create_case(
                                action="kick",
                                user_id=message.author.id,
                                creator_user_id=self.bot.user.id,
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                            )

                            dm_success, dm_error = await send_dm(
                                embed=kicked_dm(self.bot, message, case),
                                user=message.author,
                                source_guild=message.guild,
                                module="Automod",
                                action="kicking",
                            )

                            embeds.append(
                                kicked(
                                    self.bot,
                                    message.author,
                                    self.bot.user,
                                    case,
                                    dm_success=dm_success,
                                    dm_error=dm_error,
                                )
                            )
                        except discord.Forbidden as e:
                            await log_error(
                                module="Automod",
                                guild_id=message.guild.id,
                                error=f"Titanium was not allowed to kick @{message.author.name} ({message.author.id})",
                                details=e.text,
                            )
                            embeds.append(forbidden(self.bot, message.author))
                        except discord.HTTPException as e:
                            await log_error(
                                module="Automod",
                                guild_id=message.guild.id,
                                error=f"Unknown Discord error while kicking @{message.author.name} ({message.author.id})",
                                details=e.text,
                            )
                            embeds.append(http_exception(self.bot, message.author))
                    elif punishment.action_type == AutomodActionType.BAN:
                        # Ban user
                        try:
                            await message.author.ban(
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                            )

                            case = await manager.create_case(
                                action="ban",
                                user_id=message.author.id,
                                creator_user_id=self.bot.user.id,
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                                duration=(
                                    timedelta(seconds=punishment.duration)
                                    if punishment.duration > 0
                                    else None
                                ),
                            )

                            dm_success, dm_error = await send_dm(
                                embed=banned_dm(self.bot, message, case),
                                user=message.author,
                                source_guild=message.guild,
                                module="Automod",
                                action="banning",
                            )

                            embeds.append(
                                banned(
                                    self.bot,
                                    message.author,
                                    self.bot.user,
                                    case,
                                    dm_success=dm_success,
                                    dm_error=dm_error,
                                )
                            )
                        except discord.Forbidden as e:
                            await log_error(
                                module="Automod",
                                guild_id=message.guild.id,
                                error=f"Titanium was not allowed to ban @{message.author.name} ({message.author.id})",
                                details=e.text,
                            )
                            embeds.append(forbidden(self.bot, message.author))
                        except discord.HTTPException as e:
                            await log_error(
                                module="Automod",
                                guild_id=message.guild.id,
                                error=f"Unknown Discord error while banning @{message.author.name} ({message.author.id})",
                                details=e.text,
                            )
                            embeds.append(http_exception(self.bot, message.author))

                    if embeds:
                        await message.channel.send(embeds=embeds)

            if triggers:
                guild_logger = GuildLogger(self.bot, message.guild)
                await guild_logger.titanium_automod_trigger(
                    rules=triggers,
                    actions=punishments,
                    message=message,
                )

            self.logger.debug(f"Processed message from {message.author}: {message.id}")
        except Exception as e:
            await log_error(
                module="Automod",
                guild_id=message.guild.id if message.guild else None,
                error=f"An unknown error occurred while processing automod for message {message.id} from @{message.author.name} ({message.author.id})",
                exc=e,
            )

    # Listen for messages
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.handle_message(message)

    # Listen for message edits
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        if not payload.data.get("guild_id"):
            return

        if not payload.data.get("content"):
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel or not isinstance(channel, discord.abc.Messageable):
            return

        if payload.cached_message:
            message = payload.cached_message
        else:
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.NotFound:
                return
            except discord.Forbidden:
                return
            except discord.HTTPException:
                return

        await self.handle_message(message)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(AutomodMonitorCog(bot))
