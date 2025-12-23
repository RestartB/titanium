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
from lib.embeds.mod_actions import (
    banned,
    forbidden,
    http_exception,
    kicked,
    muted,
    warned,
)
from lib.enums.automod import AutomodActionType, AutomodAntispamType
from lib.enums.moderation import CaseSource, CaseType
from lib.helpers.log_error import log_error
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
        config = await self.bot.fetch_guild_config(message.guild.id) if message.guild else None

        try:
            # Check for server ID in config list
            if (
                not message.guild
                or message.guild.id not in self.bot.guild_configs
                or not config
                or not config.automod_settings
                or not message.author
                or not isinstance(message.author, discord.Member)
                or not self.bot.user
            ):
                self.logger.debug("Automod initial checks failed, skipping message")
                return

            triggers: list[AutomodRule] = []
            punishments: list[AutomodAction] = []

            if not config.automod_enabled:
                self.logger.debug("Automod is not enabled, skipping message")
                return

            config = config.automod_settings

            triggered_word_rule_amount = {}
            malicious_link_count = 0
            phishing_link_count = 0

            self.logger.debug(f"Starting badword detection check for message {message.id}")
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

            self.logger.debug(
                f"Badword detection complete. Triggered counts: {triggered_word_rule_amount}"
            )

            self.logger.debug(f"Starting malicious link check for message {message.id}")
            for link in self.bot.malicious_links:
                if link in message.content:
                    malicious_link_count += 1

            self.logger.debug(f"Malicious link check complete. Count: {malicious_link_count}")

            self.logger.debug(f"Starting phishing link check for message {message.id}")
            for link in self.bot.phishing_links:
                if link in message.content:
                    phishing_link_count += 1

            self.logger.debug(f"Phishing link check complete. Count: {phishing_link_count}")

            if event_type == "new":
                self.logger.debug(
                    f"Adding new message {message.id} to automod queue for user {message.author.id}"
                )
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
                self.logger.debug(
                    f"Checking spam rules against {len(current_state)} messages from user {message.author.id}"
                )
            else:
                self.logger.debug(
                    f"Processing edited message {message.id}, creating temporary state"
                )
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
                        timestamp=message.edited_at if message.edited_at else message.created_at,
                    )
                ]

            # Check for any spam detection
            if len(config.spam_detection_rules) > 0:
                self.logger.debug(
                    f"Checking {len(config.spam_detection_rules)} spam detection rules"
                )
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
                        self.logger.debug(
                            f"Spam rule {rule.id} triggered: {count} >= {rule.threshold} (type: {rule.antispam_type})"
                        )
                        triggers.append(rule)
                        for action in rule.actions:
                            punishments.append(action)
                    else:
                        self.logger.debug(
                            f"Spam rule {rule.id} not triggered: {count} < {rule.threshold} (type: {rule.antispam_type})"
                        )

            # Malicious link check
            self.logger.debug(f"Checking {len(config.malicious_link_rules)} malicious link rules")
            for rule in config.malicious_link_rules:
                latest_timestamp = current_state[0].timestamp
                filtered_messages = [
                    m
                    for m in current_state
                    if (latest_timestamp - m.timestamp).total_seconds() < rule.duration
                ]

                malicious_count = sum(msg.malicious_link_count for msg in filtered_messages)
                if malicious_count >= rule.threshold:
                    self.logger.debug(
                        f"Malicious link rule {rule.id} triggered: {malicious_count} >= {rule.threshold}"
                    )
                    triggers.append(rule)
                    for action in rule.actions:
                        punishments.append(action)
                else:
                    self.logger.debug(
                        f"Malicious link rule {rule.id} not triggered: {malicious_count} < {rule.threshold}"
                    )

            # Phishing link check
            self.logger.debug(f"Checking {len(config.phishing_link_rules)} phishing link rules")
            for rule in config.phishing_link_rules:
                latest_timestamp = current_state[0].timestamp
                filtered_messages = [
                    m
                    for m in current_state
                    if (latest_timestamp - m.timestamp).total_seconds() < rule.duration
                ]

                phishing_count = sum(msg.phishing_link_count for msg in filtered_messages)
                if phishing_count >= rule.threshold:
                    self.logger.debug(
                        f"Phishing link rule {rule.id} triggered: {phishing_count} >= {rule.threshold}"
                    )
                    triggers.append(rule)
                    for action in rule.actions:
                        punishments.append(action)
                else:
                    self.logger.debug(
                        f"Phishing link rule {rule.id} not triggered: {phishing_count} < {rule.threshold}"
                    )

            # Bad word detection
            self.logger.debug(
                f"Checking {len(config.badword_detection_rules)} badword detection rules"
            )
            for rule in config.badword_detection_rules:
                if not rule.words:
                    continue

                latest_timestamp = current_state[0].timestamp
                filtered_messages = [
                    m
                    for m in current_state
                    if (latest_timestamp - m.timestamp).total_seconds() < rule.duration
                ]

                word_count = sum(
                    msg.triggered_word_rule_amount.get(rule.id, 0) for msg in filtered_messages
                )
                if word_count >= rule.threshold:
                    self.logger.debug(
                        f"Badword rule {rule.id} triggered: {word_count} >= {rule.threshold}"
                    )
                    triggers.append(rule)
                    for action in rule.actions:
                        punishments.append(action)
                else:
                    self.logger.debug(
                        f"Badword rule {rule.id} not triggered: {word_count} < {rule.threshold}"
                    )

            # Get list of punishment types
            punishment_types = list(set(action.action_type for action in punishments))
            self.logger.debug(
                f"Total triggers: {len(triggers)}, Total punishments: {len(punishments)}, Punishment types: {punishment_types}"
            )
            embeds: list[discord.Embed] = []

            async with get_session() as session:
                manager = GuildModCaseManager(self.bot, message.guild, session)

                self.logger.debug(f"Processing {len(punishments)} punishments")
                for punishment in punishments:
                    if punishment.action_type == AutomodActionType.SEND_MESSAGE and not isinstance(
                        message.channel, (discord.DMChannel, discord.PartialMessageable)
                    ):
                        self.logger.debug(f"Sending automod message to user {message.author.id}")
                        try:
                            if punishment.message_embed:
                                embed = discord.Embed(description=punishment.message_content)
                                embed.set_author(
                                    name="Titanium Automod",
                                    icon_url=self.bot.user.display_avatar.url,
                                )

                                if punishment.embed_colour:
                                    try:
                                        embed.colour = discord.Colour.from_str(
                                            punishment.embed_colour
                                        )
                                    except ValueError:
                                        embed.colour = discord.Colour.random()
                                else:
                                    embed.colour = discord.Colour.random()

                                if punishment.message_reply:
                                    await message.reply(
                                        embed=embed,
                                        mention_author=punishment.message_mention,
                                        allowed_mentions=discord.AllowedMentions.none(),
                                    )
                                else:
                                    await message.channel.send(
                                        embed=embed,
                                        allowed_mentions=discord.AllowedMentions.none(),
                                    )
                            else:
                                content = f"-# Titanium Automod\n{punishment.message_content}"
                                if punishment.message_reply:
                                    await message.reply(
                                        content=content,
                                        mention_author=punishment.message_mention,
                                        allowed_mentions=discord.AllowedMentions.none(),
                                    )
                                else:
                                    await message.channel.send(
                                        content=content,
                                        allowed_mentions=discord.AllowedMentions.none(),
                                    )

                        except discord.Forbidden as e:
                            await log_error(
                                module="Automod",
                                guild_id=message.guild.id,
                                error=f"Titanium was not allowed to send a message to @{message.author.name} ({message.author.id}) in #{message.channel.name} ({message.channel.id})",
                                details=e.text,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                module="Automod",
                                guild_id=message.guild.id,
                                error=f"Unknown Discord error while sending automod message to @{message.author.name} ({message.author.id})",
                                details=e.text,
                            )
                    elif punishment.action_type == AutomodActionType.DELETE:
                        self.logger.debug(f"Deleting message {message.id}")
                        await message.delete()
                    elif punishment.action_type == AutomodActionType.WARN:
                        self.logger.debug(f"Creating warn case for user {message.author.id}")
                        case, dm_success, dm_error = await manager.create_case(
                            action=CaseType.WARN,
                            user=message.author,
                            creator_user=self.bot.user,
                            reason=f"Automod: {punishment.reason if punishment.reason else 'No reason provided'}",
                            source=CaseSource.AUTOMOD,
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
                        self.logger.debug(f"Processing mute action for user {message.author.id}")
                        # Check if user is already timed out
                        if message.author.is_timed_out():
                            self.logger.debug(
                                f"User {message.author.id} is already timed out, skipping mute"
                            )
                            continue

                        # Time out user
                        try:
                            self.logger.debug(
                                f"Timing out user {message.author.id} for {punishment.duration} seconds"
                            )
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

                            case, dm_success, dm_error = await manager.create_case(
                                action=CaseType.MUTE,
                                user=message.author,
                                creator_user=self.bot.user,
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                                duration=(
                                    timedelta(seconds=punishment.duration)
                                    if punishment.duration > 0
                                    else None
                                ),
                                source=CaseSource.AUTOMOD,
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
                        self.logger.debug(f"Processing kick action for user {message.author.id}")
                        # Kick user
                        try:
                            self.logger.debug(f"Kicking user {message.author.id}")
                            await message.author.kick(
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                            )

                            case, dm_success, dm_error = await manager.create_case(
                                action=CaseType.KICK,
                                user=message.author,
                                creator_user=self.bot.user,
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                                source=CaseSource.AUTOMOD,
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
                        self.logger.debug(f"Processing ban action for user {message.author.id}")
                        # Ban user
                        try:
                            self.logger.debug(f"Banning user {message.author.id}")
                            await message.author.ban(
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                            )

                            case, dm_success, dm_error = await manager.create_case(
                                action=CaseType.BAN,
                                user=message.author,
                                creator_user=self.bot.user,
                                reason=f"{punishment.reason if punishment.reason else 'No reason provided'}",
                                duration=(
                                    timedelta(seconds=punishment.duration)
                                    if punishment.duration > 0
                                    else None
                                ),
                                source=CaseSource.AUTOMOD,
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
                        self.logger.debug(
                            f"Sending {len(embeds)} embeds to channel {message.channel.id}"
                        )
                        await message.channel.send(embeds=embeds)

            if triggers:
                self.logger.debug(f"Logging {len(triggers)} automod triggers to guild logger")
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
        self.logger.debug(f"Received new message event: {message.id}")
        await self.handle_message(message)

    # Listen for message edits
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        self.logger.debug(f"Received raw message edit event: {payload.message_id}")

        if not payload.data.get("guild_id"):
            self.logger.debug(f"Message edit event {payload.message_id} has no guild_id, skipping")
            return

        if "content" not in payload.data:
            self.logger.debug(f"{payload.message_id} edit has no content in payload data")
            return

        message = payload.message
        if not message.content or any([message.webhook_id, message.embeds, message.poll]):
            self.logger.debug(
                f"Ignoring {payload.message_id} edit due to content type / no content"
            )
            return

        if payload.cached_message and payload.cached_message.content == payload.data["content"]:
            self.logger.debug(
                f"Message content is the same as cached message for {payload.message_id}"
            )
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel or not isinstance(channel, discord.abc.Messageable):
            return

        self.logger.debug(f"Processing edited message {payload.message_id}")
        await self.handle_message(message, event_type="edit")


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(AutomodMonitorCog(bot))
