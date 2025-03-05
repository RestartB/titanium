# pylint: disable=possibly-used-before-assignment

import asyncio
import random

import asqlite
import discord
import discord.ext
import discord.ext.commands
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View


class Fireboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fireboard_pool: asqlite.Pool = bot.fireboard_pool
        self.locked_messages = []

        self.bot.loop.create_task(self.setup())

    # SQL Setup
    async def setup(self):
        async with self.fireboard_pool.acquire() as sql:
            if (
                await sql.fetchone(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='fireMessages';"
                )
                is None
            ):
                # Fire Messages - messages that are active on the fireboard
                await sql.execute(
                    "CREATE TABLE fireMessages (serverID int, msgID int, boardMsgID int, reactionAmount int)"
                )

            if (
                await sql.fetchone(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='fireSettings';"
                )
                is None
            ):
                # Fire Settings - server properties for fireboard
                await sql.execute(
                    "CREATE TABLE fireSettings (serverID int, reactionAmount int, emoji text, channelID int, ignoreBots int)"
                )

            if (
                await sql.fetchone(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='fireChannelBlacklist';"
                )
                is None
            ):
                # Fire Channel Blacklist - blacklisted channels
                await sql.execute(
                    "CREATE TABLE fireChannelBlacklist (serverID int, channelID int)"
                )

            if (
                await sql.fetchone(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='fireRoleBlacklist';"
                )
                is None
            ):
                # Fire Role Blacklist - blacklisted roles
                await sql.execute(
                    "CREATE TABLE fireRoleBlacklist (serverID int, roleID int)"
                )

            await sql.commit()

        await self.refresh_fire_lists()

    # List refresh function
    async def refresh_fire_lists(self):
        async with self.fireboard_pool.acquire() as sql:
            self.fire_messages = await sql.fetchall("SELECT * FROM fireMessages")
            self.fire_settings = await sql.fetchall("SELECT * FROM fireSettings")
            self.fire_channel_blacklist = await sql.fetchall(
                "SELECT * FROM fireChannelBlacklist"
            )
            self.fire_role_blacklist = await sql.fetchall(
                "SELECT * FROM fireRoleBlacklist"
            )

    # Listen for reactions
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        self.bot: discord.ext.commands.Bot

        # Stop if this is a DM
        if payload.guild_id is None:
            return

        queued = False

        # Lock system
        if payload.message_id in self.locked_messages:
            queued = True

            while payload.message_id in self.locked_messages:
                await asyncio.sleep(0.5)

        self.locked_messages.append(payload.message_id)

        try:
            fetched = False

            # Find server config
            for server in self.fire_settings:
                if server[0] == payload.guild_id:
                    react_minimum = server[1]
                    emoji = server[2]
                    channel_id = server[3]
                    ignore_bots = True if int(server[4]) == 1 else False

                    fetched = True

            # Stop if server has no config (fireboard isn't enabled)
            if not fetched:
                return

            # Stop if message is by Titanium
            if payload.message_author_id == self.bot.user.id:
                return

            # Stop if emoji doesn't match
            if str(payload.emoji) != emoji:
                return

            # --- Edit board message if it already exists ---
            if payload.message_id in [message[1] for message in self.fire_messages]:
                message = [
                    message
                    for message in self.fire_messages
                    if message[1] == payload.message_id
                ][0]

                # Only fetch updated reaction count if I have queued or reaction amount is undefined
                if queued or message[3] is None:
                    # Fetch message and channel
                    try:
                        msg_channel = await self.bot.fetch_channel(payload.channel_id)
                        message = await msg_channel.fetch_message(payload.message_id)
                    except discord.errors.NotFound:
                        return

                    # Stop if not enough reactions
                    for reaction in message.reactions:
                        if str(reaction.emoji) == emoji:
                            react_count = reaction.count
                            break

                    if react_count < react_minimum:
                        return
                else:
                    react_count = None

                async with self.fireboard_pool.acquire() as sql:
                    # Set updated react count
                    if react_count is not None:
                        await sql.execute(
                            "UPDATE fireMessages SET reactionAmount = ? WHERE msgID = ?",
                            (
                                react_count,
                                payload.message_id,
                            ),
                        )
                        await self.refresh_fire_lists()
                    else:
                        await sql.execute(
                            "UPDATE fireMessages SET reactionAmount = reactionAmount + 1 WHERE msgID = ?",
                            (payload.message_id,),
                        )
                        await self.refresh_fire_lists()

                # Get message from message list
                message = [
                    message
                    for message in self.fire_messages
                    if message[1] == payload.message_id
                ][0]

                # Get board message
                board_channel = await self.bot.fetch_channel(channel_id)
                board_message = await board_channel.fetch_message(message[2])

                await board_message.edit(
                    content=f"**{message[3]} {emoji}** | <@{payload.message_author_id}> | <#{payload.channel_id}>",
                    embeds=board_message.embeds,
                )

                return

            # Stop if message is in a blacklisted channel
            if payload.channel_id in [
                channel[1] for channel in self.fire_channel_blacklist
            ]:
                return

            # Stop if message is by a blacklisted role
            guild = await self.bot.fetch_guild(payload.guild_id)
            member = await guild.fetch_member(payload.user_id)

            if any(
                role[1] in [role.id for role in member.roles]
                for role in self.fire_role_blacklist
            ):
                return

            # Fetch message and channel
            try:
                msg_channel = await self.bot.fetch_channel(payload.channel_id)
                message = await msg_channel.fetch_message(payload.message_id)
            except discord.errors.NotFound:
                return

            # Stop if message is by a bot
            if ignore_bots and message.author.bot:
                return

            # Stop if message is in an NSFW channel
            if message.channel.nsfw:
                return

            # Stop if not enough reactions
            for reaction in message.reactions:
                if str(reaction.emoji) == emoji:
                    react_count = reaction.count
                    break

            if react_count < react_minimum:
                return

            # --- Send message to fireboard ---

            # Create embed
            embed = discord.Embed(description=message.content, color=Color.random())
            embed.set_author(
                name=message.author.name, icon_url=message.author.display_avatar.url
            )
            embed.timestamp = message.created_at

            # Jump to message button
            view = View()
            view.add_item(
                discord.ui.Button(
                    label="Jump to Message",
                    url=message.jump_url,
                    style=discord.ButtonStyle.url,
                )
            )

            embed_list = [embed]

            # Add reply embed
            if message.reference:
                try:
                    reply_message = await msg_channel.fetch_message(
                        message.reference.message_id
                    )

                    reply_embed = discord.Embed(
                        title="Replying To",
                        description=reply_message.content,
                        color=Color.random(),
                    )
                    reply_embed.set_author(
                        name=reply_message.author.name,
                        icon_url=reply_message.author.display_avatar.url,
                    )
                    reply_embed.timestamp = reply_message.created_at

                    embed_list.insert(0, reply_embed)
                except discord.errors.NotFound:
                    pass

            # Send message
            board_channel = await self.bot.fetch_channel(channel_id)
            board_message = await board_channel.send(
                content=f"**{react_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>",
                embeds=embed_list,
                view=view,
                files=[
                    await attachment.to_file() for attachment in message.attachments
                ],
            )

            async with self.fireboard_pool.acquire() as sql:
                # Insert message to DB
                await sql.execute(
                    "INSERT INTO fireMessages (serverID, msgID, boardMsgID, reactionAmount) VALUES (?, ?, ?, ?)",
                    (
                        payload.guild_id,
                        payload.message_id,
                        board_message.id,
                        react_count,
                    ),
                )
                await sql.commit()

            await self.refresh_fire_lists()
        except Exception as e:
            raise e
        finally:
            self.locked_messages.remove(payload.message_id)

    # Listen for reaction removal
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        self.bot: discord.ext.commands.Bot

        queued = False

        # Stop if this is a DM
        if payload.guild_id is None:
            return

        # Lock system
        if payload.message_id in self.locked_messages:
            queued = True

            while payload.message_id in self.locked_messages:
                await asyncio.sleep(0.5)

        self.locked_messages.append(payload.message_id)

        try:
            fetched = False

            # Find server config
            for server in self.fire_settings:
                if server[0] == payload.guild_id:
                    react_minimum = server[1]
                    emoji = server[2]
                    channel_id = server[3]
                    ignore_bots = True if int(server[4]) == 1 else False

                    fetched = True

            # Stop if server has no config (fireboard isn't enabled)
            if not fetched:
                return

            # Stop if message is by Titanium
            if payload.message_author_id == self.bot.user.id:
                return

            # Stop if emoji doesn't match
            if str(payload.emoji) != emoji:
                return

            # --- Edit board message if it already exists ---
            if payload.message_id in [message[1] for message in self.fire_messages]:
                prev_react_count = [
                    message
                    for message in self.fire_messages
                    if message[1] == payload.message_id
                ][0][3]

                # Only fetch updated reaction count if I have queued
                if queued or prev_react_count is None:
                    # Fetch message and channel
                    try:
                        msg_channel = await self.bot.fetch_channel(payload.channel_id)
                        message = await msg_channel.fetch_message(payload.message_id)
                    except discord.errors.NotFound:
                        return

                    # Stop if not enough reactions
                    for reaction in message.reactions:
                        if str(reaction.emoji) == emoji:
                            react_count = reaction.count
                            break

                    if react_count < react_minimum:
                        return
                else:
                    react_count = None

                async with self.fireboard_pool.acquire() as sql:
                    # Set updated react count
                    if react_count is not None:
                        await sql.execute(
                            "UPDATE fireMessages SET reactionAmount = ? WHERE msgID = ?",
                            (
                                react_count,
                                payload.message_id,
                            ),
                        )
                        await self.refresh_fire_lists()
                    else:
                        await sql.execute(
                            "UPDATE fireMessages SET reactionAmount = reactionAmount - 1 WHERE msgID = ?",
                            (payload.message_id,),
                        )
                        await self.refresh_fire_lists()

                # Get message from message list
                message = [
                    message
                    for message in self.fire_messages
                    if message[1] == payload.message_id
                ][0]

                # Get board message
                board_channel = await self.bot.fetch_channel(channel_id)
                board_message = await board_channel.fetch_message(message[2])

                # Remove message if not enough reactions
                if message[3] < react_minimum:
                    await board_message.delete()

                    async with self.fireboard_pool.acquire() as sql:
                        await sql.execute(
                            "DELETE FROM fireMessages WHERE msgID = ?",
                            (payload.message_id,),
                        )
                        await sql.commit()

                    await self.refresh_fire_lists()

                    return

                # Workaround for lack of message author ID
                content = board_message.content
                content = content.replace(
                    f"{prev_react_count} {emoji}", f"{message[3]} {emoji}"
                )

                await board_message.edit(content=content)

                return

            # Stop if message is in a blacklisted channel
            if payload.channel_id in [
                channel[1] for channel in self.fire_channel_blacklist
            ]:
                return

            # Stop if message is by a blacklisted role
            guild = await self.bot.fetch_guild(payload.guild_id)
            member = await guild.fetch_member(payload.user_id)

            if any(
                role[1] in [role.id for role in member.roles]
                for role in self.fire_role_blacklist
            ):
                return

            # Fetch message and channel
            try:
                msg_channel = await self.bot.fetch_channel(payload.channel_id)
                message = await msg_channel.fetch_message(payload.message_id)
            except discord.errors.NotFound:
                return

            # Stop if message is by a bot
            if ignore_bots and message.author.bot:
                return

            # Stop if message is in an NSFW channel
            if message.channel.nsfw:
                return

            # Get reaction count
            react_count = 0

            for reaction in message.reactions:
                if str(reaction.emoji) == emoji:
                    react_count = reaction.count
                    break

            # Stop if not enough reactions
            if react_count < react_minimum:
                return

            # --- Send message to fireboard ---

            # Create embed
            embed = discord.Embed(description=message.content, color=Color.random())
            embed.set_author(
                name=message.author.name, icon_url=message.author.display_avatar.url
            )
            embed.timestamp = message.created_at

            # Jump to message button
            view = View()
            view.add_item(
                discord.ui.Button(
                    label="Jump to Message",
                    url=message.jump_url,
                    style=discord.ButtonStyle.url,
                )
            )

            embed_list = [embed]

            # Add reply embed
            if message.reference:
                try:
                    reply_message = await msg_channel.fetch_message(
                        message.reference.message_id
                    )

                    reply_embed = discord.Embed(
                        title="Replying To",
                        description=reply_message.content,
                        color=Color.random(),
                    )
                    reply_embed.set_author(
                        name=reply_message.author.name,
                        icon_url=reply_message.author.display_avatar.url,
                    )
                    reply_embed.timestamp = reply_message.created_at

                    embed_list.insert(0, reply_embed)
                except discord.errors.NotFound:
                    pass

            # Send message
            board_channel = await self.bot.fetch_channel(channel_id)
            board_message = await board_channel.send(
                content=f"**{react_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>",
                embeds=embed_list,
                view=view,
                files=[
                    await attachment.to_file() for attachment in message.attachments
                ],
            )

            async with self.fireboard_pool.acquire() as sql:
                # Insert message to DB
                await sql.execute(
                    "INSERT INTO fireMessages (serverID, msgID, boardMsgID, reactionAmount) VALUES (?, ?, ?, ?)",
                    (
                        payload.guild_id,
                        payload.message_id,
                        board_message.id,
                        react_count,
                    ),
                )
                await sql.commit()

            await self.refresh_fire_lists()
        except Exception as e:
            raise e
        finally:
            self.locked_messages.remove(payload.message_id)

    # Listen for message reaction clear
    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionClearEvent):
        self.bot: discord.ext.commands.Bot

        # Stop if this is a DM
        if payload.guild_id is None:
            return

        # Lock system
        if payload.message_id in self.locked_messages:
            while payload.message_id in self.locked_messages:
                await asyncio.sleep(0.5)

        self.locked_messages.append(payload.message_id)

        try:
            # Only trigger if message is already in the fireboard DB
            if payload.message_id in [message[1] for message in self.fire_messages]:
                # Find server config
                for server in self.fire_settings:
                    if server[0] == payload.guild_id:
                        channel_id = server[3]

                # Get guild
                try:
                    guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                except discord.errors.NotFound:
                    return

                # Get message channel
                channel: discord.abc.GuildChannel = await guild.fetch_channel(
                    payload.channel_id
                )

                # Get our message
                message: discord.Message = await channel.fetch_message(
                    payload.message_id
                )

                # See if board message is already present
                for fire_message in self.fire_messages:
                    if fire_message[1] == message.id:
                        async with self.fireboard_pool.acquire() as sql:
                            try:
                                # Delete message
                                try:
                                    channel: discord.TextChannel = (
                                        await guild.fetch_channel(channel_id)
                                    )
                                except discord.errors.NotFound:
                                    await sql.execute(
                                        "DELETE FROM fireSettings WHERE serverID = ?",
                                        (payload.guild_id,),
                                    )
                                    await sql.commit()
                                    self.locked_messages.remove(payload.message_id)

                                    return

                                board_message = await channel.fetch_message(
                                    fire_message[2]
                                )
                                await board_message.delete()

                                # Delete message from DB
                                await sql.execute(
                                    "DELETE FROM fireMessages WHERE msgID = ?",
                                    (message.id,),
                                )
                                await sql.commit()

                                await self.refresh_fire_lists()

                                return
                            except discord.errors.NotFound:
                                # Delete message from DB
                                await sql.execute(
                                    "DELETE FROM fireMessages WHERE msgID = ?",
                                    (message.id,),
                                )
                                await sql.commit()

                                await self.refresh_fire_lists()

                                return
            else:
                return
        except Exception as e:
            raise e
        finally:
            self.locked_messages.remove(payload.message_id)

    # Listen for specific emoji being cleared
    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(
        self, payload: discord.RawReactionClearEmojiEvent
    ):
        self.bot: discord.ext.commands.Bot

        # Stop if this is a DM
        if payload.guild_id is None:
            return

        # Lock system
        if payload.message_id in self.locked_messages:
            while payload.message_id in self.locked_messages:
                await asyncio.sleep(0.5)

        self.locked_messages.append(payload.message_id)

        try:
            # Only trigger if message is already in the fireboard DB
            if payload.message_id in [message[1] for message in self.fire_messages]:
                for server in self.fire_settings:
                    if server[0] == payload.guild_id:
                        emoji = server[2]
                        channel_id = server[3]

                # Only trigger if cleared emoji is our emoji
                if str(payload.emoji) == emoji:
                    # Fetch server
                    try:
                        guild: discord.Guild = await self.bot.fetch_guild(
                            payload.guild_id
                        )
                    except discord.errors.NotFound:
                        return

                    # Get message channel
                    channel: discord.abc.GuildChannel = await guild.fetch_channel(
                        payload.channel_id
                    )

                    # See if board message is already present
                    for fire_message in self.fire_messages:
                        if fire_message[1] == payload.message_id:
                            async with self.fireboard_pool.acquire() as sql:
                                try:
                                    # Fetch fireboard channel
                                    try:
                                        channel: discord.TextChannel = (
                                            await guild.fetch_channel(channel_id)
                                        )
                                    except discord.errors.NotFound:
                                        await sql.execute(
                                            "DELETE FROM fireSettings WHERE serverID = ?",
                                            (payload.guild_id,),
                                        )
                                        await sql.commit()

                                        return

                                    # Delete message
                                    board_message = await channel.fetch_message(
                                        fire_message[2]
                                    )
                                    await board_message.delete()

                                    # Delete message from DB
                                    await sql.execute(
                                        "DELETE FROM fireMessages WHERE msgID = ?",
                                        (payload.message_id,),
                                    )
                                    await sql.commit()

                                    await self.refresh_fire_lists()

                                    return
                                except discord.errors.NotFound:
                                    # Delete message from DB
                                    await sql.execute(
                                        "DELETE FROM fireMessages WHERE msgID = ?",
                                        (payload.message_id,),
                                    )
                                    await sql.commit()

                                    await self.refresh_fire_lists()

                                    return
            else:
                return
        except Exception as e:
            raise e
        finally:
            self.locked_messages.remove(payload.message_id)

    # Listen for message being deleted
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        self.bot: discord.ext.commands.Bot

        # Stop if this is a DM
        if payload.guild_id is None:
            return

        # Lock system
        if payload.message_id in self.locked_messages:
            while payload.message_id in self.locked_messages:
                await asyncio.sleep(0.5)

        self.locked_messages.append(payload.message_id)

        try:
            # Only trigger if message is already in the fireboard DB
            if payload.message_id in [message[1] for message in self.fire_messages]:
                # Fetch server config
                for server in self.fire_settings:
                    if server[0] == payload.guild_id:
                        channel_id = server[3]

                # Fetch server
                try:
                    guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                except discord.errors.NotFound:
                    return

                # Get message channel
                channel: discord.abc.GuildChannel = await guild.fetch_channel(
                    payload.channel_id
                )

                # See if board message is already present
                for fire_message in self.fire_messages:
                    if fire_message[1] == payload.message_id:
                        async with self.fireboard_pool.acquire() as sql:
                            try:
                                # Fetch fireboard channel
                                try:
                                    channel: discord.TextChannel = (
                                        await guild.fetch_channel(channel_id)
                                    )
                                except discord.errors.NotFound:
                                    await sql.execute(
                                        "DELETE FROM fireSettings WHERE serverID = ?",
                                        (payload.guild_id,),
                                    )
                                    await sql.commit()

                                    return

                                # Delete message
                                board_message = await channel.fetch_message(
                                    fire_message[2]
                                )
                                await board_message.delete()

                                # Delete message from DB
                                await sql.execute(
                                    "DELETE FROM fireMessages WHERE msgID = ?",
                                    (payload.message_id,),
                                )
                                await sql.commit()

                                await self.refresh_fire_lists()

                                return
                            except discord.errors.NotFound:
                                # Delete message from DB
                                await sql.execute(
                                    "DELETE FROM fireMessages WHERE msgID = ?",
                                    (payload.message_id,),
                                )
                                await sql.commit()

                                await self.refresh_fire_lists()

                                return
            else:
                return
        except Exception as e:
            raise e
        finally:
            self.locked_messages.remove(payload.message_id)

    # Listen for message being edited
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        self.bot: discord.ext.commands.Bot

        # Stop if this is a DM
        if payload.guild_id is None:
            return

        # Lock system
        if payload.message_id in self.locked_messages:
            while payload.message_id in self.locked_messages:
                await asyncio.sleep(0.5)

        self.locked_messages.append(payload.message_id)

        try:
            # Only trigger if message is already in the fireboard DB
            if payload.message_id in [message[1] for message in self.fire_messages]:
                # Fetch server config
                for server in self.fire_settings:
                    if server[0] == payload.guild_id:
                        channel_id = server[3]

                # Fetch server
                try:
                    guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                except discord.errors.NotFound:
                    return

                # Get message channel
                channel: discord.abc.GuildChannel = await guild.fetch_channel(
                    payload.channel_id
                )

                # Get our message
                message: discord.Message = await channel.fetch_message(
                    payload.message_id
                )

                embed = discord.Embed(description=message.content, color=Color.random())
                embed.set_author(
                    name=message.author.name, icon_url=message.author.display_avatar.url
                )
                embed.timestamp = message.created_at

                # Jump to message button
                view = View()
                view.add_item(
                    discord.ui.Button(
                        label="Jump to Message",
                        url=message.jump_url,
                        style=discord.ButtonStyle.url,
                    )
                )

                embed_list = [embed]

                # Add reply embed
                if message.reference:
                    try:
                        reply_message = await channel.fetch_message(
                            message.reference.message_id
                        )

                        reply_embed = discord.Embed(
                            title="Replying To",
                            description=reply_message.content,
                            color=Color.random(),
                        )
                        reply_embed.set_author(
                            name=reply_message.author.name,
                            icon_url=reply_message.author.display_avatar.url,
                        )
                        reply_embed.timestamp = reply_message.created_at

                        embed_list.insert(0, reply_embed)
                    except discord.errors.NotFound:
                        pass

                try:
                    channel: discord.TextChannel = await guild.fetch_channel(channel_id)
                except discord.errors.NotFound:
                    async with self.fireboard_pool.acquire() as sql:
                        await sql.execute(
                            "DELETE FROM fireSettings WHERE serverID = ?",
                            (payload.guild_id,),
                        )
                        await sql.commit()

                    return

                # Find previous fireboard message
                try:
                    for fire_message in self.fire_messages:
                        if (
                            fire_message[0] == payload.guild_id
                            and fire_message[1] == payload.message_id
                        ):
                            # Edit with updated embed - reaction amount stays the same
                            board_message = await channel.fetch_message(fire_message[2])

                            await board_message.edit(
                                embeds=embed_list, attachments=message.attachments
                            )
                except discord.errors.NotFound:  # Message not found
                    async with self.fireboard_pool.acquire() as sql:
                        # Delete message from DB
                        await sql.execute(
                            "DELETE FROM fireMessages WHERE msgID = ?",
                            (payload.message_id,),
                        )
                        await sql.commit()

                        await self.refresh_fire_lists()

                    return
            else:
                return
        except Exception as e:
            raise e
        finally:
            self.locked_messages.remove(payload.message_id)

    # Listen for fireboard channel delete
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        # Only trigger if server has fireboard enabled
        if channel.guild.id in [guild[0] for guild in self.fire_settings]:
            for server in self.fire_settings:
                if server[0] == channel.guild.id:
                    if server[3] == channel.id:
                        async with self.fireboard_pool.acquire() as sql:
                            # Delete fireboard config
                            await sql.execute(
                                "DELETE FROM fireMessages WHERE serverID = ?",
                                (channel.guild.id,),
                            )
                            await sql.execute(
                                "DELETE FROM fireSettings WHERE serverID = ?",
                                (channel.guild.id,),
                            )
                            await sql.commit()

                        await self.refresh_fire_lists()

                        return
        else:
            return

    # Listen for server being left / deleted
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        # Only trigger if server has fireboard enabled
        if guild.id in [guild[0] for guild in self.fire_settings]:
            for server in self.fire_settings:
                if server[0] == guild.id:
                    async with self.fireboard_pool.acquire() as sql:
                        # Delete fireboard config
                        await sql.execute(
                            "DELETE FROM fireMessages WHERE serverID = ?", (guild.id,)
                        )
                        await sql.execute(
                            "DELETE FROM fireSettings WHERE serverID = ?", (guild.id,)
                        )
                        await sql.commit()

                    await self.refresh_fire_lists()

                    return
        else:
            return

    # Command group setup
    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=False, private_channel=False
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=False)
    fireGroup = app_commands.Group(
        name="fireboard",
        description="Fireboard related commands.",
        allowed_contexts=context,
        allowed_installs=installs,
    )

    # Random fireboard message command
    @fireGroup.command(
        name="random", description="Get a random message from the fireboard."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    async def random_fireboard(
        self, interaction: discord.Interaction, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        channel_id = None

        # Find server config
        for server in self.fire_settings:
            if server[0] == interaction.guild_id:
                channel_id = server[3]

        if channel_id is None:
            embed = discord.Embed(
                title="Error",
                description="Fireboard is not enabled in this server.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

            return

        # Fetch channel
        try:
            channel = await interaction.guild.fetch_channel(channel_id)
        except discord.errors.NotFound:
            embed = discord.Embed(
                title="Error",
                description="Can't find the fireboard channel. Please contact a server admin.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

            return

        # Fetch messages
        async with self.fireboard_pool.acquire() as sql:
            messages = await sql.fetchall(
                "SELECT * FROM fireMessages WHERE serverID = ?", (interaction.guild_id,)
            )

            if not messages:
                embed = discord.Embed(
                    title="Error",
                    description="No messages found in the fireboard.",
                    color=Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)

                return
            else:
                while messages != []:
                    message = random.choice(messages)

                    try:
                        board_message = await channel.fetch_message(message[2])

                        view = View().from_message(board_message)

                        await interaction.followup.send(
                            embeds=board_message.embeds, view=view, ephemeral=ephemeral
                        )

                        return
                    except discord.errors.NotFound:
                        messages.remove(message)

                embed = discord.Embed(
                    title="Error",
                    description="No messages found in the fireboard.",
                    color=Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Command group setup
    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=False, private_channel=False
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=False)
    perms = discord.Permissions()
    fireSetupGroup = app_commands.Group(
        name="fireboard-setup",
        description="Control the fireboard.",
        allowed_contexts=context,
        allowed_installs=installs,
        default_permissions=perms,
    )

    # Fireboard enable command
    @fireSetupGroup.command(
        name="enable", description="Enable the fireboard in the current channel."
    )
    async def enable_fireboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fire_settings]:
            embed = discord.Embed(
                title="Fireboard is already enabled.", color=Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Default settings
            react_minimum = 3
            emoji = "🔥"
            channel_id = interaction.channel_id
            ignore_bots = True

            embed = discord.Embed(
                title="Fireboard",
                description="This channel has been configured as the server fireboard.",
                color=Color.random(),
            )
            embed.set_footer(text="Feel free to delete this message!")

            try:
                channel = await interaction.guild.fetch_channel(channel_id)
                await channel.send(embed=embed)
            except discord.errors.Forbidden or discord.errors.NotFound:
                embed = discord.Embed(
                    title="Error",
                    description="Looks like I can't send messages in this channel. Check permissions and try again.",
                    color=Color.random(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

                return

            async with self.fireboard_pool.acquire() as sql:
                # Insert to DB, refresh lists
                await sql.execute(
                    "INSERT INTO fireSettings (serverID, reactionAmount, emoji, channelID, ignoreBots) VALUES (?, ?, ?, ?, ?)",
                    (
                        interaction.guild_id,
                        react_minimum,
                        emoji,
                        channel_id,
                        ignore_bots,
                    ),
                )
                await sql.commit()

            await self.refresh_fire_lists()

            embed = discord.Embed(
                title="Enabled",
                description="Fireboard has been enabled in the current channel.",
                color=Color.green(),
            )
            embed.add_field(
                name="Info",
                value=f"**Reaction Requirement:** `{react_minimum} reactions`\n**Fireboard Channel:** <#{channel_id}>\n**Emoji:** {emoji}\n**Ignore Bots:** `{ignore_bots}`",
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

    class ConfirmDisableView(View):
        def __init__(self):
            super().__init__(timeout=60)

        async def disable_fireboard(
            self, interaction: discord.Interaction, pool: asqlite.Pool
        ):
            async with pool.acquire() as sql:
                try:
                    await sql.execute(
                        "DELETE FROM fireMessages WHERE serverID = ?",
                        (interaction.guild_id,),
                    )
                    await sql.execute(
                        "DELETE FROM fireSettings WHERE serverID = ?",
                        (interaction.guild_id,),
                    )
                    await sql.execute(
                        "DELETE FROM fireChannelBlacklist WHERE serverID = ?",
                        (interaction.guild_id,),
                    )
                    await sql.execute(
                        "DELETE FROM fireRoleBlacklist WHERE serverID = ?",
                        (interaction.guild_id,),
                    )
                    await sql.commit()
                    return True
                except Exception:
                    return False

        @discord.ui.button(label="Disable", style=discord.ButtonStyle.red)
        async def confirm(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            await interaction.response.defer(ephemeral=True)

            success = await self.disable_fireboard(interaction, self.pool)

            if success:
                embed = discord.Embed(
                    title="Done!",
                    description="Fireboard was disabled.",
                    color=Color.green(),
                )
                await self.cog.refresh_fire_lists()  # pylint: disable=no-member
            else:
                embed = discord.Embed(
                    title="Error",
                    description="Failed to disable fireboard.",
                    color=Color.red(),
                )

            await interaction.edit_original_response(embed=embed, view=None)
            self.stop()

        async def on_timeout(self):
            for item in self.children:
                item.disabled = True

            embed = discord.Embed(
                title="Timeout",
                description="You didn't press the button in time.",
                color=Color.red(),
            )
            await self.message.edit(embed=embed, view=self)

    # Fireboard disable command
    @fireSetupGroup.command(name="disable", description="Disable the server fireboard.")
    async def disable_fireboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if interaction.guild_id in [guild[0] for guild in self.fire_settings]:
            view = self.ConfirmDisableView()
            view.pool = self.fireboard_pool
            view.cog = self

            embed = discord.Embed(
                title="Are you sure?",
                description="All data about this server's fireboard will be deleted. This cannot be undone!",
                color=Color.orange(),
            )

            message = await interaction.followup.send(
                embed=embed, view=view, ephemeral=True, wait=True
            )
            view.message = message
        else:
            await interaction.followup.send(
                "Fireboard is not enabled in this server!", ephemeral=True
            )

    # Fireboard server info command
    @fireSetupGroup.command(
        name="info", description="View fireboard config for this server."
    )
    async def fireboard_info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fire_settings]:
            # Fetch server settings
            for server in self.fire_settings:
                if server[0] == interaction.guild_id:
                    react_minimum = server[1]
                    emoji = server[2]
                    channel_id = server[3]
                    ignore_bots = True if int(server[4]) == 1 else False

            embed = discord.Embed(
                title="Server Fireboard Settings",
                description=f"**Reaction Requirement:** `{react_minimum} reactions`\n**Fireboard Channel:** <#{channel_id}>\n**Emoji:** {emoji}\n**Ignore Bots:** `{ignore_bots}`",
                color=Color.random(),
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="Fireboard is not enabled.", color=Color.red())

            await interaction.followup.send(embed=embed, ephemeral=True)

    # Fireboard set emoji command
    @fireSetupGroup.command(name="emoji", description="Set a custom fireboard emoji.")
    async def fireboard_emoji(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fire_settings]:
            embed = discord.Embed(
                title="Waiting for Reaction",
                description=f"{self.bot.options['loading-emoji']} React with this message with your target emoji to set the fireboard emoji.",
                color=Color.orange(),
            )

            msg = await interaction.followup.send(embed=embed, ephemeral=False)

            def check(reaction, user):
                return user == interaction.user and reaction.message.id == msg.id

            # Wait for a reaction
            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=60.0, check=check
                )

                reaction: discord.Reaction = reaction

                async with self.fireboard_pool.acquire() as sql:
                    # Change emoji in DB, refresh lists
                    await sql.execute(
                        "UPDATE fireSettings SET emoji = ? WHERE serverID = ?",
                        (
                            str(reaction.emoji),
                            interaction.guild_id,
                        ),
                    )
                    await sql.commit()

                embed = discord.Embed(
                    title="Emoji Set",
                    description=f"Set emoji to **{str(reaction.emoji)}.**",
                    color=Color.green(),
                )

                await self.refresh_fire_lists()
                await interaction.edit_original_response(embed=embed)
            except asyncio.TimeoutError:  # Timed out
                embed = discord.Embed(
                    title="Timed Out",
                    description="You didn't react in time.",
                    color=Color.red(),
                )

                await interaction.edit_original_response(embed=embed)
        else:
            embed = discord.Embed(title="Fireboard is not enabled.", color=Color.red())

            await interaction.followup.send(embed=embed, ephemeral=False)

    # Fireboard set channel command
    @fireSetupGroup.command(
        name="channel",
        description="Set the channel for fireboard messages to be sent in.",
    )
    async def fireboard_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fire_settings]:
            embed = discord.Embed(
                title="Fireboard",
                description="This channel has been configured as the server fireboard.",
                color=Color.random(),
            )
            embed.set_footer(text="Feel free to delete this message!")

            try:
                await channel.send(embed=embed)
            except discord.errors.NotFound:
                embed = discord.Embed(
                    title="Error",
                    description="Looks like I can't find that channel. Check permissions and try again.",
                    color=Color.random(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

                return
            except discord.errors.Forbidden as e:
                embed = discord.Embed(
                    title="Error",
                    description="Looks like I can't send messages in that channel. Check permissions and try again.",
                    color=Color.random(),
                )
                await interaction.followup.send(embed=embed, content=e, ephemeral=True)

                return

            async with self.fireboard_pool.acquire() as sql:
                # Update channel in DB, refresh lists
                await sql.execute(
                    "UPDATE fireSettings SET channelID = ? WHERE serverID = ?",
                    (
                        channel.id,
                        interaction.guild_id,
                    ),
                )
                await sql.commit()

            await self.refresh_fire_lists()

            embed = discord.Embed(
                title="Channel Set",
                description=f"Fireboard channel has been set to **{channel.mention}.**",
                color=Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="Fireboard is not enabled.", color=Color.red())

            await interaction.followup.send(embed=embed, ephemeral=True)

    # Fireboard set requirement command
    @fireSetupGroup.command(
        name="requirement",
        description="Set required reaction amount for message to be posted on the fireboard.",
    )
    async def fireboard_requirement(
        self, interaction: discord.Interaction, amount: int
    ):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fire_settings]:
            embed = discord.Embed(
                title="Set",
                description=f"Reaction requirement has been set to **{amount} reactions.**",
                color=Color.green(),
            )

            async with self.fireboard_pool.acquire() as sql:
                # Update reaction requirement in DB, refresh lists
                await sql.execute(
                    "UPDATE fireSettings SET reactionAmount = ? WHERE serverID = ?",
                    (
                        amount,
                        interaction.guild_id,
                    ),
                )
                await sql.commit()

            await self.refresh_fire_lists()
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="Fireboard is not enabled.", color=Color.red())

            await interaction.followup.send(embed=embed, ephemeral=True)

    # Fireboard ignore bots command
    @fireSetupGroup.command(
        name="ignore-bots",
        description="Whether bot messages are ignored in the fireboard. Defaults to true.",
    )
    async def fireboard_ignore_bots(
        self, interaction: discord.Interaction, value: bool
    ):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fire_settings]:
            embed = discord.Embed(
                title="Set",
                description=f"Bot messages will **{'be ignored.' if value else 'not be ignored.'}**",
                color=Color.green(),
            )

            async with self.fireboard_pool.acquire() as sql:
                # Update setting in DB, refresh lists
                await sql.execute(
                    "UPDATE fireSettings SET ignoreBots = ? WHERE serverID = ?",
                    (
                        value,
                        interaction.guild_id,
                    ),
                )
                await sql.commit()

            await self.refresh_fire_lists()
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="Fireboard is not enabled.", color=Color.red())

            await interaction.followup.send(embed=embed, ephemeral=True)

    # Fireboard role blacklist
    @fireSetupGroup.command(
        name="channel-blacklist",
        description="Toggle the blacklist for a channel. NSFW channels are always blacklisted.",
    )
    async def fireboard_channel_blacklist(
        self, interaction: discord.Interaction, channel: discord.abc.GuildChannel
    ):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild_id in [guild[0] for guild in self.fire_settings]:
            async with self.fireboard_pool.acquire() as sql:
                if channel.id in [
                    channelEntry[1] for channelEntry in self.fire_channel_blacklist
                ]:
                    await sql.execute(
                        "DELETE FROM fireChannelBlacklist WHERE serverID = ? AND channelID = ?",
                        (
                            interaction.guild_id,
                            channel.id,
                        ),
                    )
                    await sql.commit()

                    await self.refresh_fire_lists()

                    embed = discord.Embed(
                        title="Set",
                        description=f"Removed {channel.mention} from the channel blacklist.",
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await sql.execute(
                        "INSERT INTO fireChannelBlacklist (serverID, channelID) VALUES (?, ?)",
                        (
                            interaction.guild_id,
                            channel.id,
                        ),
                    )
                    await sql.commit()

                    await self.refresh_fire_lists()

                    embed = discord.Embed(
                        title="Set",
                        description=f"Added {channel.mention} to the channel blacklist.",
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="Fireboard is not enabled.", color=Color.red())

            await interaction.followup.send(embed=embed, ephemeral=True)

    # Fireboard role blacklist
    @fireSetupGroup.command(
        name="role-blacklist", description="Toggle the blacklist for a role."
    )
    async def fireboard_role_blacklist(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild_id in [guild[0] for guild in self.fire_settings]:
            async with self.fireboard_pool.acquire() as sql:
                if role.id in [roleEntry[1] for roleEntry in self.fire_role_blacklist]:
                    await sql.execute(
                        "DELETE FROM fireRoleBlacklist WHERE serverID = ? AND roleID = ?",
                        (
                            interaction.guild_id,
                            role.id,
                        ),
                    )
                    await sql.commit()

                    await self.refresh_fire_lists()

                    embed = discord.Embed(
                        title="Set",
                        description=f"Removed {role.mention} from the role blacklist.",
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await sql.execute(
                        "INSERT INTO fireRoleBlacklist (serverID, roleID) VALUES (?, ?)",
                        (
                            interaction.guild_id,
                            role.id,
                        ),
                    )
                    await sql.commit()

                    await self.refresh_fire_lists()

                    embed = discord.Embed(
                        title="Set",
                        description=f"Added {role.mention} to the role blacklist.",
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title="Fireboard is not enabled.", color=Color.red())

            await interaction.followup.send(embed=embed, ephemeral=True)

    # Fireboard role blacklist
    @fireSetupGroup.command(
        name="blacklists", description="View this server's role and channel blacklists."
    )
    async def fireboard_blacklists(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild_id in [guild[0] for guild in self.fire_settings]:

            class BlacklistViewer(View):
                def __init__(self):
                    super().__init__(timeout=240)

                    self.fire_channel_blacklist: list
                    self.fire_role_blacklist: list
                    self.interaction: discord.Interaction

                async def on_timeout(self) -> None:
                    for item in self.children:
                        item.disabled = True

                    await self.interaction.edit_original_response(view=self)

                @discord.ui.button(
                    label="Role Blacklist",
                    style=discord.ButtonStyle.gray,
                    row=0,
                    custom_id="role",
                    disabled=True,
                )
                async def role(
                    self, interaction: discord.Interaction, button: discord.ui.Button
                ):
                    await interaction.response.defer(ephemeral=True)

                    for item in self.children:
                        if item.custom_id == "channel":
                            item.disabled = False
                        else:
                            item.disabled = True

                    my_roles = []

                    for role in self.fire_channel_blacklist:
                        if role[0] == interaction.guild_id:
                            my_roles.append(f"<@&{role[1]}>")

                    if my_roles != []:
                        embed = discord.Embed(
                            title="Role Blacklist",
                            description="\n".join(my_roles),
                            color=Color.random(),
                        )
                        await interaction.edit_original_response(embed=embed, view=self)
                    else:
                        embed = discord.Embed(
                            title="Role Blacklist",
                            description="No roles have been blacklisted.",
                            color=Color.random(),
                        )
                        await interaction.edit_original_response(embed=embed, view=self)

                @discord.ui.button(
                    label="Channel Blacklist",
                    style=discord.ButtonStyle.gray,
                    row=0,
                    custom_id="channel",
                )
                async def channel(
                    self, interaction: discord.Interaction, button: discord.ui.Button
                ):
                    await interaction.response.defer(ephemeral=True)

                    for item in self.children:
                        if item.custom_id == "role":
                            item.disabled = False
                        else:
                            item.disabled = True

                    my_channels = []

                    for channel in self.fire_channel_blacklist:
                        if channel[0] == interaction.guild_id:
                            my_channels.append(f"<#{role[1]}>")

                    if my_channels != []:
                        embed = discord.Embed(
                            title="Channel Blacklist",
                            description="\n".join(my_channels),
                            color=Color.random(),
                        )
                        await interaction.edit_original_response(embed=embed, view=self)
                    else:
                        embed = discord.Embed(
                            title="Channel Blacklist",
                            description="No channels have been blacklisted.",
                            color=Color.random(),
                        )
                        await interaction.edit_original_response(embed=embed, view=self)

            view_instance = BlacklistViewer()
            view_instance.fire_channel_blacklist = self.fire_channel_blacklist
            view_instance.fire_role_blacklist = self.fire_role_blacklist
            view_instance.interaction = interaction

            my_roles = []

            for role in self.fire_role_blacklist:
                if role[0] == interaction.guild_id:
                    my_roles.append(f"<@&{role[1]}>")

            if my_roles != []:
                embed = discord.Embed(
                    title="Role Blacklist",
                    description="\n".join(my_roles),
                    color=Color.random(),
                )
                await interaction.followup.send(
                    embed=embed, view=view_instance, ephemeral=True
                )
            else:
                embed = discord.Embed(
                    title="Role Blacklist",
                    description="No roles have been blacklisted.",
                    color=Color.random(),
                )
                await interaction.followup.send(
                    embed=embed, view=view_instance, ephemeral=True
                )
        else:
            embed = discord.Embed(title="Fireboard is not enabled.", color=Color.red())

            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Fireboard(bot))
