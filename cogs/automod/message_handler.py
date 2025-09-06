import asyncio
import logging
import re
import traceback
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from lib.cases.case_manager import GuildModCaseManager
from lib.classes.automod_message import AutomodMessage
from lib.embeds.dm_notifs import banned_dm, kicked_dm, muted_dm, warned_dm
from lib.embeds.mod_actions import (
    banned,
    forbidden,
    http_exception,
    kicked,
    muted,
    warned,
)
from lib.helpers.send_dm import send_dm
from lib.sql import AutomodAction, AutomodRule, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class AutomodMonitorCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
        self.new_message_queue: asyncio.Queue[discord.Message] = asyncio.Queue()
        self.new_message_queue_task = self.bot.loop.create_task(self.queue_worker())

    def cog_unload(self) -> None:
        self.new_message_queue.shutdown(immediate=True)

    async def queue_worker(self):
        while True:
            try:
                message = await self.new_message_queue.get()
            except asyncio.QueueShutDown:
                return

            try:
                await self.message_handler(message)
            except Exception:
                logging.error("Error processing message in automod")
                logging.error(traceback.format_exc())
            finally:
                self.new_message_queue.task_done()

    async def message_handler(self, message: discord.Message):
        # Check for server ID in config list
        if (
            not message.guild
            or message.guild.id not in self.bot.server_configs
            or not message.author
            or not isinstance(message.author, discord.Member)
            or not self.bot.user
        ):
            return

        triggers: list[AutomodRule] = []
        punishments: list[AutomodAction] = []

        if not self.bot.server_configs[message.guild.id].automod_enabled:
            return

        config = self.bot.server_configs[message.guild.id].automod_settings

        self.bot.automod_messages.setdefault(message.guild.id, {}).setdefault(
            message.author.id, []
        ).append(
            AutomodMessage(
                user_id=message.author.id,
                message_id=message.id,
                channel_id=message.channel.id,
                content=message.content,
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
                emoji_count=0,
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

        # Check for any spam detection
        if config.spam_detection:
            if len(config.spam_detection_rules) > 0:
                for rule in config.spam_detection_rules:
                    rule: AutomodRule

                    latest_timestamp = current_state[0].timestamp
                    filtered_messages = [
                        m
                        for m in current_state
                        if (latest_timestamp - m.timestamp).total_seconds()
                        < rule.duration
                    ]

                    if str(rule.antispam_type) == "message_spam":
                        count = len(list(filtered_messages))
                    elif str(rule.antispam_type) == "mention_spam":
                        count = sum(m.mention_count for m in filtered_messages)
                    elif str(rule.antispam_type) == "word_spam":
                        count = sum(m.word_count for m in filtered_messages)
                    elif str(rule.antispam_type) == "newline_spam":
                        count = sum(m.newline_count for m in filtered_messages)
                    elif str(rule.antispam_type) == "link_spam":
                        count = sum(m.link_count for m in filtered_messages)
                    elif str(rule.antispam_type) == "attachment_spam":
                        count = sum(m.attachment_count for m in filtered_messages)
                    elif str(rule.antispam_type) == "emoji_spam":
                        count = sum(m.emoji_count for m in filtered_messages)
                    else:
                        continue

                    if count > rule.threshold:
                        triggers.append(rule)
                        for action in rule.actions:
                            action: AutomodAction
                            punishments.append(action)

        # Malicious link check
        if config.malicious_link_detection:
            for rule in config.malicious_link_rules:
                rule: AutomodRule

                latest_timestamp = current_state[0].timestamp
                filtered_messages = [
                    m
                    for m in current_state
                    if (latest_timestamp - m.timestamp).total_seconds() < rule.duration
                ]
                spotted = 0

                for filtered_msg in filtered_messages:
                    if any(
                        link in filtered_msg.content
                        for link in self.bot.malicious_links
                    ):
                        spotted += 1

                if spotted > rule.threshold:
                    triggers.append(rule)
                    for action in rule.actions:
                        action: AutomodAction
                        punishments.append(action)

        # Phishing link check
        if config.phishing_link_detection:
            for rule in config.phishing_link_rules:
                rule: AutomodRule

                latest_timestamp = current_state[0].timestamp
                filtered_messages = [
                    m
                    for m in current_state
                    if (latest_timestamp - m.timestamp).total_seconds() < rule.duration
                ]
                spotted = 0

                for filtered_msg in filtered_messages:
                    if any(
                        f"http://{link}" in filtered_msg.content
                        for link in self.bot.phishing_links
                    ) or any(
                        f"https://{link}" in filtered_msg.content
                        for link in self.bot.phishing_links
                    ):
                        spotted += 1

                if spotted > rule.threshold:
                    triggers.append(rule)
                    for action in rule.actions:
                        action: AutomodAction
                        punishments.append(action)

        # Bad word detection
        if config.badword_detection:
            for rule in config.badword_detection_rules:
                rule: AutomodRule

                latest_timestamp = current_state[0].timestamp
                filtered_messages = [
                    m
                    for m in current_state
                    if (latest_timestamp - m.timestamp).total_seconds() < rule.duration
                ]
                spotted = 0

                for filtered_msg in filtered_messages:
                    content_list = filtered_msg.content.lower().split()

                    if any(word in content_list for word in rule.words):
                        spotted += 1

                if spotted >= rule.threshold:
                    triggers.append(rule)
                    for action in rule.actions:
                        action: AutomodAction
                        punishments.append(action)

        # Get list of punishment types
        punishment_types = list(set(action.action_type for action in punishments))
        embeds: list[discord.Embed] = []

        async with get_session() as session:
            manager = GuildModCaseManager(message.guild, session)

            for punishment in punishments:
                if str(punishment.action_type) == "delete":
                    await message.delete()
                elif str(punishment.action_type) == "warn":
                    case = await manager.create_case(
                        type="warn",
                        user_id=message.author.id,
                        creator_user_id=self.bot.user.id,
                        reason=f"Automod: {punishment.reason}",
                    )

                    dm_success, dm_error = await send_dm(
                        embed=warned_dm(self.bot, message, case),
                        user=message.author,
                        source_guild=message.guild,
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
                elif str(punishment.action_type) == "mute":
                    # Check if user is already timed out
                    if message.author.is_timed_out():
                        continue

                    # Time out user
                    try:
                        await message.author.timeout(
                            timedelta(seconds=punishment.duration),
                            reason=f"Automod: {punishment.reason}",
                        )

                        case = await manager.create_case(
                            type="mute",
                            user_id=message.author.id,
                            creator_user_id=self.bot.user.id,
                            reason=f"Automod: {punishment.reason}",
                            duration=timedelta(seconds=punishment.duration),
                        )

                        dm_success, dm_error = await send_dm(
                            embed=muted_dm(self.bot, message, case),
                            user=message.author,
                            source_guild=message.guild,
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
                    except discord.Forbidden:
                        embeds.append(forbidden(self.bot, message.author))
                    except discord.HTTPException:
                        embeds.append(http_exception(self.bot, message.author))

                elif (
                    str(punishment.action_type) == "kick"
                    and "ban" not in punishment_types
                ):
                    # Kick user
                    try:
                        await message.author.kick(
                            reason=f"Automod: {punishment.reason}",
                        )

                        case = await manager.create_case(
                            type="kick",
                            user_id=message.author.id,
                            creator_user_id=self.bot.user.id,
                            reason=f"Automod: {punishment.reason}",
                        )

                        dm_success, dm_error = await send_dm(
                            embed=kicked_dm(self.bot, message, case),
                            user=message.author,
                            source_guild=message.guild,
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
                    except discord.Forbidden:
                        embeds.append(forbidden(self.bot, message.author))
                    except discord.HTTPException:
                        embeds.append(http_exception(self.bot, message.author))
                elif str(punishment.action_type) == "ban":
                    # Ban user
                    try:
                        await message.author.ban(
                            reason=f"Automod: {punishment.reason}",
                        )

                        case = await manager.create_case(
                            type="ban",
                            user_id=message.author.id,
                            creator_user_id=self.bot.user.id,
                            reason=f"Automod: {punishment.reason}",
                        )

                        dm_success, dm_error = await send_dm(
                            embed=banned_dm(self.bot, message, case),
                            user=message.author,
                            source_guild=message.guild,
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
                    except discord.Forbidden:
                        embeds.append(forbidden(self.bot, message.author))
                    except discord.HTTPException:
                        embeds.append(http_exception(self.bot, message.author))

                if embeds:
                    await message.channel.send(embeds=embeds)

    # Listen for messages
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            await self.new_message_queue.put(message)
        except asyncio.QueueShutDown:
            return


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(AutomodMonitorCog(bot))
