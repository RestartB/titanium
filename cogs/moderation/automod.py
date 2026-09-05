import logging
import re
import unicodedata
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

# TODO: this file has hit pylance's processing limit so adding new features will be much more difficult
# likely i will need to split the criteria / action parts into separate functions


class AutomodMonitorCog(commands.Cog):
    """Monitors new messages for automod triggers and creates cases/punishments"""

    DISCORD_DICE_ROLL_RE = re.compile(
        r"https?://(?:www\.|canary\.|ptb\.)?discord(?:app)?\.com/channels/"
        r"\d+/\d+(?:/\d+)?/roll-dice/[^\s<>()]+",
        flags=re.IGNORECASE,
    )

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("automod")

    def normalise_automod_text(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        return "".join(char for char in text if unicodedata.category(char) != "Cf")

    async def add_reaction(self, message: discord.Message, reaction: str) -> None:
        if emoji.is_emoji(reaction):
            await message.add_reaction(reaction)
            return

        custom_emoji = discord.PartialEmoji(name="_", id=int(reaction))
        await message.add_reaction(custom_emoji)

    async def handle_message(
        self, message: discord.Message, event_type: Literal["new", "edit"] = "new"
    ):
        self.logger.debug(f"Processing message from {message.author}: {message.id}")
        config = await self.bot.fetch_guild_config(message.guild.id) if message.guild else None

        # support forwarded messages
        content_to_check = message.content
        if message.message_snapshots:
            content_to_check = message.message_snapshots[0].content

        # normalise to remove unicode bypasses
        normalised_content_to_check = self.normalise_automod_text(content_to_check)

        try:
            # Check for server ID in config list
            if (
                not message.guild
                or not config
                or not config.moderation_settings
                or not config.automod_settings
                or not message.author
                or not isinstance(message.author, discord.Member)
                or not isinstance(message.channel, discord.abc.GuildChannel)
                or not self.bot.user
                or message.author.id == self.bot.user.id
                or message.author.guild_permissions.administrator
            ):
                self.logger.debug("Automod initial checks failed, skipping message")
                return

            if not config.automod_enabled or not config.moderation_enabled:
                self.logger.debug("Automod is disabled, skipping message")
                return

            automod_config = config.automod_settings

            if message.channel.id in automod_config.global_ignored_channels:
                self.logger.debug("Message in ignored channel, skipping message")
                return

            if any(role.id in automod_config.global_ignored_roles for role in message.author.roles):
                self.logger.debug("Message sent by ignored role, skipping message")
                return

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
            messages_to_delete: dict[int, list[AutomodMessage]] = {}

            rules = automod_config.rules.copy()
            rules.sort(key=lambda r: r.order)

            self.logger.debug(f"Will evaluate {len(rules)} rules")
            for rule in rules:
                self.logger.debug(f"({rule.id}) Evaluating...")

                if not rule.enabled:
                    self.logger.debug(f"({rule.id}) Rule disabled")
                    continue

                if not rule.evaluate_edits and event_type == "edit":
                    self.logger.debug(f"({rule.id}) Not evaluating edit")
                    continue

                criterion_matched = 0
                for criteria in rule.criteria:
                    type = AutomodCriteriaType(criteria.type)
                    self.logger.debug(type)

                    if type.value.endswith("_spam"):
                        duration = criteria.duration
                        threshold = criteria.threshold

                        # check required values for spam filters are present
                        if not current_state or duration is None or threshold is None:
                            self.logger.warning(
                                f"({criteria.id}) Required values for spam filtering missing"
                            )
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

                        if type == AutomodCriteriaType.MESSAGE_SPAM:
                            self.logger.debug(len(filtered_messages))
                            self.logger.debug(threshold)

                            if len(filtered_messages) >= threshold:
                                criterion_matched += 1

                                for past_message in filtered_messages:
                                    messages_to_delete.setdefault(
                                        past_message.channel_id, []
                                    ).append(past_message)
                        else:
                            # fmt: off
                            if type == AutomodCriteriaType.MENTION_SPAM:
                                count = sum(
                                    [
                                        past_message.mention_count
                                        for past_message in filtered_messages
                                    ]
                                )
                            elif type == AutomodCriteriaType.WORD_SPAM:
                                count = sum(
                                    [
                                        past_message.word_count
                                        for past_message in filtered_messages
                                    ]
                                )
                            elif type == AutomodCriteriaType.NEWLINE_SPAM:
                                count = sum(
                                    [
                                        past_message.newline_count
                                        for past_message in filtered_messages
                                    ]
                                )
                            elif type == AutomodCriteriaType.LINK_SPAM:
                                count = sum(
                                    [
                                        past_message.link_count
                                        for past_message in filtered_messages
                                        ]
                                )
                            elif type == AutomodCriteriaType.ATTACHMENT_SPAM:
                                count = sum(
                                    [
                                        past_message.attachment_count
                                        for past_message in filtered_messages
                                    ]
                                )
                            elif type == AutomodCriteriaType.EMOJI_SPAM:
                                count = sum(
                                    [
                                        past_message.emoji_count
                                        for past_message in filtered_messages
                                    ]
                                )
                            else:
                                self.logger.warning(
                                    f"({criteria.id}) Unknown spam rule type: {type}"
                                )
                                continue
                            # fmt: on

                            if count >= threshold:
                                criterion_matched += 1

                                for past_message in filtered_messages:
                                    messages_to_delete.setdefault(
                                        past_message.channel_id, []
                                    ).append(past_message)

                        continue

                    criteria_met = False

                    if type == AutomodCriteriaType.WORD_LIST:
                        words_matched = 0
                        for word in criteria.words:
                            normalised_word = self.normalise_automod_text(word)
                            pattern = r"\b" + re.escape(normalised_word) + r"\b"
                            if not criteria.match_whole_word:
                                pattern = pattern.lstrip(r"\b").rstrip(r"\b")

                            matches = re.findall(
                                pattern,
                                normalised_content_to_check,
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
                    elif type == AutomodCriteriaType.MALICIOUS_LINK:
                        for link in self.bot.malicious_links:
                            if link in content_to_check:
                                criteria_met = True
                                break
                    elif type == AutomodCriteriaType.PHISHING_LINK:
                        for link in self.bot.phishing_links:
                            if link in content_to_check:
                                criteria_met = True
                                break
                    elif type == AutomodCriteriaType.NSFW_LINK:
                        for link in self.bot.nsfw_links:
                            if link in content_to_check:
                                criteria_met = True
                                break
                    elif type == AutomodCriteriaType.DISCORD_DICE_ROLL:
                        criteria_met = bool(
                            self.DISCORD_DICE_ROLL_RE.search(normalised_content_to_check)
                        )
                    else:
                        self.logger.warning(f"({criteria.id}) Unknown rule type: {type}")
                        continue

                    if criteria_met:
                        criterion_matched += 1
                        messages_to_delete.setdefault(message.channel.id, []).append(
                            current_state[0]
                        )

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
                not in [AutomodActionType.MUTE, AutomodActionType.KICK, AutomodActionType.BAN]
            ]

            kicks = [
                action for action in triggered_actions if action.type == AutomodActionType.KICK
            ]
            if kicks:
                processed_actions.append(kicks[0])

            mutes = [
                action for action in triggered_actions if action.type == AutomodActionType.MUTE
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

            bans = [action for action in triggered_actions if action.type == AutomodActionType.BAN]
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
            successful_actions: list[AutomodAction] = []
            failed_actions: dict[AutomodAction, str] = {}

            async with get_session() as session:
                manager = GuildModCaseManager(self.bot, message.guild, session)

                self.logger.debug(f"Will process {len(processed_actions)} actions")

                for action in processed_actions:
                    self.logger.debug(f"({action.id}) Processing {action.type} action...")

                    try:
                        if action.type == AutomodActionType.WARN:
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
                        elif action.type == AutomodActionType.MUTE:
                            # fmt: off
                            if message.author.top_role >= message.guild.me.top_role:
                                failed_actions[action] = "No permission to mute this user (Titanium's role not higher than user's top role)"
                                embeds.append(mod_embeds.titanium_not_allowed(self.bot, user=message.author, action="time out"))
                                continue
                            elif not message.channel.permissions_for(message.guild.me).moderate_members:
                                failed_actions[action] = "No mute permissions"
                                embeds.append(mod_embeds.forbidden(self.bot, action="time out members"))
                                continue
                            # fmt: on

                            await message.author.timeout(
                                (
                                    timedelta(seconds=action.duration)
                                    if action.duration and action.duration <= 2419200
                                    else timedelta(seconds=2419200)
                                ),
                                reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                            )

                            case, dm_success, dm_error = await manager.create_case(
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
                        elif action.type == AutomodActionType.KICK:
                            # fmt: off
                            if message.author.top_role >= message.guild.me.top_role:
                                failed_actions[action] = "No permission to kick this user (Titanium's role not higher than user's top role)"
                                embeds.append(mod_embeds.titanium_not_allowed(self.bot, user=message.author, action="kick"))
                                continue
                            elif not message.channel.permissions_for(message.guild.me).kick_members:
                                failed_actions[action] = "No kick permissions"
                                embeds.append(mod_embeds.forbidden(self.bot, action="kick members"))
                                continue
                            # fmt: on

                            case, dm_success, dm_error = await manager.create_case(
                                action=CaseType.KICK,
                                user=message.author,
                                creator_user=self.bot.user,
                                reason=action.reason,
                                source=CaseSource.AUTOMOD,
                            )

                            try:
                                await message.author.kick(
                                    reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                                )
                                embeds.append(
                                    mod_embeds.kicked(
                                        bot=self.bot,
                                        user=message.author,
                                        creator=self.bot.user,
                                        case=case,
                                        dm_success=dm_success,
                                        dm_error=dm_error,
                                    )
                                )
                            except Exception:
                                await manager.delete_case(case.id, raise_not_found=False)
                                raise
                        elif action.type == AutomodActionType.BAN:
                            # fmt: off
                            if message.author.top_role >= message.guild.me.top_role:
                                failed_actions[action] = "No permission to ban this user (Titanium's role not higher than user's top role)"
                                embeds.append(mod_embeds.titanium_not_allowed(self.bot, user=message.author, action="ban"))
                                continue
                            elif not message.channel.permissions_for(message.guild.me).ban_members:
                                failed_actions[action] = "No ban permissions"
                                embeds.append(mod_embeds.forbidden(self.bot, action="ban members"))
                                continue
                            # fmt: on

                            case, dm_success, dm_error = await manager.create_case(
                                action=CaseType.BAN,
                                user=message.author,
                                creator_user=self.bot.user,
                                reason=action.reason,
                                duration=timedelta(seconds=action.duration)
                                if action.duration
                                else None,
                                source=CaseSource.AUTOMOD,
                            )

                            try:
                                await message.author.ban(
                                    delete_message_seconds=config.moderation_settings.ban_days
                                    * 86400,
                                    reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
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
                            except Exception:
                                await manager.delete_case(case.id, raise_not_found=False)
                                raise
                        elif action.type == AutomodActionType.DELETE:
                            # fmt: off
                            if not message.channel.permissions_for(message.guild.me).manage_messages:
                                failed_actions[action] = "No delete message permissions in the message channel"
                                embeds.append(mod_embeds.forbidden(self.bot, action="delete messages in this channel"))
                                continue
                            # fmt: on

                            for channel_id, value in messages_to_delete.items():
                                channel = message.guild.get_channel(channel_id)
                                if not channel or not isinstance(channel, discord.abc.Messageable):
                                    continue

                                unique_messages = {
                                    delete_msg.message_id: delete_msg for delete_msg in value
                                }
                                messages = [
                                    discord.Object(id=delete_msg.message_id)
                                    for delete_msg in unique_messages.values()
                                    if not delete_msg.deleted
                                    and discord.utils.utcnow() - delete_msg.timestamp
                                    <= timedelta(days=14)
                                ]
                                message_chunks = discord.utils.as_chunks(messages, 100)

                                for chunk in message_chunks:
                                    await channel.delete_messages(
                                        messages=chunk,
                                        reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                                    )
                        elif action.type == AutomodActionType.ADD_ROLE:
                            # fmt: off
                            if message.author.top_role >= message.guild.me.top_role:
                                failed_actions[action] = "No permission to manage this user (Titanium's role below user's top role)"
                                embeds.append(mod_embeds.titanium_not_allowed(self.bot, user=message.author, action="manage roles for"))
                                continue
                            elif not message.channel.permissions_for(message.guild.me).manage_roles:
                                failed_actions[action] = "No manage role permissions"
                                embeds.append(mod_embeds.forbidden(self.bot, action="manage roles"))
                                continue
                            # fmt: on

                            roles: list[discord.Role] = []
                            for role_id in set(action.role_ids):
                                role = message.guild.get_role(role_id)
                                if role and message.guild.me.top_role > role:
                                    roles.append(role)

                            await message.author.add_roles(
                                *roles,
                                reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                                atomic=False,
                            )
                        elif action.type == AutomodActionType.REMOVE_ROLE:
                            # fmt: off
                            if message.author.top_role >= message.guild.me.top_role:
                                failed_actions[action] = "No permission to manage this user (Titanium's role below user's top role)"
                                embeds.append(mod_embeds.titanium_not_allowed(self.bot, user=message.author, action="manage roles for"))
                                continue
                            elif not message.channel.permissions_for(message.guild.me).manage_roles:
                                failed_actions[action] = "No manage role permissions"
                                embeds.append(mod_embeds.forbidden(self.bot, action="manage roles"))
                                continue
                            # fmt: on

                            roles: list[discord.Role] = []
                            for role_id in set(action.role_ids):
                                role = message.guild.get_role(role_id)
                                if role and message.guild.me.top_role > role:
                                    roles.append(role)

                            await message.author.remove_roles(
                                *roles,
                                reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                                atomic=False,
                            )
                        elif action.type == AutomodActionType.TOGGLE_ROLE:
                            # fmt: off
                            if message.author.top_role >= message.guild.me.top_role:
                                failed_actions[action] = "No permission to manage this user (Titanium's role below user's top role)"
                                embeds.append(mod_embeds.titanium_not_allowed(self.bot, user=message.author, action="manage roles for"))
                                continue
                            elif not message.channel.permissions_for(message.guild.me).manage_roles:
                                failed_actions[action] = "No manage role permissions"
                                embeds.append(mod_embeds.forbidden(self.bot, action="manage roles"))
                                continue
                            # fmt: on

                            roles_to_add: list[discord.Role] = []
                            roles_to_remove: list[discord.Role] = []

                            for role_id in set(action.role_ids):
                                role = message.guild.get_role(role_id)
                                if not role or message.guild.me.top_role <= role:
                                    continue

                                if role in message.author.roles:
                                    roles_to_remove.append(role)
                                else:
                                    roles_to_add.append(role)

                            if roles_to_add:
                                await message.author.add_roles(
                                    *roles_to_add,
                                    reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                                    atomic=False,
                                )

                            if roles_to_remove:
                                await message.author.remove_roles(
                                    *roles_to_remove,
                                    reason=f"Automod: {action.reason if action.reason else 'No reason provided'}",
                                    atomic=False,
                                )
                        elif (
                            action.type == AutomodActionType.SEND_MESSAGE
                            and action.message_content
                            and not message.author.bot
                        ):
                            # fmt: off
                            if (
                                not message.channel.permissions_for(message.guild.me).view_channel
                                or not message.channel.permissions_for(
                                    message.guild.me
                                ).send_messages
                            ):
                                failed_actions[action] = "No send message permissions in the message channel"
                                embeds.append(mod_embeds.forbidden(self.bot, action=f"send messages in {message.channel.mention} (`#{message.channel.name}`, `{message.channel.id}`)"))
                                continue
                            # fmt: on

                            embed = None
                            if action.message_embed:
                                embed = discord.Embed(
                                    description=action.message_content,
                                    colour=discord.Colour.from_str(action.embed_colour)
                                    if action.embed_colour
                                    else discord.Colour.light_grey(),
                                ).set_author(
                                    name="Titanium Automod",
                                    icon_url=self.bot.user.display_avatar.url,
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
                                await message.channel.send(
                                    reference=message.to_reference(fail_if_not_exists=False),
                                    **send_kwargs,
                                )
                            else:
                                await message.channel.send(**send_kwargs)
                        elif action.type == AutomodActionType.REACTION:
                            if not action.reaction:
                                self.logger.debug(f"{action.id} No reaction provided")
                                continue

                            if not message.channel.permissions_for(message.guild.me).add_reactions:
                                failed_actions[action] = (
                                    "No add reaction permissions in the message channel"
                                )
                                continue

                            try:
                                await self.add_reaction(message, action.reaction)
                            except discord.NotFound:
                                failed_actions[action] = "Couldn't find target reaction emoji"
                            except discord.HTTPException:
                                failed_actions[action] = "Failed to add reaction to message"
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
                            guild_id=message.guild.id,
                            error=f"Titanium was not allowed to perform the {action.type.value} action against @{message.author.name} ({message.author.id})",
                            details=e.text,
                            exc=e,
                        )
                    except discord.HTTPException as e:
                        failed_actions[action] = "Unknown Discord error occurred"
                        await log_error(
                            bot=self.bot,
                            module="Automod",
                            guild_id=message.guild.id,
                            error=f"Unknown Discord error occurred while processing {action.type.value} against @{message.author.name} ({message.author.id})",
                            details=e.text,
                            exc=e,
                        )
                    except Exception as e:
                        failed_actions[action] = "Unexpected error occurred"
                        await log_error(
                            bot=self.bot,
                            module="Automod",
                            guild_id=message.guild.id,
                            error=f"Unexpected error occurred while processing {action.type.value} against @{message.author.name} ({message.author.id})",
                            exc=e,
                        )

                if embeds and not message.channel.permissions_for(message.guild.me).send_messages:
                    await log_error(
                        bot=self.bot,
                        module="Automod",
                        guild_id=message.guild.id,
                        error=f"Titanium did not have permissions to send automod outcome message in #{message.channel.name}` (`{message.channel.id}`)",
                    )
                elif embeds and automod_config.show_outcome_message:
                    try:
                        embed_chunks = discord.utils.as_chunks(embeds, 10)
                        for chunk in embed_chunks:
                            await message.channel.send(
                                embeds=chunk, allowed_mentions=discord.AllowedMentions.none()
                            )
                    except discord.Forbidden as e:
                        await log_error(
                            bot=self.bot,
                            module="Automod",
                            guild_id=message.guild.id,
                            error=f"Titanium was not allowed to send automod outcome message in #{message.channel.name}` (`{message.channel.id}`)",
                            details=e.text,
                            exc=e,
                        )
                    except discord.HTTPException as e:
                        await log_error(
                            bot=self.bot,
                            module="Automod",
                            guild_id=message.guild.id,
                            error=f"Unknown Discord error occurred while sending automod outcome message in #{message.channel.name}` (`{message.channel.id}`)",
                            details=e.text,
                            exc=e,
                        )
                    except Exception as e:
                        await log_error(
                            bot=self.bot,
                            module="Automod",
                            guild_id=message.guild.id,
                            error=f"Unexpected error occurred while sending automod outcome message in #{message.channel.name}` (`{message.channel.id}`)",
                            exc=e,
                        )

            if triggered_rules:
                self.logger.debug(
                    f"Logging {len(triggered_rules)} automod triggers to guild logger"
                )
                guild_logger = GuildLogger(self.bot, message.guild)

                await guild_logger.titanium_automod_trigger(
                    rules=triggered_rules,
                    successful_actions=successful_actions,
                    failed_actions=failed_actions,
                    message=message,
                )

            self.logger.debug(
                f"Finished processing message from {message.guild.id} ({message.author}, {message.author.id}) - {message.id}"
            )
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

        if "content" not in payload.data or payload.data.get("content") is None:
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

    # Listen for message delete
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        self.logger.debug(f"Received raw message delete event: {payload.message_id}")
        if not payload.cached_message:
            return

        if payload.guild_id not in self.bot.automod_messages:
            return

        if payload.cached_message.author.id not in self.bot.automod_messages[payload.guild_id]:
            return

        for i, message in enumerate(
            self.bot.automod_messages[payload.guild_id][payload.cached_message.author.id]
        ):
            if message.message_id != payload.message_id:
                continue

            self.bot.automod_messages[payload.guild_id][payload.cached_message.author.id][
                i
            ].deleted = True


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(AutomodMonitorCog(bot))
