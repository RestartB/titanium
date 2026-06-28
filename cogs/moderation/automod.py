import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal

import discord
import emoji
from discord.ext import commands

import lib.embeds.mod_actions as mod_embeds
from lib.classes.automod_message import AutomodMessage
from lib.classes.case_manager import GuildModCaseManager
from lib.classes.guild_logger import GuildLogger
from lib.enums.automod import AutomodActionType, AutomodCriteriaType
from lib.enums.moderation import CaseSource, CaseType
from lib.helpers.log_error import log_error
from lib.sql.sql import AutomodAction, AutomodRule, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class AutomodMonitorCog(commands.Cog):
    """Monitors new messages for automod triggers and creates cases/punishments"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("automod")

    async def handle_message(
        self, message: discord.Message, event_type: Literal["new", "edit"] = "new"
    ):
        self.logger.debug(f"Processing message from {message.author}: {message.id}")
        config = await self.bot.fetch_guild_config(message.guild.id) if message.guild else None

        # support forwarded messages
        content_to_check = message.content
        if message.message_snapshots:
            content_to_check = message.message_snapshots[0].content

        try:
            # Check for server ID in config list
            if (
                not message.guild
                or not config
                or not config.automod_settings
                or not message.author
                or not isinstance(message.author, discord.Member)
                or not self.bot.user
                or message.author.id == self.bot.user.id
            ):
                self.logger.debug("Automod initial checks failed, skipping message")
                return

            if not config.automod_enabled or not config.moderation_enabled:
                self.logger.debug("Automod is disabled, skipping message")
                return

            automod_config = config.automod_settings
            current_state: list[AutomodMessage] = []

            automod_message = AutomodMessage(
                user_id=message.author.id,
                message_id=message.id,
                channel_id=message.channel.id,
                mention_count=len(message.mentions)
                + len(message.role_mentions)
                + (1 if message.mention_everyone else 0),
                word_count=len(message.clean_content.split()),
                newline_count=len(message.clean_content.splitlines()),
                link_count=len(
                    re.findall(
                        r"(http|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])",
                        content_to_check,
                    )
                ),
                attachment_count=len(message.attachments),
                emoji_count=len(emoji.emoji_list(content_to_check))
                + len(re.findall(r"(<a?)?:\w+:(\d{18}>)?", content_to_check)),
                timestamp=message.edited_at
                if event_type == "edit" and message.edited_at
                else message.created_at,
            )

            if event_type == "new":
                self.logger.debug(
                    f"Adding new message {message.id} to automod queue for user {message.author.id}"
                )
                self.bot.automod_messages.setdefault(message.guild.id, {}).setdefault(
                    message.author.id, []
                ).append(automod_message)

                # Limit to 100 messages
                self.bot.automod_messages[message.guild.id][message.author.id] = (
                    self.bot.automod_messages[message.guild.id][message.author.id][-100:]
                )

                current_state = self.bot.automod_messages[message.guild.id][
                    message.author.id
                ].copy()
                current_state.reverse()
            else:
                current_state = [automod_message]

            triggered_rules: list[AutomodRule] = []
            triggered_actions: list[AutomodAction] = []
            messages_to_delete: dict[int, list[int]] = {}

            for rule in automod_config.rules:
                if not rule.enabled:
                    self.logger.warning(f"({rule.id}) Rule disabled")
                    continue

                if not rule.evaluate_edits and event_type == "edit":
                    self.logger.warning(f"({rule.id}) Not evaluating edit")
                    continue

                criterion_matched = 0
                for criteria in rule.criteria:
                    if criteria.criteria_type.value.endswith("_spam"):
                        duration = criteria.duration
                        threshold = criteria.threshold

                        # check required values for spam filters are present
                        if not current_state or duration is None or threshold is None:
                            continue

                        if event_type == "new":
                            filtered_messages = [
                                past_message
                                for past_message in current_state
                                if (message.created_at - past_message.timestamp).total_seconds()
                                <= duration
                            ]
                        else:
                            filtered_messages = current_state.copy()

                        if criteria.criteria_type == AutomodCriteriaType.MESSAGE_SPAM:
                            if len(filtered_messages) >= threshold:
                                criterion_matched += 1

                                for past_message in filtered_messages:
                                    messages_to_delete.setdefault(
                                        past_message.channel_id, []
                                    ).append(past_message.message_id)
                        else:
                            # fmt: off
                            if criteria.criteria_type == AutomodCriteriaType.MENTION_SPAM:
                                count = sum(
                                    [
                                        past_message.mention_count
                                        for past_message in filtered_messages
                                    ]
                                )
                            elif criteria.criteria_type == AutomodCriteriaType.WORD_SPAM:
                                count = sum(
                                    [
                                        past_message.word_count
                                        for past_message in filtered_messages
                                    ]
                                )
                            elif criteria.criteria_type == AutomodCriteriaType.NEWLINE_SPAM:
                                count = sum(
                                    [
                                        past_message.newline_count
                                        for past_message in filtered_messages
                                    ]
                                )
                            elif criteria.criteria_type == AutomodCriteriaType.LINK_SPAM:
                                count = sum(
                                    [
                                        past_message.link_count
                                        for past_message in filtered_messages
                                        ]
                                )
                            elif criteria.criteria_type == AutomodCriteriaType.ATTACHMENT_SPAM:
                                count = sum(
                                    [
                                        past_message.attachment_count
                                        for past_message in filtered_messages
                                    ]
                                )
                            elif criteria.criteria_type == AutomodCriteriaType.EMOJI_SPAM:
                                count = sum(
                                    [
                                        past_message.emoji_count
                                        for past_message in filtered_messages
                                    ]
                                )
                            else:
                                self.logger.warning(
                                    f"({rule.id}) Unknown rule type: {criteria.criteria_type}"
                                )
                            # fmt: on

                            if count >= threshold:
                                criterion_matched += 1

                                for past_message in filtered_messages:
                                    messages_to_delete.setdefault(
                                        past_message.channel_id, []
                                    ).append(past_message.message_id)

                    criteria_met = False

                    if criteria.criteria_type == AutomodCriteriaType.WORD_LIST:
                        words_matched = 0
                        for word in criteria.words:
                            pattern = r"\b" + re.escape(word) + r"\b"
                            if not criteria.match_whole_word:
                                pattern = pattern.lstrip(r"\b").rstrip(r"\b")

                            matches = re.findall(
                                pattern,
                                content_to_check,
                                flags=(0 if criteria.case_sensitive else re.IGNORECASE),
                            )
                            if matches:
                                words_matched += 1

                        if criteria.match_all_words and words_matched == len(criteria.words):
                            criteria_met = True
                        elif not criteria.match_all_words and words_matched > 0:
                            criteria_met = True
                    elif criteria.criteria_type == AutomodCriteriaType.MALICIOUS_LINK:
                        for link in self.bot.malicious_links:
                            if link in content_to_check:
                                criteria_met = True
                                break
                    elif criteria.criteria_type == AutomodCriteriaType.PHISHING_LINK:
                        for link in self.bot.phishing_links:
                            if link in content_to_check:
                                criteria_met = True
                                break
                    else:
                        self.logger.warning(
                            f"({rule.id}) Unknown rule type: {criteria.criteria_type}"
                        )
                        continue

                    if criteria_met:
                        criterion_matched += 1
                        messages_to_delete.setdefault(message.channel.id, []).append(message.id)

                if rule.match_all_criteria and criterion_matched == len(rule.criteria):
                    self.logger.warning(f"({rule.id}) Rule met")
                    triggered_rules.append(rule)
                    triggered_actions.extend(rule.actions)
                elif not rule.match_all_criteria and criterion_matched > 0:
                    self.logger.warning(f"({rule.id}) Rule met")
                    triggered_rules.append(rule)
                    triggered_actions.extend(rule.actions)
                else:
                    self.logger.warning(f"({rule.id}) Rule not met")

            del_kwargs: dict[str, Any] = (
                {"delete_after": 5.0}
                if config and config.moderation_settings.delete_confirmation
                else {}
            )

            processed_actions = [
                action
                for action in triggered_actions
                if action.action_type
                not in [AutomodActionType.MUTE, AutomodActionType.KICK, AutomodActionType.BAN]
            ]

            kicks = [
                action
                for action in triggered_actions
                if action.action_type == AutomodActionType.KICK
            ]
            if kicks:
                processed_actions.append(kicks[0])

            mutes = [
                action
                for action in triggered_actions
                if action.action_type == AutomodActionType.MUTE
            ]
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

            bans = [
                action
                for action in triggered_actions
                if action.action_type == AutomodActionType.BAN
            ]
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

            embeds: list[discord.Embed] = []
            async with get_session() as session:
                manager = GuildModCaseManager(self.bot, message.guild, session)

                self.logger.debug(f"Processing {len(processed_actions)} actions")
                for action in processed_actions:
                    if action.action_type == AutomodActionType.WARN:
                        case, dm_success, dm_error = await manager.create_case(
                            action=CaseType.WARN,
                            user=message.author,
                            creator_user=self.bot.user,
                            reason=action.reason,
                            source=CaseSource.AUTOMOD,
                        )
                        embeds.append(
                            mod_embeds.warned(
                                bot=self.bot,
                                user=message.author,
                                creator=self.bot.user,
                                case=case,
                                dm_success=dm_success,
                                dm_error=dm_error,
                            )
                        )
                    elif action.action_type == AutomodActionType.MUTE:
                        await message.author.timeout(
                            (
                                timedelta(seconds=action.duration)
                                if action.duration and action.duration <= 2419200
                                else timedelta(seconds=2419200)
                            ),
                            reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                        )
                        await manager.create_case(
                            action=CaseType.MUTE,
                            user=message.author,
                            creator_user=self.bot.user,
                            reason=action.reason,
                            duration=timedelta(seconds=action.duration)
                            if action.duration
                            else None,
                            source=CaseSource.AUTOMOD,
                        )
                        embeds.append(
                            mod_embeds.muted(
                                bot=self.bot,
                                user=message.author,
                                creator=self.bot.user,
                                case=case,
                                dm_success=dm_success,
                                dm_error=dm_error,
                            )
                        )
                    elif action.action_type == AutomodActionType.BAN:
                        await message.author.ban(
                            delete_message_seconds=config.moderation_settings.ban_days * 86400,
                            reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                        )
                        await manager.create_case(
                            action=CaseType.BAN,
                            user=message.author,
                            creator_user=self.bot.user,
                            reason=action.reason,
                            duration=timedelta(seconds=action.duration)
                            if action.duration
                            else None,
                            source=CaseSource.AUTOMOD,
                        )
                        embeds.append(
                            mod_embeds.banned(
                                bot=self.bot,
                                user=message.author,
                                creator=self.bot.user,
                                case=case,
                                dm_success=dm_success,
                                dm_error=dm_error,
                            )
                        )
                    elif action.action_type == AutomodActionType.DELETE:
                        for channel_id in messages_to_delete:
                            channel = message.guild.get_channel(channel_id)
                            if not channel or not isinstance(channel, discord.abc.Messageable):
                                continue

                            # FIXME: 14 day limit
                            messages = [
                                discord.Object(id=delete_msg)
                                for delete_msg in set(messages_to_delete[channel_id])
                            ]
                            message_chunks = discord.utils.as_chunks(messages, 100)

                            for chunk in message_chunks:
                                await channel.delete_messages(
                                    messages=chunk,
                                    reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                                )
                    elif action.action_type == AutomodActionType.ADD_ROLE:
                        await message.author.add_roles(
                            *(discord.Object(id=role_id) for role_id in set(action.role_ids)),
                            reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                            atomic=False,
                        )
                    elif action.action_type == AutomodActionType.REMOVE_ROLE:
                        await message.author.remove_roles(
                            *(discord.Object(id=role_id) for role_id in set(action.role_ids)),
                            reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                            atomic=False,
                        )
                    elif action.action_type == AutomodActionType.TOGGLE_ROLE:
                        roles_to_add: list[discord.Object] = []
                        roles_to_remove: list[discord.Object] = []
                        roles_to_process = set(action.role_ids)
                        user_roles = [role.id for role in message.author.roles[:1]]

                        for role in roles_to_process:
                            if role in user_roles:
                                roles_to_remove.append(discord.Object(id=role))
                            else:
                                roles_to_add.append(discord.Object(id=role))

                        await message.author.add_roles(
                            *roles_to_add,
                            reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                            atomic=False,
                        )
                        await message.author.remove_roles(
                            *roles_to_remove,
                            reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                            atomic=False,
                        )
                    elif action.action_type == AutomodActionType.SEND_MESSAGE:
                        embed = None
                        if action.message_embed:
                            embed = discord.Embed(
                                description=action.message_content,
                                colour=discord.Colour.from_str(action.embed_colour)
                                if action.embed_colour
                                else discord.Colour.light_grey(),
                            ).set_author(
                                name="Titanium Automod", icon_url=self.bot.user.display_avatar.url
                            )

                        send_kwargs: dict[str, Any] = (
                            {"embed": embed}
                            if action.message_embed and embed
                            else {
                                "content": action.message_content,
                                "allowed_mentions": discord.AllowedMentions.none(),
                            }
                        )

                        if action.message_reply:
                            await message.reply(**send_kwargs)
                        else:
                            await message.channel.send(**send_kwargs)

            if embeds:
                embed_chunks = discord.utils.as_chunks(embeds, 10)
                for chunk in embed_chunks:
                    await message.channel.send(
                        embeds=chunk, allowed_mentions=discord.AllowedMentions.none(), *del_kwargs
                    )

            if triggered_rules:
                self.logger.debug(
                    f"Logging {len(triggered_rules)} automod triggers to guild logger"
                )
                guild_logger = GuildLogger(self.bot, message.guild)

                await guild_logger.titanium_automod_trigger(
                    rules=triggered_rules,
                    actions=processed_actions,
                    message=message,
                )

            self.logger.debug(f"Processed message from {message.author}: {message.id}")
        except Exception as e:
            await log_error(
                bot=self.bot,
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

        if not hasattr(payload.data, "content") or payload.data.get("content") is None:
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
