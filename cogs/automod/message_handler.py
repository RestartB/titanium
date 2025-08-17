import re
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from lib.classes.automod_message import AutomodMessage
from lib.sql import AutomodAction, AutomodRule

if TYPE_CHECKING:
    from main import TitaniumBot


class AutomodMonitorCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    # Listen for messages
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Check for server ID in config list
        if not message.guild or message.guild.id not in self.bot.server_automod_configs:
            return

        triggers: list[AutomodRule] = []
        punishments: list[tuple[str, int | None]] = []

        config = self.bot.server_automod_configs[message.guild.id]

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

        current_state = self.bot.automod_messages[message.guild.id][message.author.id]
        current_state.reverse()

        # Check for any spam detection
        if config.spam_detection:
            if len(config.spam_detection_rules) > 0:
                latest_timestamp = current_state[0].timestamp
                filtered_messages = filter(
                    lambda m: (latest_timestamp - m.timestamp).total_seconds()
                    < rule.duration,
                    current_state,
                )

                for rule in config.spam_detection_rules:
                    rule: AutomodRule

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
                            punishments.append(
                                [
                                    action.action_type,
                                    action.duration if action.duration else None,
                                ]
                            )

        # Malicious link check
        if config.malicious_link_detection:
            for rule in config.malicious_link_rules:
                rule: AutomodRule

                latest_timestamp = current_state[0].timestamp
                filtered_messages = filter(
                    lambda m: (latest_timestamp - m.timestamp).total_seconds()
                    < rule.duration,
                    current_state,
                )
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
                        punishments.append(
                            [
                                action.action_type,
                                action.duration if action.duration else None,
                            ]
                        )

        # Phishing link check
        if config.phishing_link_detection:
            for rule in config.phishing_link_rules:
                rule: AutomodRule

                latest_timestamp = current_state[0].timestamp
                filtered_messages = filter(
                    lambda m: (latest_timestamp - m.timestamp).total_seconds()
                    < rule.duration,
                    current_state,
                )
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
                        punishments.append(
                            [
                                action.action_type,
                                action.duration if action.duration else None,
                            ]
                        )

        # Bad word detection
        if config.badword_detection:
            for rule in config.badword_detection_rules:
                rule: AutomodRule

                latest_timestamp = current_state[0].timestamp
                filtered_messages = filter(
                    lambda m: (latest_timestamp - m.timestamp).total_seconds()
                    < rule.duration,
                    current_state,
                )
                spotted = 0

                for filtered_msg in filtered_messages:
                    content_list = filtered_msg.content.lower().split()
                    for rule in config.badword_detection_rules:
                        rule: AutomodRule

                        if any(word in content_list for word in rule.words):
                            spotted += 1

                if spotted > rule.threshold:
                    triggers.append(rule)
                    for action in rule.actions:
                        action: AutomodAction
                        punishments.append(
                            [
                                action.action_type,
                                action.duration if action.duration else None,
                            ]
                        )


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(AutomodMonitorCog(bot))
