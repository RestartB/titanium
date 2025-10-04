import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lib.sql import FireboardMessage, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


class FireboardCog(commands.Cog):
    """Server fireboard system"""

    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
        self.event_queue: asyncio.Queue[
            discord.RawMessageUpdateEvent
            | discord.RawMessageDeleteEvent
            | discord.Reaction
            | tuple[discord.Reaction, discord.User | discord.Member]
            | discord.Message
        ] = asyncio.Queue()
        self.event_queue_task = self.bot.loop.create_task(self.queue_worker())
        self.logger: logging.Logger = logging.getLogger("fireboard")

    def cog_unload(self) -> None:
        self.event_queue.shutdown(immediate=True)

    def _fireboard_embed(
        self,
        message: discord.Message,
    ) -> discord.Embed:
        """Creates a fireboard embed message"""
        embed = discord.Embed(
            description=message.content,
            color=discord.Color.random(),
            timestamp=message.created_at,
        )
        embed.set_author(
            name=message.author.name, icon_url=message.author.display_avatar.url
        )
        return embed

    async def queue_worker(self):
        self.logger.info("Fireboard event handler started.")
        while True:
            try:
                await self.bot.wait_until_ready()
                event = await self.event_queue.get()
            except asyncio.QueueShutDown:
                return

            try:
                if isinstance(event, discord.RawMessageUpdateEvent):
                    await self.message_edit_handler(event)
                elif isinstance(event, discord.RawMessageDeleteEvent):
                    await self.message_delete_handler(event)
                elif isinstance(event, discord.Reaction):
                    await self.reaction_emoji_clear_handler(event)
                elif isinstance(event, tuple) and len(event) == 2:
                    await self._reaction_add_remove(event[0], event[1])
                elif isinstance(event, discord.Message):
                    await self.reaction_clear_handler(event)
                elif isinstance(event, discord.Reaction):
                    await self.reaction_emoji_clear_handler(event)
            except Exception as e:
                self.logger.error("Error processing event in fireboard:")
                self.logger.exception(e)
            finally:
                self.event_queue.task_done()

    async def _calculate_reaction_count(
        self,
        reaction: discord.Reaction,
        author: discord.User | discord.Member,
        ignore_self: bool,
        ignore_bots: bool,
    ) -> int:
        users = [user async for user in reaction.users()]
        amount = 0

        for user in users:
            if ignore_bots and user.bot:
                continue
            if ignore_self and user.id == author.id:
                continue
            amount += 1

        return amount

    async def _reaction_add_remove(
        self, reaction: discord.Reaction, user: discord.User | discord.Member
    ):
        if (
            self.bot.user is None
            or reaction.message.guild is None
            or reaction.message.guild.id not in self.bot.guild_configs
            or not self.bot.guild_configs[reaction.message.guild.id].fireboard_enabled
            or len(
                self.bot.guild_configs[
                    reaction.message.guild.id
                ].fireboard_settings.fireboard_boards
            )
            == 0
            or user.id == self.bot.user.id
            or isinstance(
                reaction.message.channel, (discord.DMChannel, discord.GroupChannel)
            )
            or isinstance(reaction.message.author, discord.User)
        ):
            self.logger.debug("Ignoring reaction")
            return

        processed_boards: list[int] = []

        for user_message in self.bot.fireboard_messages.get(
            reaction.message.guild.id, []
        ):
            if user_message.message_id == reaction.message.id:
                processed_boards.append(user_message.fireboard.id)
                channel = self.bot.get_channel(user_message.fireboard.channel_id)

                if channel is None or isinstance(
                    channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    continue

                try:
                    board_msg = await channel.fetch_message(
                        user_message.fireboard_message_id
                    )
                    count = await self._calculate_reaction_count(
                        reaction,
                        reaction.message.author,
                        user_message.fireboard.ignore_self_reactions,
                        user_message.fireboard.ignore_bots,
                    )

                    content = f"{count} {user_message.fireboard.reaction} | {reaction.message.author.mention} | {reaction.message.channel.mention}"

                    if (
                        count >= user_message.fireboard.threshold
                        and content != board_msg.content
                    ):
                        await board_msg.edit(
                            content=content,
                            embed=self._fireboard_embed(reaction.message),
                        )
                        continue
                    elif count < user_message.fireboard.threshold:
                        await board_msg.delete()

                        async with get_session() as session:
                            await session.delete(user_message)

                        self.bot.fireboard_messages[reaction.message.guild.id].remove(
                            user_message
                        )

                        continue
                except (discord.NotFound, discord.Forbidden):
                    continue

        for board in self.bot.guild_configs[
            reaction.message.guild.id
        ].fireboard_settings.fireboard_boards:
            if board.id in processed_boards or board.reaction != str(reaction.emoji):
                continue

            count = await self._calculate_reaction_count(
                reaction,
                reaction.message.author,
                board.ignore_self_reactions,
                board.ignore_bots,
            )

            if (
                count >= board.threshold
                and reaction.message.channel.id not in board.ignored_channels
                and any(
                    role.id not in board.ignored_roles
                    for role in reaction.message.author.roles
                )
            ):
                content = f"{count} {board.reaction} | {reaction.message.author.mention} | {reaction.message.channel.mention}"
                channel = self.bot.get_channel(board.channel_id)

                if channel is None or isinstance(
                    channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    return

                new_message = await channel.send(
                    content=content,
                    embed=self._fireboard_embed(reaction.message),
                )

                async with get_session() as session:
                    fireboard_message = FireboardMessage(
                        guild_id=reaction.message.guild.id,
                        channel_id=reaction.message.channel.id,
                        message_id=reaction.message.id,
                        fireboard_id=board.id,
                        fireboard_message_id=new_message.id,
                    )
                    session.add(fireboard_message)

                    await session.commit()
                    await session.flush()
                    await session.refresh(fireboard_message)

                    stmt = (
                        select(FireboardMessage)
                        .where(FireboardMessage.id == fireboard_message.id)
                        .options(selectinload("*"))
                    )
                    result = await session.execute(stmt)
                    fireboard_message = result.scalars().first()

                    self.bot.fireboard_messages.setdefault(
                        reaction.message.guild.id, []
                    ).append(fireboard_message)

                return

    async def message_edit_handler(self, payload: discord.RawMessageUpdateEvent):
        self.logger.debug(
            f"Handling message edit. Message id: {payload.message_id}, channel id: {payload.channel_id}, guild id: {payload.guild_id}"
        )

        if (
            payload.guild_id is None
            or payload.guild_id not in self.bot.guild_configs
            or not self.bot.guild_configs[payload.guild_id].fireboard_enabled
            or len(
                self.bot.guild_configs[
                    payload.guild_id
                ].fireboard_settings.fireboard_boards
            )
            == 0
        ):
            return

        if isinstance(
            payload.message.channel, (discord.DMChannel, discord.GroupChannel)
        ):
            self.logger.debug("Ignoring edit in DM/Group channel")
            return

        for message in self.bot.fireboard_messages.get(payload.guild_id, []):
            self.logger.debug(
                f"Checking for match: {message.message_id} == {payload.message_id}"
            )
            if message.message_id == payload.message_id:
                self.logger.debug("Found matching message")
                channel = self.bot.get_channel(message.fireboard.channel_id)

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
                    msg = await channel.fetch_message(message.fireboard_message_id)
                    await msg.edit(
                        embed=self._fireboard_embed(payload.message),
                    )

                    self.logger.debug("Edited message")

                except discord.NotFound:
                    self.logger.debug("Edit message not found, deleting record")

                    async with get_session() as session:
                        await session.delete(message)

                    self.bot.fireboard_messages[payload.guild_id].remove(message)
                    continue
                except Exception as e:
                    self.logger.error("Error editing fireboard message:")
                    self.logger.exception(e)
                    continue

    async def message_delete_handler(self, payload: discord.RawMessageDeleteEvent):
        if (
            payload.guild_id is None
            or payload.guild_id not in self.bot.guild_configs
            or not self.bot.guild_configs[payload.guild_id].fireboard_enabled
            or len(
                self.bot.guild_configs[
                    payload.guild_id
                ].fireboard_settings.fireboard_boards
            )
            == 0
        ):
            return

        for message in self.bot.fireboard_messages.get(payload.guild_id, []):
            if message.message_id == payload.message_id:
                channel = self.bot.get_channel(message.fireboard.channel_id)

                if channel is None or isinstance(
                    channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    continue

                try:
                    msg = await channel.fetch_message(message.fireboard_message_id)
                    await msg.delete()

                    async with get_session() as session:
                        await session.delete(message)

                    self.bot.fireboard_messages[payload.guild_id].remove(message)

                except discord.NotFound:
                    self.logger.debug("Delete message not found, deleting record")
                    async with get_session() as session:
                        await session.delete(message)

                    self.bot.fireboard_messages[payload.guild_id].remove(message)
                    continue
                except Exception as e:
                    self.logger.error("Error deleting fireboard message:")
                    self.logger.exception(e)
                    continue

    async def reaction_clear_handler(self, message: discord.Message):
        if (
            message.guild is None
            or message.guild.id not in self.bot.guild_configs
            or not self.bot.guild_configs[message.guild.id].fireboard_enabled
            or len(
                self.bot.guild_configs[
                    message.guild.id
                ].fireboard_settings.fireboard_boards
            )
            == 0
        ):
            return

        for message in self.bot.fireboard_messages.get(message.guild.id, []):
            if message.message_id == message.id:
                channel = self.bot.get_channel(message.fireboard.channel_id)

                if channel is None or isinstance(
                    channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    continue

                try:
                    msg = await channel.fetch_message(message.fireboard_message_id)
                    await msg.delete()

                    async with get_session() as session:
                        await session.delete(message)

                    self.bot.fireboard_messages[message.guild_id].remove(message)
                except discord.NotFound:
                    self.logger.debug("Delete message not found, deleting record")
                    async with get_session() as session:
                        await session.delete(message)

                    self.bot.fireboard_messages[message.guild_id].remove(message)
                except Exception as e:
                    self.logger.error("Error deleting fireboard message:")
                    self.logger.exception(e)
                    continue

    async def reaction_emoji_clear_handler(self, reaction: discord.Reaction):
        if (
            reaction.message.guild is None
            or reaction.message.guild.id not in self.bot.guild_configs
            or not self.bot.guild_configs[reaction.message.guild.id].fireboard_enabled
            or len(
                self.bot.guild_configs[
                    reaction.message.guild.id
                ].fireboard_settings.fireboard_boards
            )
            == 0
        ):
            return

        for message in self.bot.fireboard_messages.get(reaction.message.guild.id, []):
            if (
                message.message_id == reaction.message.id
                and message.fireboard.reaction == str(reaction.emoji)
            ):
                channel = self.bot.get_channel(message.fireboard.channel_id)

                if channel is None or isinstance(
                    channel,
                    (
                        discord.ForumChannel,
                        discord.CategoryChannel,
                        discord.abc.PrivateChannel,
                    ),
                ):
                    continue

                try:
                    msg = await channel.fetch_message(message.fireboard_message_id)
                    await msg.delete()

                    async with get_session() as session:
                        await session.delete(message)

                    self.bot.fireboard_messages[reaction.message.guild.id].remove(
                        message
                    )
                except discord.NotFound:
                    self.logger.debug("Delete message not found, deleting record")
                    async with get_session() as session:
                        await session.delete(message)

                    self.bot.fireboard_messages[reaction.message.guild.id].remove(
                        message
                    )
                except Exception as e:
                    self.logger.error("Error deleting fireboard message:")
                    self.logger.exception(e)
                    continue

    # Listen for reactions added
    @commands.Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: discord.User | discord.Member
    ):
        try:
            await self.event_queue.put((reaction, user))
        except asyncio.QueueShutDown:
            return

    # Listen for reactions removed
    @commands.Cog.listener()
    async def on_reaction_remove(
        self, reaction: discord.Reaction, user: discord.User | discord.Member
    ):
        try:
            await self.event_queue.put((reaction, user))
        except asyncio.QueueShutDown:
            return

    # Listen for message edits
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        try:
            await self.event_queue.put(payload)
        except asyncio.QueueShutDown:
            return

    # Listen for message delete
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        try:
            await self.event_queue.put(payload)
        except asyncio.QueueShutDown:
            return

    # Listen for reactions cleared
    @commands.Cog.listener()
    async def on_reaction_clear(
        self, message: discord.Message, reactions: list[discord.Reaction]
    ):
        try:
            await self.event_queue.put(message)
        except asyncio.QueueShutDown:
            return

    # Listen for specific reaction cleared
    @commands.Cog.listener()
    async def on_reaction_clear_emoji(self, reaction: discord.Reaction):
        try:
            await self.event_queue.put(reaction)
        except asyncio.QueueShutDown:
            return


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(FireboardCog(bot))
