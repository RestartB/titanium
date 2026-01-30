import asyncio
import logging
import uuid
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from lib.helpers.cache import get_or_fetch_message
from lib.helpers.log_error import log_error
from lib.sql.sql import FireboardMessage, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class FireboardCog(commands.Cog):
    """Server fireboard system"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.event_queue: asyncio.Queue[
            discord.RawReactionActionEvent
            | discord.RawMessageUpdateEvent
            | discord.RawMessageDeleteEvent
            | discord.Reaction
            | discord.Message
        ] = asyncio.Queue()
        self.event_queue_task = self.bot.loop.create_task(self.queue_worker())
        self.logger: logging.Logger = logging.getLogger("fireboard")

    def cog_unload(self) -> None:
        self.event_queue.shutdown(immediate=True)

    def _normalize_emoji(self, emoji: str) -> str:
        # Remove variation selector-16 (U+FE0F) which makes emojis render as colorful
        return emoji.replace("\ufe0f", "")

    def _get_emoji_identifier(self, emoji: discord.Emoji | discord.PartialEmoji | str) -> str:
        if isinstance(emoji, discord.Emoji):
            return str(emoji.id)
        elif isinstance(emoji, discord.PartialEmoji) and emoji.is_custom_emoji():
            return str(emoji.id)
        else:
            return self._normalize_emoji(str(emoji))

    def _fireboard_embed(
        self,
        message: discord.Message,
        failed_attachments: int = 0,
        footer: str | None = None,
    ) -> discord.Embed:
        """Creates a fireboard embed message"""
        embed = discord.Embed(
            description=message.content,
            colour=discord.Colour.random(),
            timestamp=message.created_at,
        )
        embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)

        if footer:
            embed.set_footer(text=footer)
        elif failed_attachments > 0:
            embed.set_footer(
                text=f"⚠️ Failed to download {failed_attachments} attachment"
                + ("s" if failed_attachments != 1 else "")
            )

        return embed

    async def queue_worker(self):
        self.logger.info("Fireboard event handler started.")
        while True:
            try:
                await self.bot.wait_until_ready()
                event = await self.event_queue.get()
                self.logger.debug(f"Processing event from queue: {type(event).__name__}")
            except asyncio.QueueShutDown:
                self.logger.info("Fireboard event handler shutting down.")
                return

            try:
                if isinstance(event, discord.RawReactionActionEvent):
                    await self._reaction_add_remove(event)
                elif isinstance(event, discord.RawMessageUpdateEvent):
                    await self.message_edit_handler(event)
                elif isinstance(event, discord.RawMessageDeleteEvent):
                    await self.message_delete_handler(event)
                elif isinstance(event, discord.Reaction):
                    await self.reaction_emoji_clear_handler(event)
                elif isinstance(event, discord.Message):
                    await self.reaction_clear_handler(event)

                self.logger.debug(f"Successfully processed event: {type(event).__name__}")
            except Exception as e:
                if isinstance(
                    event,
                    (
                        discord.RawReactionActionEvent,
                        discord.RawMessageUpdateEvent,
                        discord.RawMessageDeleteEvent,
                    ),
                ):
                    guild_id = event.guild_id or 0
                    message_id = event.message_id
                    channel_id = event.channel_id
                elif isinstance(event, discord.Reaction):
                    guild_id = event.message.guild.id if event.message.guild else 0
                    message_id = event.message.id
                    channel_id = event.message.channel.id
                elif isinstance(event, discord.Message):
                    guild_id = event.guild.id if event.guild else 0
                    message_id = event.id
                    channel_id = event.channel.id

                await log_error(
                    bot=self.bot,
                    module="Fireboard",
                    guild_id=guild_id or None,
                    error="An unknown error occurred while processing a fireboard event",
                    details=f"Message ID: {message_id or None}\nChannel ID: {channel_id or None}",
                    exc=e,
                )
            finally:
                self.event_queue.task_done()

    async def _calculate_reaction_count(
        self,
        message: discord.Message,
        emoji: discord.PartialEmoji,
        author: discord.User | discord.Member,
        ignore_self: bool,
        ignore_bots: bool,
    ) -> int:
        self.logger.debug(f"Calculating reaction count for message {message.id}, emoji: {emoji}")

        for reaction in message.reactions:
            if str(reaction.emoji) == str(emoji):
                # if both ignore options are disabled, we don't need to get each user
                if not ignore_self and not ignore_bots:
                    return reaction.count

                users = [user async for user in reaction.users()]
                break
        else:
            self.logger.debug("No matching reaction found on message")
            return 0

        amount = 0

        for user in users:
            if ignore_bots and user.bot:
                self.logger.debug(f"Ignoring bot user {user.id}")
                continue
            if ignore_self and user.id == author.id:
                self.logger.debug(f"Ignoring self-reaction from {user.id}")
                continue
            amount += 1

        self.logger.debug(f"Final reaction count: {amount}")
        return amount

    async def _reaction_add_remove(self, event: discord.RawReactionActionEvent):
        if not event.guild_id:
            self.logger.debug("Ignoring reaction in DM/Group channel")
            return

        self.logger.debug(
            f"Handling reaction add/remove. Reaction: {event.emoji}, User: {event.user_id}, Message id: {event.message_id}"
        )

        config = await self.bot.fetch_guild_config(event.guild_id)
        msg_channel = self.bot.get_channel(event.channel_id)

        if (
            self.bot.user is None
            or not config
            or not config.fireboard_enabled
            or len(config.fireboard_settings.fireboard_boards) == 0
            or event.user_id == self.bot.user.id
            or not msg_channel
            or isinstance(
                msg_channel,
                (
                    discord.ForumChannel,
                    discord.CategoryChannel,
                    discord.abc.PrivateChannel,
                ),
            )
        ):
            self.logger.debug("Ignoring reaction")
            return

        processed_boards: list[uuid.UUID] = []
        self.logger.debug(
            f"Processing {len(self.bot.fireboard_messages.get(event.guild_id, []))} existing fireboard messages"
        )

        source_msg = None
        source_msg_fetched = False

        # board messages should be ignored
        if event.message_id in list(
            fireboard_message.fireboard_message_id
            for fireboard_message in self.bot.fireboard_messages.get(event.guild_id, [])
        ):
            return

        for fireboard_message in list(self.bot.fireboard_messages.get(event.guild_id, [])):
            if fireboard_message.message_id == event.message_id:
                normalized_board_reaction = self._normalize_emoji(
                    fireboard_message.fireboard.reaction
                )
                reaction_identifier = self._get_emoji_identifier(event.emoji)

                if normalized_board_reaction != reaction_identifier:
                    self.logger.debug(
                        f"Skipping board {fireboard_message.fireboard.id}: reaction mismatch ({fireboard_message.fireboard.reaction} != {event.emoji})"
                    )
                    continue

                self.logger.debug(
                    f"Found existing fireboard entry for board {fireboard_message.fireboard.id}"
                )
                processed_boards.append(fireboard_message.fireboard.id)
                board_channel = self.bot.get_channel(fireboard_message.fireboard.channel_id)

                if board_channel is None or isinstance(
                    board_channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    self.logger.debug(
                        f"Channel {fireboard_message.fireboard.channel_id} not found or invalid type"
                    )
                    continue

                try:
                    board_msg = await get_or_fetch_message(
                        self.bot, board_channel, fireboard_message.fireboard_message_id
                    )

                    if board_msg is None:
                        self.logger.debug("Fireboard message not found, deleting record")
                        async with get_session() as session:
                            await session.delete(fireboard_message)

                        self.bot.fireboard_messages[event.guild_id].remove(fireboard_message)
                        continue

                    if source_msg is None and not source_msg_fetched:
                        source_msg = await get_or_fetch_message(
                            self.bot, msg_channel, event.message_id
                        )
                        source_msg_fetched = True

                    if source_msg is None or isinstance(
                        source_msg.channel, (discord.abc.PrivateChannel)
                    ):
                        self.logger.debug("Source message not found, deleting fireboard message")
                        await board_msg.delete()
                        continue

                    count = await self._calculate_reaction_count(
                        source_msg,
                        event.emoji,
                        source_msg.author,
                        fireboard_message.fireboard.ignore_self_reactions,
                        fireboard_message.fireboard.ignore_bots,
                    )

                    content = f"**{count} {event.emoji}** • {source_msg.author.mention} • {source_msg.channel.mention}"
                    self.logger.debug(
                        f"Count: {count}, Threshold: {fireboard_message.fireboard.threshold}"
                    )

                    if (
                        count >= fireboard_message.fireboard.threshold
                        and content != board_msg.content
                    ):
                        self.logger.debug("Updating fireboard message")
                        await board_msg.edit(
                            content=content,
                            embed=self._fireboard_embed(
                                source_msg,
                                footer=board_msg.embeds[0].footer.text
                                if board_msg.embeds
                                else None,
                            ),
                        )
                        continue
                    elif count < fireboard_message.fireboard.threshold:
                        self.logger.debug("Count below threshold, deleting fireboard message")
                        await board_msg.delete()
                        continue
                except discord.NotFound, discord.Forbidden:
                    self.logger.debug("Fireboard message not found or forbidden")
                    continue

        self.logger.debug(
            f"Checking {len(config.fireboard_settings.fireboard_boards)} boards for new entries"
        )

        source_msg = None
        source_msg_fetched = False

        for board in config.fireboard_settings.fireboard_boards:
            normalized_board_reaction = self._normalize_emoji(board.reaction)
            reaction_identifier = self._get_emoji_identifier(event.emoji)

            if board.id in processed_boards or normalized_board_reaction != reaction_identifier:
                self.logger.debug(
                    f"Skipping board {board.id}: already processed or wrong emoji ({board.reaction} != {event.emoji})"
                )
                continue

            self.logger.debug(f"Evaluating board {board.id} for new fireboard entry")
            if source_msg is None and not source_msg_fetched:
                source_msg = await get_or_fetch_message(self.bot, msg_channel, event.message_id)
                source_msg_fetched = True

            if source_msg is None or isinstance(source_msg.channel, (discord.abc.PrivateChannel)):
                self.logger.debug("Source message not found, skipping")
                continue

            count = await self._calculate_reaction_count(
                source_msg,
                event.emoji,
                source_msg.author,
                board.ignore_self_reactions,
                board.ignore_bots,
            )

            if (
                count >= board.threshold
                and msg_channel.id not in board.ignored_channels
                and (
                    any(role.id not in board.ignored_roles for role in source_msg.author.roles)
                    if isinstance(source_msg.author, discord.Member)
                    else True
                )
            ):
                self.logger.debug(f"Creating new fireboard entry on board {board.id}")
                content = f"**{count} {event.emoji}** • {source_msg.author.mention} • {msg_channel.mention}"
                board_channel = self.bot.get_channel(board.channel_id)

                if board_channel is None or isinstance(
                    board_channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    self.logger.debug(f"Board channel {board.channel_id} not found or invalid type")
                    return

                view = discord.ui.View()
                view.add_item(
                    discord.ui.Button(
                        label="Jump to Message",
                        url=source_msg.jump_url,
                        style=discord.ButtonStyle.url,
                    )
                )

                files = []
                failed = False

                for attempt in range(2):
                    for attachment in source_msg.attachments:
                        try:
                            files.append(await attachment.to_file())
                        except Exception as e:
                            if not failed:
                                failed = True
                                break

                            await log_error(
                                bot=self.bot,
                                module="Fireboard",
                                guild_id=event.guild_id,
                                error="Failed to download fireboard attachment",
                                details=f"Attachment name: {attachment.filename}\nMessage ID: {source_msg.id}\nChannel ID: {source_msg.channel.id}",
                                exc=e,
                            )

                    if not failed:
                        break

                    if attempt == 0:
                        self.logger.debug(
                            "Failed to download one or more attachments, retrying fetch of source message"
                        )

                        source_msg = await source_msg.channel.fetch_message(source_msg.id)
                        files = []

                new_message = await board_channel.send(
                    content=content,
                    embed=self._fireboard_embed(
                        source_msg, len(source_msg.attachments) - len(files)
                    ),
                    files=files,
                    view=view,
                )
                self.logger.debug(f"Created fireboard message {new_message.id}")

                async with get_session() as session:
                    fireboard_message = FireboardMessage(
                        guild_id=event.guild_id,
                        message_id=event.message_id,
                        fireboard_id=board.id,
                        fireboard_message_id=new_message.id,
                    )
                    session.add(fireboard_message)

                    await session.commit()
                    await session.refresh(fireboard_message, ["fireboard"])
                    session.expunge(fireboard_message)

                    self.logger.debug(
                        f"Saved fireboard message to database with ID {fireboard_message.id}"
                    )

                    self.bot.fireboard_messages.setdefault(event.guild_id, []).append(
                        fireboard_message
                    )
                    self.logger.debug("Added fireboard message to cache")

                if not board.send_notifications:
                    self.logger.debug("Board notifications disabled, skipping notification")
                    return

                notification_embed = discord.Embed(
                    description=f"🎉 Your message was featured in {board_channel.mention}!",
                    colour=discord.Colour.green(),
                    timestamp=discord.utils.utcnow(),
                )

                notification_view = discord.ui.View()
                notification_view.add_item(
                    discord.ui.Button(
                        label="View Board Message",
                        url=new_message.jump_url,
                        style=discord.ButtonStyle.url,
                    )
                )

                try:
                    await source_msg.reply(
                        embed=notification_embed,
                        view=notification_view,
                    )
                    self.logger.debug(f"Sent fireboard notification to user {source_msg.author.id}")
                except discord.Forbidden as e:
                    await log_error(
                        bot=self.bot,
                        module="Fireboard",
                        guild_id=event.guild_id,
                        error=f"Titanium was not allowed to send fireboard notification in #{source_msg.channel.name if not isinstance(source_msg.channel, (discord.PartialMessageable, discord.abc.PrivateChannel)) else 'Unknown'} ({source_msg.channel.id})",
                        details=str(e.text),
                        exc=e,
                    )
                except discord.HTTPException as e:
                    await log_error(
                        bot=self.bot,
                        module="Fireboard",
                        guild_id=event.guild_id,
                        error=f"Unknown Discord error while sending fireboard notification in #{source_msg.channel.name if not isinstance(source_msg.channel, (discord.PartialMessageable, discord.abc.PrivateChannel)) else 'Unknown'} ({source_msg.channel.id})",
                        details=str(e.text),
                        exc=e,
                    )

                return
            else:
                self.logger.debug(
                    f"Board {board.id} criteria not met: count={count}, threshold={board.threshold}, channel_ignored={source_msg.channel.id in board.ignored_channels}"
                )

    async def message_edit_handler(self, payload: discord.RawMessageUpdateEvent):
        if not payload.guild_id:
            self.logger.debug("Ignoring edit in DM/Group channel")
            return

        self.logger.debug(
            f"Handling message edit. Message id: {payload.message_id}, channel id: {payload.channel_id}, guild id: {payload.guild_id}"
        )

        config = await self.bot.fetch_guild_config(payload.guild_id) if payload.guild_id else None

        if (
            not config
            or not config.fireboard_enabled
            or len(config.fireboard_settings.fireboard_boards) == 0
        ):
            self.logger.debug("No fireboard boards found")
            return

        if isinstance(payload.message.channel, (discord.DMChannel, discord.GroupChannel)):
            self.logger.debug("Ignoring edit in DM/Group channel")
            return

        self.logger.debug(
            f"Checking {len(self.bot.fireboard_messages.get(payload.guild_id, []))} fireboard messages"
        )
        for fireboard_message in list(self.bot.fireboard_messages.get(payload.guild_id, [])):
            self.logger.debug(
                f"Checking for match: {fireboard_message.message_id} == {payload.message_id}"
            )
            if fireboard_message.message_id == payload.message_id:
                self.logger.debug("Found matching message")
                channel = self.bot.get_channel(fireboard_message.fireboard.channel_id)

                if channel is None or isinstance(
                    channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    self.logger.debug("Edit channel not found")
                    continue

                try:
                    board_msg = await get_or_fetch_message(
                        self.bot, channel, fireboard_message.fireboard_message_id
                    )

                    if board_msg is None:
                        self.logger.debug("Edit message not found, deleting record")

                        async with get_session() as session:
                            await session.delete(fireboard_message)

                        self.bot.fireboard_messages[payload.guild_id].remove(fireboard_message)
                        continue

                    self.logger.debug(
                        f"Fetched fireboard message {fireboard_message.fireboard_message_id} for editing"
                    )
                    await board_msg.edit(
                        embed=self._fireboard_embed(
                            payload.message,
                            footer=board_msg.embeds[0].footer.text if board_msg.embeds else None,
                        ),
                        attachments=payload.message.attachments,
                    )

                    self.logger.debug("Edited message")

                except discord.NotFound:
                    self.logger.debug("Edit message not found, deleting record")

                    async with get_session() as session:
                        await session.delete(fireboard_message)

                    self.bot.fireboard_messages[payload.guild_id].remove(fireboard_message)
                    continue
                except Exception as e:
                    await log_error(
                        bot=self.bot,
                        module="Fireboard",
                        guild_id=payload.guild_id,
                        error="An unknown error occurred while processing a fireboard message edit",
                        details=f"Message ID: {payload.message_id}",
                        exc=e,
                    )
                    continue

        self.logger.debug("Done")

    async def message_delete_handler(self, payload: discord.RawMessageDeleteEvent):
        if not payload.guild_id:
            self.logger.debug("Ignoring delete in DM/Group channel")
            return

        self.logger.debug(
            f"Handling message delete. Message id: {payload.message_id}, channel id: {payload.channel_id}, guild id: {payload.guild_id}"
        )

        config = await self.bot.fetch_guild_config(payload.guild_id)

        if (
            not config
            or not config.fireboard_enabled
            or len(config.fireboard_settings.fireboard_boards) == 0
        ):
            self.logger.debug("No fireboard boards found")
            return

        self.logger.debug(
            f"Checking {len(self.bot.fireboard_messages.get(payload.guild_id, []))} fireboard messages"
        )
        for fireboard_message in list(self.bot.fireboard_messages.get(payload.guild_id, [])):
            if fireboard_message.message_id == payload.message_id:
                self.logger.debug(
                    f"Found matching fireboard message {fireboard_message.fireboard_message_id}"
                )
                channel = self.bot.get_channel(fireboard_message.fireboard.channel_id)

                if channel is None or isinstance(
                    channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    self.logger.debug(
                        f"Channel {fireboard_message.fireboard.channel_id} not found or invalid type"
                    )
                    continue

                try:
                    board_msg = await get_or_fetch_message(
                        self.bot, channel, fireboard_message.fireboard_message_id
                    )
                    if board_msg is None:
                        self.logger.debug("Delete message not found, deleting record")
                        async with get_session() as session:
                            await session.delete(fireboard_message)

                        self.bot.fireboard_messages[payload.guild_id].remove(fireboard_message)
                        continue

                    self.logger.debug(
                        f"Deleting fireboard message {fireboard_message.fireboard_message_id}"
                    )
                    await board_msg.delete()
                except discord.NotFound:
                    self.logger.debug("Delete message not found, deleting record")
                    async with get_session() as session:
                        await session.delete(fireboard_message)

                    self.bot.fireboard_messages[payload.guild_id].remove(fireboard_message)
                    continue
                except Exception as e:
                    await log_error(
                        bot=self.bot,
                        module="Fireboard",
                        guild_id=fireboard_message.guild_id,
                        error="An unknown error occurred while processing a fireboard message deletion",
                        details=f"Message ID: {fireboard_message.id}",
                        exc=e,
                    )
                    continue
            elif fireboard_message.fireboard_message_id == payload.message_id:
                self.logger.debug(
                    f"Fireboard board message {fireboard_message.fireboard_message_id} deleted"
                )

                async with get_session() as session:
                    await session.delete(fireboard_message)

                self.bot.fireboard_messages[payload.guild_id].remove(fireboard_message)
                self.logger.debug("Removed from cache")

    async def reaction_clear_handler(self, message: discord.Message):
        if not message.guild:
            self.logger.debug("Ignoring reaction clear in DM/Group channel")
            return

        self.logger.debug(
            f"Handling reaction clear. Message id: {message.id}, channel id: {message.channel.id}, guild id: {message.guild.id if message.guild else 'DM'}"
        )

        config = await self.bot.fetch_guild_config(message.guild.id)

        if (
            not config
            or not config.fireboard_enabled
            or len(config.fireboard_settings.fireboard_boards) == 0
        ):
            self.logger.debug("No fireboard boards found")
            return

        self.logger.debug(
            f"Checking {len(self.bot.fireboard_messages.get(message.guild.id, []))} fireboard messages"
        )
        for fireboard_message in list(self.bot.fireboard_messages.get(message.guild.id, [])):
            if fireboard_message.message_id == message.id:
                self.logger.debug(
                    f"Found matching fireboard message {fireboard_message.fireboard_message_id}"
                )
                channel = self.bot.get_channel(fireboard_message.fireboard.channel_id)

                if channel is None or isinstance(
                    channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    self.logger.debug(
                        f"Channel {fireboard_message.fireboard.channel_id} not found or invalid type"
                    )
                    continue

                try:
                    board_msg = await get_or_fetch_message(
                        self.bot, channel, fireboard_message.fireboard_message_id
                    )
                    if board_msg is None:
                        self.logger.debug("Delete message not found, deleting record")
                        async with get_session() as session:
                            await session.delete(fireboard_message)

                        self.bot.fireboard_messages[message.guild.id].remove(fireboard_message)
                        continue

                    self.logger.debug(
                        f"Deleting fireboard message {fireboard_message.fireboard_message_id}"
                    )
                    await board_msg.delete()
                except discord.NotFound:
                    self.logger.debug("Delete message not found, deleting record")
                    async with get_session() as session:
                        await session.delete(fireboard_message)

                    self.bot.fireboard_messages[message.guild.id].remove(fireboard_message)
                except Exception as e:
                    await log_error(
                        bot=self.bot,
                        module="Fireboard",
                        guild_id=message.guild.id,
                        error="An unknown error occurred while processing a fireboard message deletion",
                        details=f"Message ID: {message.id}",
                        exc=e,
                    )
                    continue

    async def reaction_emoji_clear_handler(self, reaction: discord.Reaction):
        if not reaction.message.guild:
            self.logger.debug("Ignoring reaction emoji clear in DM/Group channel")
            return

        self.logger.debug(
            f"Handling reaction emoji clear. Message id: {reaction.message.id}, channel id: {reaction.message.channel.id}, guild id: {reaction.message.guild.id if reaction.message.guild else 'DM'}"
        )

        config = await self.bot.fetch_guild_config(reaction.message.guild.id)

        if (
            not config
            or not config.fireboard_enabled
            or len(config.fireboard_settings.fireboard_boards) == 0
        ):
            self.logger.debug("No fireboard boards found")
            return

        self.logger.debug(
            f"Checking {len(self.bot.fireboard_messages.get(reaction.message.guild.id, []))} fireboard messages"
        )
        for fireboard_message in list(
            self.bot.fireboard_messages.get(reaction.message.guild.id, [])
        ):
            normalized_board_reaction = self._normalize_emoji(fireboard_message.fireboard.reaction)
            reaction_identifier = self._get_emoji_identifier(reaction.emoji)

            if (
                fireboard_message.message_id == reaction.message.id
                and normalized_board_reaction == reaction_identifier
            ):
                self.logger.debug(
                    f"Found matching fireboard message {fireboard_message.fireboard_message_id} for emoji {reaction.emoji}"
                )
                channel = self.bot.get_channel(fireboard_message.fireboard.channel_id)

                if channel is None or isinstance(
                    channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    self.logger.debug(
                        f"Channel {fireboard_message.fireboard.channel_id} not found or invalid type"
                    )
                    continue

                try:
                    board_msg = await get_or_fetch_message(
                        self.bot, channel, fireboard_message.fireboard_message_id
                    )
                    if board_msg is None:
                        self.logger.debug("Delete message not found, deleting record")
                        async with get_session() as session:
                            await session.delete(fireboard_message)

                        self.bot.fireboard_messages[reaction.message.guild.id].remove(
                            fireboard_message
                        )
                        continue

                    self.logger.debug(
                        f"Deleting fireboard message {fireboard_message.fireboard_message_id}"
                    )
                    await board_msg.delete()
                except discord.NotFound:
                    self.logger.debug("Delete message not found, deleting record")
                    async with get_session() as session:
                        await session.delete(fireboard_message)

                    self.bot.fireboard_messages[reaction.message.guild.id].remove(fireboard_message)
                except Exception as e:
                    await log_error(
                        bot=self.bot,
                        module="Fireboard",
                        guild_id=reaction.message.guild.id,
                        error="An unknown error occurred while processing a fireboard reaction emoji clear event",
                        details=f"Message ID: {reaction.message.id}",
                        exc=e,
                    )
                    continue

    # Listen for reactions added
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        self.logger.debug(
            f"Reaction added: {payload.emoji} by {payload.user_id} on message {payload.message_id}"
        )

        try:
            await self.event_queue.put(payload)
        except asyncio.QueueShutDown:
            return

    # Listen for reactions removed
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        self.logger.debug(
            f"Reaction removed: {payload.emoji} by {payload.user_id} on message {payload.message_id}"
        )

        try:
            await self.event_queue.put(payload)
        except asyncio.QueueShutDown:
            return

    # Listen for message edits
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        self.logger.debug(f"Message edited: {payload.message_id} in channel {payload.channel_id}")

        if "content" not in payload.data:
            self.logger.debug("No content in payload data")
            return

        message = payload.message
        if not message.content or any([message.webhook_id, message.embeds, message.poll]):
            self.logger.debug("Ignoring message edit due to content type / no content")
            return

        if payload.cached_message and payload.cached_message.content == payload.data["content"]:
            self.logger.debug("Message content is the same as cached message")
            return

        try:
            await self.event_queue.put(payload)
        except asyncio.QueueShutDown:
            return

    # Listen for message delete
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        self.logger.debug(f"Message deleted: {payload.message_id} in channel {payload.channel_id}")

        try:
            await self.event_queue.put(payload)
        except asyncio.QueueShutDown:
            return

    # Listen for reactions cleared
    @commands.Cog.listener()
    async def on_reaction_clear(self, message: discord.Message, reactions: list[discord.Reaction]):
        self.logger.debug(
            f"Reactions cleared on message {message.id} in channel {message.channel.id}"
        )

        try:
            await self.event_queue.put(message)
        except asyncio.QueueShutDown:
            return

    # Listen for specific reaction cleared
    @commands.Cog.listener()
    async def on_reaction_clear_emoji(self, reaction: discord.Reaction):
        self.logger.debug(
            f"Reactions cleared for emoji {reaction.emoji} on message {reaction.message.id} in channel {reaction.message.channel.id}"
        )

        try:
            await self.event_queue.put(reaction)
        except asyncio.QueueShutDown:
            return


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(FireboardCog(bot))
