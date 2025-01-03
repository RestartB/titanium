# pylint: disable=possibly-used-before-assignment

import asyncio

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
        self.fireboardPool: asqlite.Pool = bot.fireboardPool
        self.lockedMessages = []
        
        self.bot.loop.create_task(self.setup())
        self.bot.loop.create_task(self.refreshFireLists())
    
    # SQL Setup
    async def setup(self):
        async with self.fireboardPool.acquire() as sql:
            if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='fireMessages';") is None:
                # Fire Messages - messages that are active on the fireboard
                await sql.execute("CREATE TABLE fireMessages (serverID int, msgID int, boardMsgID int, reactAmount int)")
            
            if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='fireSettings';") is None:
                # Fire Settings - server properties for fireboard
                await sql.execute("CREATE TABLE fireSettings (serverID int, reactAmount int, emoji text, channelID int, ignoreBots int)")
            
            if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='fireChannelBlacklist';") is None:
                # Fire Channel Blacklist - blacklisted channels
                await sql.execute("CREATE TABLE fireChannelBlacklist (serverID int, channelID int)")
            
            if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='fireRoleBlacklist';") is None:
                # Fire Role Blacklist - blacklisted roles
                await sql.execute("CREATE TABLE fireRoleBlacklist (serverID int, roleID int)")
                
            await sql.commit()
    
    # List refresh function
    async def refreshFireLists(self):
        async with self.fireboardPool.acquire() as sql:
            self.fireMessages = await sql.fetchall("SELECT * FROM fireMessages")
            self.fireSettings = await sql.fetchall("SELECT * FROM fireSettings")
            self.fireChannelBlacklist = await sql.fetchall("SELECT * FROM fireChannelBlacklist")
            self.fireRoleBlacklist = await sql.fetchall("SELECT * FROM fireRoleBlacklist")

    # Listen for reactions
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        self.bot: discord.ext.commands.Bot
        
        # Stop if this is a DM
        if payload.guild_id == None:
            return
        
        queued = False
        
        # Lock system
        if payload.message_id in self.lockedMessages:
            queued = True

            while payload.message_id in self.lockedMessages:
                await asyncio.sleep(0.5)

        self.lockedMessages.append(payload.message_id)
        
        try:
            fetched = False
            
            # Find server config
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactMinimum = server[1]
                    emoji = server[2]
                    channelID = server[3]
                    ignoreBots = (True if int(server[4]) == 1 else False)

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
            if payload.message_id in [message[1] for message in self.fireMessages]:
                message = [message for message in self.fireMessages if message[1] == payload.message_id][0]
                
                # Only fetch updated reaction count if I have queued or reaction amount is undefined
                if queued or message[3] is None:
                    # Fetch message and channel
                    try:
                        msgChannel = await self.bot.fetch_channel(payload.channel_id)
                        message = await msgChannel.fetch_message(payload.message_id)
                    except discord.errors.NotFound:
                        return
                
                    # Stop if not enough reactions
                    for reaction in message.reactions:
                        if str(reaction.emoji) == emoji:
                            reactCount = reaction.count
                            break
                    
                    if reactCount < reactMinimum:
                        return
                else:
                    reactCount = None
                
                async with self.fireboardPool.acquire() as sql:
                    # Set updated react count
                    if reactCount is not None:
                        await sql.execute(f"UPDATE fireMessages SET reactionAmount = ? WHERE msgID = ?", (reactCount, payload.message_id,))
                        await self.refreshFireLists()
                    else:
                        await sql.execute(f"UPDATE fireMessages SET reactionAmount = reactionAmount + 1 WHERE msgID = ?", (payload.message_id,))
                        await self.refreshFireLists()

                # Get message from message list
                message = [message for message in self.fireMessages if message[1] == payload.message_id][0]

                # Get board message
                boardChannel = await self.bot.fetch_channel(channelID)
                boardMessage = await boardChannel.fetch_message(message[2])

                await boardMessage.edit(content=f"**{message[3]} {emoji}** | <@{payload.message_author_id}> | <#{payload.channel_id}>", embeds=boardMessage.embeds)

                return
            
            # Stop if message is in a blacklisted channel
            if payload.channel_id in [channel[1] for channel in self.fireChannelBlacklist]:
                return
            
            # Stop if message is by a blacklisted role
            guild = await self.bot.fetch_guild(payload.guild_id)
            member = await guild.fetch_member(payload.user_id)

            if any(role[1] in [role.id for role in member.roles] for role in self.fireRoleBlacklist):
                return
            
            # Fetch message and channel
            try:
                msgChannel = await self.bot.fetch_channel(payload.channel_id)
                message = await msgChannel.fetch_message(payload.message_id)
            except discord.errors.NotFound:
                return
            
            # Stop if message is by a bot
            if ignoreBots and message.author.bot:
                return
            
            # Stop if message is in an NSFW channel
            if message.channel.nsfw:
                return
            
            # Stop if not enough reactions
            for reaction in message.reactions:
                if str(reaction.emoji) == emoji:
                    reactCount = reaction.count
                    break
            
            if reactCount < reactMinimum:
                return

            # --- Send message to fireboard ---
            
            # Create embed
            embed = discord.Embed(description=message.content, color=Color.random())
            embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
            embed.timestamp = message.created_at

            # Jump to message button
            view = View()
            view.add_item(discord.ui.Button(label="Jump to Message", url = message.jump_url, style=discord.ButtonStyle.url))

            embedList = [embed]

            # Add reply embed
            if message.reference:
                try:
                    replyMessage = await msgChannel.fetch_message(message.reference.message_id)
                    
                    replyEmbed = discord.Embed(title="Replying To", description=replyMessage.content, color=Color.random())
                    replyEmbed.set_author(name=replyMessage.author.name, icon_url=replyMessage.author.display_avatar.url)
                    replyEmbed.timestamp = replyMessage.created_at

                    embedList.insert(0, replyEmbed)
                except discord.errors.NotFound:
                    pass
            
            # Send message
            boardChannel = await self.bot.fetch_channel(channelID)
            boardMessage = await boardChannel.send(content=f"**{reactCount} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view, files=[await attachment.to_file() for attachment in message.attachments])

            async with self.fireboardPool.acquire() as sql:
                # Insert message to DB
                await sql.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, reactionAmount) VALUES (?, ?, ?, ?)", (payload.guild_id, payload.message_id, boardMessage.id, reactCount))
                await sql.commit()

            await self.refreshFireLists()
        except Exception as e:
            raise e
        finally:
            self.lockedMessages.remove(payload.message_id)

    # Listen for reaction removal
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        self.bot: discord.ext.commands.Bot
        
        queued = False

        # Stop if this is a DM
        if payload.guild_id == None:
            return
        
        # Lock system
        if payload.message_id in self.lockedMessages:
            queued = True

            while payload.message_id in self.lockedMessages:
                await asyncio.sleep(0.5)

        self.lockedMessages.append(payload.message_id)
        
        try:
            fetched = False
            
            # Find server config
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactMinimum = server[1]
                    emoji = server[2]
                    channelID = server[3]
                    ignoreBots = (True if int(server[4]) == 1 else False)

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
            if payload.message_id in [message[1] for message in self.fireMessages]:
                prevReactCount = [message for message in self.fireMessages if message[1] == payload.message_id][0][3]
                
                # Only fetch updated reaction count if I have queued
                if queued or prevReactCount is None:
                    # Fetch message and channel
                    try:
                        msgChannel = await self.bot.fetch_channel(payload.channel_id)
                        message = await msgChannel.fetch_message(payload.message_id)
                    except discord.errors.NotFound:
                        return
                
                    # Stop if not enough reactions
                    for reaction in message.reactions:
                        if str(reaction.emoji) == emoji:
                            reactCount = reaction.count
                            break
                    
                    if reactCount < reactMinimum:
                        return
                else:
                    reactCount = None
                
                async with self.fireboardPool.acquire() as sql:
                    # Set updated react count
                    if reactCount is not None:
                        await sql.execute(f"UPDATE fireMessages SET reactionAmount = ? WHERE msgID = ?", (reactCount, payload.message_id,))
                        await self.refreshFireLists()
                    else:
                        await sql.execute(f"UPDATE fireMessages SET reactionAmount = reactionAmount - 1 WHERE msgID = ?", (payload.message_id,))
                        await self.refreshFireLists()

                # Get message from message list
                message = [message for message in self.fireMessages if message[1] == payload.message_id][0]

                # Get board message
                boardChannel = await self.bot.fetch_channel(channelID)
                boardMessage = await boardChannel.fetch_message(message[2])

                # Remove message if not enough reactions
                if message[3] < reactMinimum:
                    await boardMessage.delete()
                    
                    async with self.fireboardPool.acquire() as sql:
                        await sql.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                        await sql.commit()

                    await self.refreshFireLists()

                    return
                
                # Workaround for lack of message author ID
                content = boardMessage.content
                content = content.replace(f"{prevReactCount} {emoji}", f"{message[3]} {emoji}")
                
                await boardMessage.edit(content=content)

                return
            
            # Stop if message is in a blacklisted channel
            if payload.channel_id in [channel[1] for channel in self.fireChannelBlacklist]:
                return
            
            # Stop if message is by a blacklisted role
            guild = await self.bot.fetch_guild(payload.guild_id)
            member = await guild.fetch_member(payload.user_id)

            if any(role[1] in [role.id for role in member.roles] for role in self.fireRoleBlacklist):
                return

            # Fetch message and channel
            try:
                msgChannel = await self.bot.fetch_channel(payload.channel_id)
                message = await msgChannel.fetch_message(payload.message_id)
            except discord.errors.NotFound:
                return
            
            # Stop if message is by a bot
            if ignoreBots and message.author.bot:
                return
            
            # Stop if message is in an NSFW channel
            if message.channel.nsfw:
                return
            
            # Get reaction count
            reactCount = 0

            for reaction in message.reactions:
                if str(reaction.emoji) == emoji:
                    reactCount = reaction.count
                    break
            
            # Stop if not enough reactions
            if reactCount < reactMinimum:
                return

            # --- Send message to fireboard ---
            
            # Create embed
            embed = discord.Embed(description=message.content, color=Color.random())
            embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
            embed.timestamp = message.created_at

            # Jump to message button
            view = View()
            view.add_item(discord.ui.Button(label="Jump to Message", url = message.jump_url, style=discord.ButtonStyle.url))

            embedList = [embed]

            # Add reply embed
            if message.reference:
                try:
                    replyMessage = await msgChannel.fetch_message(message.reference.message_id)
                    
                    replyEmbed = discord.Embed(title="Replying To", description=replyMessage.content, color=Color.random())
                    replyEmbed.set_author(name=replyMessage.author.name, icon_url=replyMessage.author.display_avatar.url)
                    replyEmbed.timestamp = replyMessage.created_at

                    embedList.insert(0, replyEmbed)
                except discord.errors.NotFound:
                    pass
            
            # Send message
            boardChannel = await self.bot.fetch_channel(channelID)
            boardMessage = await boardChannel.send(content=f"**{reactCount} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view, files=[await attachment.to_file() for attachment in message.attachments])

            async with self.fireboardPool.acquire() as sql:
                # Insert message to DB
                await sql.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, reactionAmount) VALUES (?, ?, ?, ?)", (payload.guild_id, payload.message_id, boardMessage.id, reactCount))
                await sql.commit()

            await self.refreshFireLists()
        except Exception as e:
            raise e
        finally:
            self.lockedMessages.remove(payload.message_id)
    
    # Listen for message reaction clear
    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionClearEvent):
        self.bot: discord.ext.commands.Bot
        
        queued = False

        # Stop if this is a DM
        if payload.guild_id == None:
            return
        
        # Lock system
        if payload.message_id in self.lockedMessages:
            queued = True

            while payload.message_id in self.lockedMessages:
                await asyncio.sleep(0.5)

        self.lockedMessages.append(payload.message_id)
        
        try:
            # Only trigger if message is already in the fireboard DB
            if payload.message_id in [message[1] for message in self.fireMessages]:
                # Find server config
                for server in self.fireSettings:
                    if server[0] == payload.guild_id:
                        reactMinimum = server[1]
                        emoji = server[2]
                        channelID = server[3]
                        ignoreBots = (True if int(server[4]) == 1 else False)
                
                # Get guild
                try:
                    guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                except discord.errors.NotFound:
                    return

                # Get message channel
                channel: discord.abc.GuildChannel = await guild.fetch_channel(payload.channel_id)

                # Get our message
                message: discord.Message = await channel.fetch_message(payload.message_id)

                # See if board message is already present
                for fireMessage in self.fireMessages:
                    if fireMessage[1] == message.id:
                        async with self.fireboardPool.acquire() as sql:
                            try:
                                # Delete message
                                try:
                                    channel: discord.TextChannel = await guild.fetch_channel(channelID)
                                except discord.errors.NotFound:
                                    await sql.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                                    await sql.commit()
                                    self.lockedMessages.remove(payload.message_id)
                                    
                                    return
                                
                                boardMessage = await channel.fetch_message(fireMessage[2])
                                await boardMessage.delete()

                                # Delete message from DB
                                await sql.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                await sql.commit()

                                await self.refreshFireLists()

                                return
                            except discord.errors.NotFound:
                                # Delete message from DB
                                await sql.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                await sql.commit()

                                await self.refreshFireLists()

                                return
            else:
                return
        except Exception as e:
            raise e
        finally:
            self.lockedMessages.remove(payload.message_id)
    
    # Listen for specific emoji being cleared
    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(self, payload: discord.RawReactionClearEmojiEvent):
        self.bot: discord.ext.commands.Bot
        
        queued = False

        # Stop if this is a DM
        if payload.guild_id == None:
            return
        
        # Lock system
        if payload.message_id in self.lockedMessages:
            queued = True

            while payload.message_id in self.lockedMessages:
                await asyncio.sleep(0.5)

        self.lockedMessages.append(payload.message_id)
        
        try:
            # Only trigger if message is already in the fireboard DB
            if payload.message_id in [message[1] for message in self.fireMessages]:
                for server in self.fireSettings:
                    if server[0] == payload.guild_id:
                        reactMinimum = server[1]
                        emoji = server[2]
                        channelID = server[3]
                        ignoreBots = (True if int(server[4]) == 1 else False)
                
                # Only trigger if cleared emoji is our emoji
                if str(payload.emoji) == emoji:
                    # Fetch server
                    try:
                        guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                    except discord.errors.NotFound:
                        return

                    # Get message channel
                    channel: discord.abc.GuildChannel = await guild.fetch_channel(payload.channel_id)

                    # See if board message is already present
                    for fireMessage in self.fireMessages:
                        if fireMessage[1] == payload.message_id:
                            async with self.fireboardPool.acquire() as sql:
                                try:
                                    # Fetch fireboard channel
                                    try:
                                        channel: discord.TextChannel = await guild.fetch_channel(channelID)
                                    except discord.errors.NotFound:
                                        await sql.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                                        await sql.commit()
                                        
                                        return
                                    
                                    # Delete message
                                    boardMessage = await channel.fetch_message(fireMessage[2])
                                    await boardMessage.delete()

                                    # Delete message from DB
                                    await sql.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                                    await sql.commit()

                                    await self.refreshFireLists()

                                    return
                                except discord.errors.NotFound:
                                    # Delete message from DB
                                    await sql.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                                    await sql.commit()

                                    await self.refreshFireLists()

                                    return
            else:
                return
        except Exception as e:
            raise e
        finally:
            self.lockedMessages.remove(payload.message_id)
    
    # Listen for message being deleted
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        self.bot: discord.ext.commands.Bot
        
        queued = False

        # Stop if this is a DM
        if payload.guild_id == None:
            return
        
        # Lock system
        if payload.message_id in self.lockedMessages:
            queued = True

            while payload.message_id in self.lockedMessages:
                await asyncio.sleep(0.5)

        self.lockedMessages.append(payload.message_id)
        
        try:
            # Only trigger if message is already in the fireboard DB
            if payload.message_id in [message[1] for message in self.fireMessages]:
                # Fetch server config
                for server in self.fireSettings:
                    if server[0] == payload.guild_id:
                        reactMinimum = server[1]
                        emoji = server[2]
                        channelID = server[3]
                        ignoreBots = (True if int(server[4]) == 1 else False)
                
                # Fetch server
                try:
                    guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                except discord.errors.NotFound:
                    return

                # Get message channel
                channel: discord.abc.GuildChannel = await guild.fetch_channel(payload.channel_id)

                # See if board message is already present
                for fireMessage in self.fireMessages:
                    if fireMessage[1] == payload.message_id:
                        async with self.fireboardPool.acquire() as sql:
                            try:
                                # Fetch fireboard channel
                                try:
                                    channel: discord.TextChannel = await guild.fetch_channel(channelID)
                                except discord.errors.NotFound:
                                    await sql.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                                    await sql.commit()
                                    
                                    return
                                
                                # Delete message
                                boardMessage = await channel.fetch_message(fireMessage[2])
                                await boardMessage.delete()

                                # Delete message from DB
                                await sql.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                                await sql.commit()

                                await self.refreshFireLists()

                                return
                            except discord.errors.NotFound:
                                # Delete message from DB
                                await sql.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                                await sql.commit()

                                await self.refreshFireLists()

                                return
            else:
                return
        except Exception as e:
            raise e
        finally:
            self.lockedMessages.remove(payload.message_id)
    
    # Listen for message being edited
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        self.bot: discord.ext.commands.Bot
        
        queued = False

        # Stop if this is a DM
        if payload.guild_id == None:
            return
        
        # Lock system
        if payload.message_id in self.lockedMessages:
            queued = True

            while payload.message_id in self.lockedMessages:
                await asyncio.sleep(0.5)

        self.lockedMessages.append(payload.message_id)

        try:
            # Only trigger if message is already in the fireboard DB
            if payload.message_id in [message[1] for message in self.fireMessages]:
                # Fetch server config
                for server in self.fireSettings:
                    if server[0] == payload.guild_id:
                        reactMinimum = server[1]
                        emoji = server[2]
                        channelID = server[3]
                        ignoreBots = (True if int(server[4]) == 1 else False)
                
                # Fetch server
                try:
                    guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                except discord.errors.NotFound:
                    return
                
                # Get message channel
                channel: discord.abc.GuildChannel = await guild.fetch_channel(payload.channel_id)

                # Get our message
                message: discord.Message = await channel.fetch_message(payload.message_id)
                
                embed = discord.Embed(description=message.content, color=Color.random())
                embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
                embed.timestamp = message.created_at

                # Jump to message button
                view = View()
                view.add_item(discord.ui.Button(label="Jump to Message", url = message.jump_url, style=discord.ButtonStyle.url))

                embedList = [embed]
                
                # Add reply embed
                if message.reference:
                    try:
                        replyMessage = await channel.fetch_message(message.reference.message_id)
                        
                        replyEmbed = discord.Embed(title="Replying To", description=replyMessage.content, color=Color.random())
                        replyEmbed.set_author(name=replyMessage.author.name, icon_url=replyMessage.author.display_avatar.url)
                        replyEmbed.timestamp = replyMessage.created_at

                        embedList.insert(0, replyEmbed)
                    except discord.errors.NotFound:
                        pass
                
                try:
                    channel: discord.TextChannel = await guild.fetch_channel(channelID)
                except discord.errors.NotFound:
                    async with self.fireboardPool.acquire() as sql:
                        await sql.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                        await sql.commit()
                        
                    return
                
                # Find previous fireboard message
                try:
                    for fireMessage in self.fireMessages:
                        if fireMessage[0] == payload.guild_id and fireMessage[1] == payload.message_id:
                            # Edit with updated embed - reaction amount stays the same
                            boardMessage = await channel.fetch_message(fireMessage[2])

                            await boardMessage.edit(embeds=embedList, files=message.attachments)
                except discord.errors.NotFound: # Message not found
                    async with self.fireboardPool.acquire() as sql:
                        # Delete message from DB
                        await sql.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                        await sql.commit()

                        await self.refreshFireLists()

                    return
            else:
                return
        except Exception as e:
            raise e
        finally:
            self.lockedMessages.remove(payload.message_id)
    
    # Listen for fireboard channel delete
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        # Only trigger if server has fireboard enabled
        if channel.guild.id in [guild[0] for guild in self.fireSettings]:
            for server in self.fireSettings:
                if server[0] == channel.guild.id:
                    if server[3] == channel.id:
                        async with self.fireboardPool.acquire() as sql:
                            # Delete fireboard config
                            await sql.execute(f"DELETE FROM fireMessages WHERE serverID = ?", (channel.guild.id,))
                            await sql.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (channel.guild.id,))
                            await sql.commit()

                        await self.refreshFireLists()

                        return
        else:
            return
    
    # Listen for server being left / deleted
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        # Only trigger if server has fireboard enabled
        if guild.id in [guild[0] for guild in self.fireSettings]:
            for server in self.fireSettings:
                if server[0] == guild.id:
                    async with self.fireboardPool.acquire() as sql:
                        # Delete fireboard config
                        await sql.execute(f"DELETE FROM fireMessages WHERE serverID = ?", (guild.id,))
                        await sql.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (guild.id,))
                        await sql.commit()

                    await self.refreshFireLists()

                    return
        else:
            return
    
    # Command group setup
    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False)
    perms = discord.Permissions()
    fireGroup = app_commands.Group(name="fireboard", description="Control the fireboard.", allowed_contexts=context, default_permissions=perms)
    
    # Fireboard enable command
    @fireGroup.command(name="enable", description="Enable the fireboard in the current channel.")
    async def enableFireboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fireSettings]:
            embed = discord.Embed(title = "Fireboard is already enabled.", color=Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Default settings
            reactMinimum = 3
            emoji = "🔥"
            channelID = interaction.channel_id
            ignoreBots = True

            embed = discord.Embed(title = "Fireboard", description="This channel has been configured as the server fireboard.", color=Color.random())
            embed.set_footer(text = "Feel free to delete this message!")

            try:
                channel = await interaction.guild.fetch_channel(channelID)
                await channel.send(embed = embed)
            except discord.errors.Forbidden or discord.errors.NotFound:
                embed = discord.Embed(title = "Error", description="Looks like I can't send messages in this channel. Check permissions and try again.", color=Color.random())
                await interaction.followup.send(embed=embed, ephemeral=True)

                return
            
            async with self.fireboardPool.acquire() as sql:
                # Insert to DB, refresh lists
                await sql.execute(f"INSERT INTO fireSettings (serverID, reactAmount, emoji, channelID, ignoreBots) VALUES (?, ?, ?, ?, ?)", (interaction.guild_id, reactMinimum, emoji, channelID, ignoreBots,))
                await sql.commit()

            await self.refreshFireLists()
            
            embed = discord.Embed(title = "Enabled", description="Fireboard has been enabled in the current channel.", color=Color.green())
            embed.add_field(name="Info", value=f"**Reaction Requirement:** `{reactMinimum} reactions`\n**Fireboard Channel:** <#{channelID}>\n**Emoji:** {emoji}\n**Ignore Bots:** `{ignoreBots}`")

            await interaction.followup.send(embed=embed, ephemeral=True)
    
    class ConfirmDisableView(View):
        def __init__(self):
            super().__init__(timeout=60)
            
        async def disable_fireboard(self, interaction: discord.Interaction, pool: asqlite.Pool):
            async with pool.acquire() as sql:
                try:
                    await sql.execute("DELETE FROM fireMessages WHERE serverID = ?", (interaction.guild_id,))
                    await sql.execute("DELETE FROM fireSettings WHERE serverID = ?", (interaction.guild_id,))
                    await sql.execute("DELETE FROM fireChannelBlacklist WHERE serverID = ?", (interaction.guild_id,))
                    await sql.execute("DELETE FROM fireRoleBlacklist WHERE serverID = ?", (interaction.guild_id,))
                    await sql.commit()
                    return True
                except Exception:
                    return False

        @discord.ui.button(label='Disable', style=discord.ButtonStyle.red)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=True)
            
            success = await self.disable_fireboard(interaction, self.pool)
            
            if success:
                embed = discord.Embed(title="Done!", description="Fireboard was disabled.", color=Color.green())
                await self.cog.refreshFireLists() # pylint: disable=no-member
            else:
                embed = discord.Embed(title="Error", description="Failed to disable fireboard.", color=Color.red())
            
            await interaction.edit_original_response(embed=embed, view=None)
            self.stop()

        async def on_timeout(self):
            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(title="Timeout", description="You didn't press the button in time.", color=Color.red())
            await self.message.edit(embed=embed, view=self)
    
    # Fireboard disable command
    @fireGroup.command(name="disable", description="Disable the server fireboard.")
    async def disableFireboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if interaction.guild_id in [guild[0] for guild in self.fireSettings]:
            view = self.ConfirmDisableView()
            view.pool = self.fireboardPool
            view.cog = self
            
            embed = discord.Embed(
                title="Are you sure?", 
                description="All data about this server's fireboard will be deleted. This cannot be undone!",
                color=Color.orange()
            )
            
            message = await interaction.followup.send(embed=embed, view=view, ephemeral=True, wait=True)
            view.message = message
        else:
            await interaction.followup.send("Fireboard is not enabled in this server!", ephemeral=True)
    
    # Fireboard server info command
    @fireGroup.command(name="info", description="View fireboard config for this server.")
    async def fireboardInfo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fireSettings]:
            # Fetch server settings
            for server in self.fireSettings:
                if server[0] == interaction.guild_id:
                    reactMinimum = server[1]
                    emoji = server[2]
                    channelID = server[3]
                    ignoreBots = (True if int(server[4]) == 1 else False)
            
            embed = discord.Embed(title="Server Fireboard Settings", description=f"**Reaction Requirement:** `{reactMinimum} reactions`\n**Fireboard Channel:** <#{channelID}>\n**Emoji:** {emoji}\n**Ignore Bots:** `{ignoreBots}`", color=Color.random())

            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title = "Fireboard is not enabled.", color=Color.green())

            await interaction.followup.send(embed=embed, ephemeral=True)
                
    # Fireboard set emoji command
    @fireGroup.command(name="emoji", description="Set a custom fireboard emoji.")
    async def fireboardEmoji(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        
        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fireSettings]:
            embed = discord.Embed(title = "Waiting for Reaction", description=f"{self.bot.options['loading-emoji']} React with this message with your target emoji to set the fireboard emoji.", color=Color.orange())
            
            msg = await interaction.followup.send(embed=embed, ephemeral=False)

            def check(reaction, user):
                return user == interaction.user and reaction.message.id == msg.id
                
            # Wait for a reaction
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                reaction: discord.Reaction = reaction
                
                async with self.fireboardPool.acquire() as sql:
                    # Change emoji in DB, refresh lists
                    await sql.execute(f"UPDATE fireSettings SET emoji = ? WHERE serverID = ?", (str(reaction.emoji), interaction.guild_id,))
                    await sql.commit()
                
                embed = discord.Embed(title = "Emoji Set", description=f"Set emoji to **{str(reaction.emoji)}.**", color=Color.green())
                
                await self.refreshFireLists()
                await interaction.edit_original_response(embed=embed)
            except asyncio.TimeoutError: # Timed out
                embed = discord.Embed(title = "Timed Out", description="You didn't react in time.", color=Color.red())
                
                await interaction.edit_original_response(embed=embed)
        else:
            embed = discord.Embed(title = "Fireboard is not enabled.", color=Color.green())

            await interaction.followup.send(embed=embed, ephemeral=False)
    
    # Fireboard set channel command
    @fireGroup.command(name="channel", description="Set the channel for fireboard messages to be sent in.")
    async def fireboardChannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        
        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fireSettings]:
            embed = discord.Embed(title = "Fireboard", description="This channel has been configured as the server fireboard.", color=Color.random())
            embed.set_footer(text = "Feel free to delete this message!")

            try:
                await channel.send(embed = embed)
            except discord.errors.NotFound as e:
                embed = discord.Embed(title = "Error", description="Looks like I can't find that channel. Check permissions and try again.", color=Color.random())
                await interaction.followup.send(embed=embed, content = e, ephemeral=True)

                return
            except discord.errors.Forbidden as e:
                embed = discord.Embed(title = "Error", description="Looks like I can't send messages in that channel. Check permissions and try again.", color=Color.random())
                await interaction.followup.send(embed=embed, content=e, ephemeral=True)

                return
            
            async with self.fireboardPool.acquire() as sql:
                # Update channel in DB, refresh lists
                await sql.execute(f"UPDATE fireSettings SET channelID = ? WHERE serverID = ?", (channel.id, interaction.guild_id,))
                await sql.commit()

            await self.refreshFireLists()
            
            embed = discord.Embed(title="Channel Set", description=f"Fireboard channel has been set to **{channel.mention}.**", color=Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title = "Fireboard is not enabled.", color=Color.green())

            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Fireboard set requirement command
    @fireGroup.command(name="requirement", description="Set required reaction amount for message to be posted on the fireboard.")
    async def fireboardRequirement(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        
        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fireSettings]:
            embed = discord.Embed(title="Set", description=f"Reaction requirement has been set to **{amount} reactions.**", color=Color.green())

            async with self.fireboardPool.acquire() as sql:
                # Update reaction requirement in DB, refresh lists
                await sql.execute(f"UPDATE fireSettings SET reactAmount = ? WHERE serverID = ?", (amount, interaction.guild_id,))
                await sql.commit()

            await self.refreshFireLists()
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title = "Fireboard is not enabled.", color=Color.green())

            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Fireboard ignore bots command
    @fireGroup.command(name="ignore-bots", description="Whether bot messages are ignored in the fireboard. Defaults to true.")
    async def fireboardIgnoreBots(self, interaction: discord.Interaction, value: bool):
        await interaction.response.defer(ephemeral=True)
        
        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fireSettings]:
            embed = discord.Embed(title="Set", description=f"Bot messages will **{"be ignored." if value else "not be ignored."}**", color=Color.green())

            async with self.fireboardPool.acquire() as sql:
                # Update setting in DB, refresh lists
                await sql.execute(f"UPDATE fireSettings SET ignoreBots = ? WHERE serverID = ?", (value, interaction.guild_id,))
                await sql.commit()

            await self.refreshFireLists()
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title = "Fireboard is not enabled.", color=Color.green())

            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Fireboard role blacklist
    @fireGroup.command(name="channel-blacklist", description="Toggle the blacklist for a channel. NSFW channels are always blacklisted.")
    async def fireboardChannelBlacklist(self, interaction: discord.Interaction, channel: discord.abc.GuildChannel):
        await interaction.response.defer(ephemeral=True)
        
        # Check fireboard status
        if interaction.guild_id in [guild[0] for guild in self.fireSettings]:
            async with self.fireboardPool.acquire() as sql:
                if channel.id in [channelEntry[1] for channelEntry in self.fireChannelBlacklist]:
                    await sql.execute("DELETE FROM fireChannelBlacklist WHERE serverID = ? AND channelID = ?", (interaction.guild_id, channel.id,))
                    await sql.commit()

                    await self.refreshFireLists()
                    
                    embed = discord.Embed(title = "Set", description = f"Removed {channel.mention} from the channel blacklist.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await sql.execute(f"INSERT INTO fireChannelBlacklist (serverID, channelID) VALUES (?, ?)", (interaction.guild_id, channel.id,))
                    await sql.commit()

                    await self.refreshFireLists()
                    
                    embed = discord.Embed(title = "Set", description = f"Added {channel.mention} to the channel blacklist.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title = "Fireboard is not enabled.", color=Color.green())

            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Fireboard role blacklist
    @fireGroup.command(name="role-blacklist", description="Toggle the blacklist for a role.")
    async def fireboardRoleBlacklist(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        
        # Check fireboard status
        if interaction.guild_id in [guild[0] for guild in self.fireSettings]:
            async with self.fireboardPool.acquire() as sql:
                if role.id in [roleEntry[1] for roleEntry in self.fireRoleBlacklist]:
                    await sql.execute("DELETE FROM fireRoleBlacklist WHERE serverID = ? AND roleID = ?", (interaction.guild_id, role.id,))
                    await sql.commit()

                    await self.refreshFireLists()
                    
                    embed = discord.Embed(title = "Set", description = f"Removed {role.mention} from the role blacklist.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await sql.execute(f"INSERT INTO fireRoleBlacklist (serverID, roleID) VALUES (?, ?)", (interaction.guild_id, role.id,))
                    await sql.commit()

                    await self.refreshFireLists()
                    
                    embed = discord.Embed(title = "Set", description = f"Added {role.mention} to the role blacklist.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(title = "Fireboard is not enabled.", color=Color.green())

            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Fireboard role blacklist
    @fireGroup.command(name="blacklists", description="View this server's role and channel blacklists.")
    async def fireboardBlacklists(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check fireboard status
        if interaction.guild_id in [guild[0] for guild in self.fireSettings]:
            class BlacklistViewer(View):
                def __init__(self):
                    super().__init__(timeout=240)

                    self.fireChannelBlacklist: list
                    self.fireRoleBlacklist: list
                    self.interaction: discord.Interaction
                
                async def on_timeout(self) -> None:
                    for item in self.children:
                        item.disabled = True
                    
                    await self.interaction.edit_original_response(view=self)
                
                @discord.ui.button(label=f'Role Blacklist', style=discord.ButtonStyle.gray, row = 0, custom_id="role", disabled=True)
                async def role(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer(ephemeral=True)
                    
                    for item in self.children:
                        if item.custom_id == "channel":
                            item.disabled = False
                        else:
                            item.disabled = True
                    
                    myRoles = []
                    
                    for role in self.fireRoleBlacklist:
                        if role[0] == interaction.guild_id:
                            myRoles.append(f"<@&{role[1]}>")
                    
                    if myRoles != []:
                        embed = discord.Embed(title="Role Blacklist", description="\n".join(myRoles), color=Color.random())
                        await interaction.edit_original_response(embed=embed, view=self)
                    else:
                        embed = discord.Embed(title="Role Blacklist", description="No roles have been blacklisted.", color=Color.random())
                        await interaction.edit_original_response(embed=embed, view=self)
                
                @discord.ui.button(label=f'Channel Blacklist', style=discord.ButtonStyle.gray, row = 0, custom_id="channel")
                async def channel(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer(ephemeral=True)
                    
                    for item in self.children:
                        if item.custom_id == "role":
                            item.disabled = False
                        else:
                            item.disabled = True
                    
                    myChannels = []
                    
                    for channel in self.fireChannelBlacklist:
                        if channel[0] == interaction.guild_id:
                            myChannels.append(f"<#{role[1]}>")
                    
                    if myChannels != []:
                        embed = discord.Embed(title="Channel Blacklist", description="\n".join(myChannels), color=Color.random())
                        await interaction.edit_original_response(embed=embed, view=self)
                    else:
                        embed = discord.Embed(title="Channel Blacklist", description="No channels have been blacklisted.", color=Color.random())
                        await interaction.edit_original_response(embed=embed, view=self)
            
            viewInstance = BlacklistViewer()
            viewInstance.fireChannelBlacklist = self.fireChannelBlacklist
            viewInstance.fireRoleBlacklist = self.fireRoleBlacklist
            viewInstance.interaction = interaction
            
            myRoles = []
            
            for role in self.fireRoleBlacklist:
                if role[0] == interaction.guild_id:
                    myRoles.append(f"<@&{role[1]}>")
            
            if myRoles != []:
                embed = discord.Embed(title="Role Blacklist", description="\n".join(myRoles), color=Color.random())
                await interaction.followup.send(embed=embed, view=viewInstance, ephemeral=True)
            else:
                embed = discord.Embed(title="Role Blacklist", description="No roles have been blacklisted.", color=Color.random())
                await interaction.followup.send(embed=embed, view=viewInstance, ephemeral=True)
        else:
            embed = discord.Embed(title = "Fireboard is not enabled.", color=Color.green())

            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Fireboard(bot))
