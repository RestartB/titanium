# pylint: disable=possibly-used-before-assignment

import asyncio
import os
import sqlite3

import discord
import discord.ext
import discord.ext.commands
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View


class fireboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lockedMessages = []
        
        # Check DB exists
        open(os.path.join("content", "sql", "fireboard.db"), "a").close()
        
        self.connection = sqlite3.connect(os.path.join("content", "sql", "fireboard.db"))
        self.cursor = self.connection.cursor()
        
        if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='fireMessages';").fetchone() == None:
            # Fire Messages - messages that are active on the fireboard
            self.cursor.execute("CREATE TABLE fireMessages (serverID int, msgID int, boardMsgID int, emoji text)")
        
        if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='fireSettings';").fetchone() == None:
            # Fire Settings - server properties for fireboard
            self.cursor.execute("CREATE TABLE fireSettings (serverID int, reactAmount int, emoji text, channelID int, ignoreBots int)")
        
        if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='fireChannelBlacklist';").fetchone() == None:
            # Fire Channel Blacklist - blacklisted channels
            self.cursor.execute("CREATE TABLE fireChannelBlacklist (serverID int, channelID int)")
        
        if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='fireRoleBlacklist';").fetchone() == None:
            # Fire Role Blacklist - blacklisted roles
            self.cursor.execute("CREATE TABLE fireRoleBlacklist (serverID int, roleID int)")
            
        self.connection.commit()
        
        self.fireMessages = self.cursor.execute("SELECT * FROM fireMessages").fetchall()
        self.fireSettings = self.cursor.execute("SELECT * FROM fireSettings").fetchall()
        self.fireChannelBlacklist = self.cursor.execute("SELECT * FROM fireChannelBlacklist").fetchall()
        self.fireRoleBlacklist = self.cursor.execute("SELECT * FROM fireRoleBlacklist").fetchall()
    
    # List refresh function
    async def refreshFireLists(self):
        self.fireMessages = self.cursor.execute("SELECT * FROM fireMessages").fetchall()
        self.fireSettings = self.cursor.execute("SELECT * FROM fireSettings").fetchall()
        self.fireChannelBlacklist = self.cursor.execute("SELECT * FROM fireChannelBlacklist").fetchall()
        self.fireRoleBlacklist = self.cursor.execute("SELECT * FROM fireRoleBlacklist").fetchall()

    # Listen for reactions
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        self.bot: discord.ext.commands.Bot
        
        # Lock system
        if payload.message_id not in self.lockedMessages:
            self.lockedMessages.append(payload.message_id)
        else:
            while payload.message_id in self.lockedMessages:
                pass

            self.lockedMessages.append(payload.message_id)
        
        # Check if message is from bot
        if payload.message_author_id != self.bot.user.id:
            # Get blacklisted roles
            blacklistedRoles = []
            for entry in self.fireRoleBlacklist:
                if entry[0] == payload.guild_id:
                    blacklistedRoles.append(entry[1])
            
            # Check if member's roles are blacklisted
            guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
            member: discord.Guild = await guild.fetch_member(payload.message_author_id)
            for role in member.roles:
                if role.id in blacklistedRoles:
                    self.lockedMessages.remove(payload.message_id)
                    return
                
            # Get blacklisted channels
            blacklistedChannels = []
            for entry in self.fireChannelBlacklist:
                if entry[0] == payload.guild_id:
                    blacklistedChannels.append(entry[1])
            
            # Check if channel is blacklisted
            if payload.channel_id not in blacklistedChannels:
                # Only trigger if server has fireboard enabled
                if payload.guild_id in [guild[0] for guild in self.fireSettings]:
                    # Find server config
                    for server in self.fireSettings:
                        if server[0] == payload.guild_id:
                            reactAmount = server[1]
                            emoji = server[2]
                            channelID = server[3]
                            ignoreBots = (True if int(server[4]) == 1 else False)
                    
                    # Check if emoji is correct
                    if str(payload.emoji) == emoji:
                        if not(ignoreBots and payload.member.bot):
                            # Get message channel
                            channel: discord.abc.GuildChannel = await guild.fetch_channel(payload.channel_id)
                            
                            # Stop if channel is NSFW
                            if channel.nsfw == True:
                                self.lockedMessages.remove(payload.message_id)
                                return

                            # Get our message
                            message: discord.Message = await channel.fetch_message(payload.message_id)

                            # See if the target reaction is present
                            for reaction in message.reactions:
                                if str(reaction.emoji) == str(emoji):
                                    if (reaction.normal_count + reaction.burst_count) >= reactAmount:
                                        embed = discord.Embed(description=message.content, color=Color.random())
                                        embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
                                        embed.timestamp = message.created_at

                                        # Jump to message button
                                        view = View()
                                        view.add_item(discord.ui.Button(label="Jump to Message", url = message.jump_url, style=discord.ButtonStyle.url))

                                        embedList = [embed]
                                        
                                        # Show message reply
                                        if message.reference:
                                            try:
                                                replyMessage = await channel.fetch_message(message.reference.message_id)
                                                
                                                replyEmbed = discord.Embed(title="Replying To", description=replyMessage.content, color=Color.random())
                                                replyEmbed.set_author(name=replyMessage.author.name, icon_url=replyMessage.author.display_avatar.url)
                                                replyEmbed.timestamp = replyMessage.created_at

                                                embedList.insert(0, replyEmbed)
                                            except discord.errors.NotFound:
                                                pass
                                        
                                        # Grab fireboard channel, remove server config if it doesn't exist
                                        try:
                                            channel: discord.TextChannel = await guild.fetch_channel(channelID)
                                        except discord.errors.NotFound:
                                            self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                                            self.connection.commit()

                                            self.lockedMessages.remove(payload.message_id)

                                            return
                                        
                                        # See if board message is already present
                                        for fireMessage in self.fireMessages:
                                            if fireMessage[1] == message.id:
                                                if str(reaction.emoji) == fireMessage[3]: # Emoji is up to date and message is present - edit message
                                                    try:
                                                        boardMessage = await channel.fetch_message(fireMessage[2])
                                                        
                                                        await boardMessage.edit(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList)
                                                    except discord.errors.NotFound:
                                                        boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view, files=[await attachment.to_file() for attachment in message.attachments])
                                                        
                                                        # Delete old message
                                                        self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                                        self.connection.commit()
                                                        
                                                        # Insert message
                                                        self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                                        self.connection.commit()

                                                        await self.refreshFireLists()

                                                    self.lockedMessages.remove(payload.message_id)
                                                    
                                                    return
                                                else: # Emoji is outdated - resend the message and delete the old one     
                                                    boardMessage = await channel.fetch_message(fireMessage[2])
                                                    await boardMessage.delete()

                                                    boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view, files=[await attachment.to_file() for attachment in message.attachments])

                                                    # Delete old message
                                                    self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                                    self.connection.commit()
                                                    
                                                    # Insert message
                                                    self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                                    self.connection.commit()

                                                    await self.refreshFireLists()

                                                    self.lockedMessages.remove(payload.message_id)
                                                    
                                                    return
                                        
                                        boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view, files=[await attachment.to_file() for attachment in message.attachments])

                                        # Insert message
                                        self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                        self.connection.commit()

                                        await self.refreshFireLists()

                                        self.lockedMessages.remove(payload.message_id)
                        else:
                            self.lockedMessages.remove(payload.message_id)
                            return
                    else:
                        self.lockedMessages.remove(payload.message_id)
                        return
                else:
                    self.lockedMessages.remove(payload.message_id)
                    return
            else:
                self.lockedMessages.remove(payload.message_id)
                return
        else:
            self.lockedMessages.remove(payload.message_id)
            return

    # Listen for reaction removal
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        self.bot: discord.ext.commands.Bot
        
        # Lock system
        if payload.message_id not in self.lockedMessages:
            self.lockedMessages.append(payload.message_id)
        else:
            while payload.message_id in self.lockedMessages:
                pass

            self.lockedMessages.append(payload.message_id)
        
        if payload.message_author_id != self.bot.user.id:
            # Only trigger if message is already in the fireboard DB
            if payload.message_id in [message[1] for message in self.fireMessages]:
                # Get server config
                for server in self.fireSettings:
                    if server[0] == payload.guild_id:
                        reactAmount = server[1]
                        emoji = server[2]
                        channelID = server[3]
                        ignoreBots = (True if int(server[4]) == 1 else False)
                
                if str(payload.emoji) == emoji:
                    try:
                        guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                    except discord.errors.NotFound:
                        self.lockedMessages.remove(payload.message_id)
                        
                        return

                    # Get message channel
                    channel: discord.abc.GuildChannel = await guild.fetch_channel(payload.channel_id)

                    # Stop if channel is NSFW
                    if channel.nsfw == True:
                        self.lockedMessages.remove(payload.message_id)
                        
                        return
                    
                    # Get our message
                    message: discord.Message = await channel.fetch_message(payload.message_id)

                    if emoji in [str(reaction.emoji) for reaction in message.reactions]:
                        # See if the target reaction is present
                        for reaction in message.reactions:
                            if str(reaction.emoji) == str(emoji):
                                if (reaction.normal_count + reaction.burst_count) < reactAmount: # Message illegible for fireboard
                                    # See if board message is already present
                                    for fireMessage in self.fireMessages:
                                        if fireMessage[1] == message.id:
                                            try:
                                                # Grab fireboard channel
                                                try:
                                                    channel: discord.TextChannel = await guild.fetch_channel(channelID)
                                                except discord.errors.NotFound:
                                                    self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                                                    self.connection.commit()
                                                    
                                                    self.lockedMessages.remove(payload.message_id)
                                                    
                                                    return
                                                
                                                # Delete old message
                                                boardMessage = await channel.fetch_message(fireMessage[2])
                                                await boardMessage.delete()

                                                # Delete message from DB
                                                self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                                self.connection.commit()

                                                await self.refreshFireLists()

                                                self.lockedMessages.remove(payload.message_id)
                                                
                                                return
                                            except discord.errors.NotFound:
                                                # Delete message from DB
                                                self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                                self.connection.commit()

                                                await self.refreshFireLists()

                                                self.lockedMessages.remove(payload.message_id)
                                                
                                                return
                                    
                                    self.lockedMessages.remove(payload.message_id)
                                    
                                    return
                                else: # Message still legible for fireboard
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
                                    
                                    # Fetch fireboard channel
                                    try:
                                        channel: discord.TextChannel = await guild.fetch_channel(channelID)
                                    except discord.errors.NotFound:
                                        self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                                        self.connection.commit()
                                        
                                        self.lockedMessages.remove(payload.message_id)
                                        
                                        return
                                    
                                    # See if board message is already present
                                    for fireMessage in self.fireMessages:
                                        if fireMessage[1] == message.id:
                                            if str(reaction.emoji) == fireMessage[3]: # Emoji is up to date and message is present - edit message
                                                try:
                                                    boardMessage = await channel.fetch_message(fireMessage[2])

                                                    await boardMessage.edit(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList)
                                                except discord.errors.NotFound:
                                                    boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view, files=[await attachment.to_file() for attachment in message.attachments])
                                                    
                                                    # Delete old message
                                                    self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                                    self.connection.commit()
                                                    
                                                    # Insert message
                                                    self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                                    self.connection.commit()

                                                    await self.refreshFireLists()

                                                self.lockedMessages.remove(payload.message_id)
                                                
                                                return
                                            else: # Emoji is outdated - resend the message and delete the old one     
                                                boardMessage = await channel.fetch_message(fireMessage[2])
                                                await boardMessage.delete()

                                                boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view, files=[await attachment.to_file() for attachment in message.attachments])

                                                # Delete old message
                                                self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                                self.connection.commit()
                                                
                                                # Insert message
                                                self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                                self.connection.commit()

                                                await self.refreshFireLists()

                                                self.lockedMessages.remove(payload.message_id)
                                                
                                                return
                                    
                                    boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view, files=[await attachment.to_file() for attachment in message.attachments])

                                    # Insert message
                                    self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                    self.connection.commit()

                                    await self.refreshFireLists()
                    else:
                        # See if board message is already present
                        for fireMessage in self.fireMessages:
                            if fireMessage[1] == message.id:
                                try:
                                    # Grab fireboard channel
                                    try:
                                        channel: discord.TextChannel = await guild.fetch_channel(channelID)
                                    except discord.errors.NotFound:
                                        self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                                        self.connection.commit()
                                        
                                        self.lockedMessages.remove(payload.message_id)
                                        
                                        return
                                    
                                    # Delete old message
                                    boardMessage = await channel.fetch_message(fireMessage[2])
                                    await boardMessage.delete()

                                    # Delete message from DB
                                    self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                    self.connection.commit()

                                    await self.refreshFireLists()

                                    self.lockedMessages.remove(payload.message_id)
                                    
                                    return
                                except discord.errors.NotFound:
                                    # Delete message from DB
                                    self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                    self.connection.commit()

                                    await self.refreshFireLists()

                                    self.lockedMessages.remove(payload.message_id)
                                    
                                    return
                        self.lockedMessages.remove(payload.message_id)

                        return
                else:
                    self.lockedMessages.remove(payload.message_id)
                    return
            else:
                self.lockedMessages.remove(payload.message_id)
                return
        else:
            self.lockedMessages.remove(payload.message_id)
            return
    
    # Listen for message reaction clear
    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionClearEvent):
        self.bot: discord.ext.commands.Bot
        
        # Lock system
        if payload.message_id not in self.lockedMessages:
            self.lockedMessages.append(payload.message_id)
        else:
            while payload.message_id in self.lockedMessages:
                pass

            self.lockedMessages.append(payload.message_id)
        
        # Only trigger if message is already in the fireboard DB
        if payload.message_id in [message[1] for message in self.fireMessages]:
            # Find server config
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
                    ignoreBots = (True if int(server[4]) == 1 else False)
            
            # Get guild
            try:
                guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
            except discord.errors.NotFound:
                self.lockedMessages.remove(payload.message_id)
                return

            # Get message channel
            channel: discord.abc.GuildChannel = await guild.fetch_channel(payload.channel_id)

            # Get our message
            message: discord.Message = await channel.fetch_message(payload.message_id)

            # See if board message is already present
            for fireMessage in self.fireMessages:
                if fireMessage[1] == message.id:
                    try:
                        # Delete message
                        try:
                            channel: discord.TextChannel = await guild.fetch_channel(channelID)
                        except discord.errors.NotFound:
                            self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                            self.connection.commit()
                            self.lockedMessages.remove(payload.message_id)
                            return
                        
                        boardMessage = await channel.fetch_message(fireMessage[2])
                        await boardMessage.delete()

                        # Delete message from DB
                        self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                        self.connection.commit()

                        await self.refreshFireLists()

                        self.lockedMessages.remove(payload.message_id)
                        return
                    except discord.errors.NotFound:
                        # Delete message from DB
                        self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                        self.connection.commit()

                        await self.refreshFireLists()

                        self.lockedMessages.remove(payload.message_id)
                        return
        else:
            self.lockedMessages.remove(payload.message_id)
            return
    
    # Listen for specific emoji being cleared
    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(self, payload: discord.RawReactionClearEmojiEvent):
        self.bot: discord.ext.commands.Bot
        
        # Lock system
        if payload.message_id not in self.lockedMessages:
            self.lockedMessages.append(payload.message_id)
        else:
            while payload.message_id in self.lockedMessages:
                pass

            self.lockedMessages.append(payload.message_id)
        
        # Only trigger if message is already in the fireboard DB
        if payload.message_id in [message[1] for message in self.fireMessages]:
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
                    ignoreBots = (True if int(server[4]) == 1 else False)
            
            # Only trigger if cleared emoji is our emoji
            if str(payload.emoji) == emoji:
                # Fetch server
                try:
                    guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                except discord.errors.NotFound:
                    self.lockedMessages.remove(payload.message_id)
                    return

                # Get message channel
                channel: discord.abc.GuildChannel = await guild.fetch_channel(payload.channel_id)

                # See if board message is already present
                for fireMessage in self.fireMessages:
                    if fireMessage[1] == payload.message_id:
                        try:
                            # Fetch fireboard channel
                            try:
                                channel: discord.TextChannel = await guild.fetch_channel(channelID)
                            except discord.errors.NotFound:
                                self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                                self.connection.commit()
                                
                                self.lockedMessages.remove(payload.message_id)
                                return
                            
                            # Delete message
                            boardMessage = await channel.fetch_message(fireMessage[2])
                            await boardMessage.delete()

                            # Delete message from DB
                            self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                            self.connection.commit()

                            await self.refreshFireLists()

                            self.lockedMessages.remove(payload.message_id)
                            return
                        except discord.errors.NotFound:
                            # Delete message from DB
                            self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                            self.connection.commit()

                            await self.refreshFireLists()

                            self.lockedMessages.remove(payload.message_id)
                            return
        else:
            self.lockedMessages.remove(payload.message_id)
            return
    
    # Listen for message being deleted
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        self.bot: discord.ext.commands.Bot
        
        # Lock system
        if payload.message_id not in self.lockedMessages:
            self.lockedMessages.append(payload.message_id)
        else:
            while payload.message_id in self.lockedMessages:
                pass

            self.lockedMessages.append(payload.message_id)
        
        # Only trigger if message is already in the fireboard DB
        if payload.message_id in [message[1] for message in self.fireMessages]:
            # Fetch server config
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
                    ignoreBots = (True if int(server[4]) == 1 else False)
            
            # Fetch server
            try:
                guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
            except discord.errors.NotFound:
                self.lockedMessages.remove(payload.message_id)
                return

            # Get message channel
            channel: discord.abc.GuildChannel = await guild.fetch_channel(payload.channel_id)

            # See if board message is already present
            for fireMessage in self.fireMessages:
                if fireMessage[1] == payload.message_id:
                    try:
                        # Fetch fireboard channel
                        try:
                            channel: discord.TextChannel = await guild.fetch_channel(channelID)
                        except discord.errors.NotFound:
                            self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                            self.connection.commit()
                            
                            self.lockedMessages.remove(payload.message_id)
                            return
                        
                        # Delete message
                        boardMessage = await channel.fetch_message(fireMessage[2])
                        await boardMessage.delete()

                        # Delete message from DB
                        self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                        self.connection.commit()

                        await self.refreshFireLists()

                        self.lockedMessages.remove(payload.message_id)
                        return
                    except discord.errors.NotFound:
                        # Delete message from DB
                        self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                        self.connection.commit()

                        await self.refreshFireLists()

                        self.lockedMessages.remove(payload.message_id)
                        return
        else:
            self.lockedMessages.remove(payload.message_id)
            return
    
    # Listen for message being edited
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        self.bot: discord.ext.commands.Bot
        
        # Lock system
        if payload.message_id not in self.lockedMessages:
            self.lockedMessages.append(payload.message_id)
        else:
            while payload.message_id in self.lockedMessages:
                pass

            self.lockedMessages.append(payload.message_id)
        
        # Only trigger if message is already in the fireboard DB
        if payload.message_id in [message[1] for message in self.fireMessages]:
            # Fetch server config
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
                    ignoreBots = (True if int(server[4]) == 1 else False)
            
            # Fetch server
            try:
                guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
            except discord.errors.NotFound:
                self.lockedMessages.remove(payload.message_id)
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
                self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                self.connection.commit()
                
                self.lockedMessages.remove(payload.message_id)
                return
            
            # Find previous fireboard message
            try:
                for fireMessage in self.fireMessages:
                    if fireMessage[0] == payload.guild_id and fireMessage[1] == payload.message_id:
                        # Edit with updated embed - reaction amount stays the same
                        boardMessage = await channel.fetch_message(fireMessage[2])

                        await boardMessage.edit(embeds=embedList, files=message.attachments)
            except discord.errors.NotFound: # Message not found
                # Delete message from DB
                self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                self.connection.commit()

                await self.refreshFireLists()

                self.lockedMessages.remove(payload.message_id)
                return
        else:
            self.lockedMessages.remove(payload.message_id)
            return
    
    # Listen for fireboard channel delete
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        # Only trigger if server has fireboard enabled
        if channel.guild.id in [guild[0] for guild in self.fireSettings]:
            for server in self.fireSettings:
                if server[0] == channel.guild.id:
                    if server[3] == channel.id:
                        # Delete fireboard config
                        self.cursor.execute(f"DELETE FROM fireMessages WHERE serverID = ?", (channel.guild.id,))
                        self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (channel.guild.id,))
                        self.connection.commit()

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
                    # Delete fireboard config
                    self.cursor.execute(f"DELETE FROM fireMessages WHERE serverID = ?", (guild.id,))
                    self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (guild.id,))
                    self.connection.commit()

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
            reactAmount = 3
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
            
            # Insert to DB, refresh lists
            self.cursor.execute(f"INSERT INTO fireSettings (serverID, reactAmount, emoji, channelID, ignoreBots) VALUES (?, ?, ?, ?, ?)", (interaction.guild_id, reactAmount, emoji, channelID, ignoreBots,))
            self.connection.commit()

            await self.refreshFireLists()
            
            embed = discord.Embed(title = "Enabled", description="Fireboard has been enabled in the current channel.", color=Color.green())
            embed.add_field(name="Info", value=f"**Reaction Requirement:** `{reactAmount} reactions`\n**Fireboard Channel:** <#{channelID}>\n**Emoji:** {emoji}\n**Ignore Bots:** `{ignoreBots}`")

            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Fireboard disable command
    @fireGroup.command(name="disable", description="Disable the server fireboard.")
    async def disableFireboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fireSettings]:
            class disableView(View):
                def __init__(self, bot):
                    super().__init__(timeout=60)

                    self.bot = bot.bot
                
                # Timeout
                async def on_timeout(self) -> None:
                    self.interaction: discord.Interaction
                    
                    for item in self.children:
                        item.disabled = True

                    embed = discord.Embed(title = "Timeout", description="You didn't press the button in time.", color=Color.red())
                    
                    await self.interaction.edit_original_response(embed=embed, view=self)
                
                # Disable button
                @discord.ui.button(label=f'Disable', style=discord.ButtonStyle.red, row = 0)
                async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer(ephemeral=True)
                    
                    self.connection: sqlite3.Connection
                    self.cursor: sqlite3.Cursor

                    # Delete all server info from DB, refresh list
                    self.cursor.execute(f"DELETE FROM fireMessages WHERE serverID = ?", (interaction.guild.id,))
                    self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (interaction.guild.id,))
                    self.connection.commit()

                    await self.botSelf.refreshFireLists() # pylint: disable=no-member

                    embed = discord.Embed(title = "Done!", description="Fireboard was disabled.", color=Color.green())
                    
                    await self.interaction.edit_original_response(embed=embed, view=None)

            viewInstance = disableView(self)
            viewInstance.interaction = interaction
            viewInstance.connection = self.connection
            viewInstance.cursor = self.cursor
            viewInstance.botSelf = self
        
            # Confirmation
            embed = discord.Embed(title = "Are you sure?", description="All data about this server's fireboard will be deleted. The fireboard will be disabled. This is a destructive action!", color=Color.orange())

            await interaction.followup.send(embed=embed, view=viewInstance, ephemeral=True)
        else:
            embed = discord.Embed(title = "Fireboard is not enabled.", color=Color.green())

            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Fireboard server info command
    @fireGroup.command(name="info", description="View fireboard config for this server.")
    async def fireboardInfo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fireSettings]:
            # Fetch server settings
            for server in self.fireSettings:
                if server[0] == interaction.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
                    ignoreBots = (True if int(server[4]) == 1 else False)
            
            embed = discord.Embed(title="Server Fireboard Settings", description=f"**Reaction Requirement:** `{reactAmount} reactions`\n**Fireboard Channel:** <#{channelID}>\n**Emoji:** {emoji}\n**Ignore Bots:** `{ignoreBots}`", color=Color.random())

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
            embed = discord.Embed(title = "Waiting for Reaction", description=f"{self.bot.loading_emoji} React with this message with your target emoji to set the fireboard emoji.", color=Color.orange())
            
            msg = await interaction.followup.send(embed=embed, ephemeral=False)

            def check(reaction, user):
                return user == interaction.user and reaction.message.id == msg.id
                
            # Wait for a reaction
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

                reaction: discord.Reaction = reaction
                
                # Change emoji in DB, refresh lists
                self.cursor.execute(f"UPDATE fireSettings SET emoji = ? WHERE serverID = ?", (str(reaction.emoji), interaction.guild_id,))
                self.connection.commit()
                
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
            embed = discord.Embed(title="Channel Set", description=f"Fireboard channel has been set to **{channel.mention}.**", color=Color.green())

            embed = discord.Embed(title = "Fireboard", description="This channel has been configured as the server fireboard.", color=Color.random())
            embed.set_footer(text = "Feel free to delete this message!")

            try:
                await channel.send(embed = embed)
            except discord.errors.Forbidden or discord.errors.NotFound:
                embed = discord.Embed(title = "Error", description="Looks like I can't send messages in this channel. Check permissions and try again.", color=Color.random())
                await interaction.followup.send(embed=embed, ephemeral=True)

                return
            
            # Update channel in DB, refresh lists
            self.cursor.execute(f"UPDATE fireSettings SET channelID = ? WHERE serverID = ?", (channel.id, interaction.guild_id,))
            self.connection.commit()

            await self.refreshFireLists()
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

            # Update reaction requirement in DB, refresh lists
            self.cursor.execute(f"UPDATE fireSettings SET reactAmount = ? WHERE serverID = ?", (amount, interaction.guild_id,))
            self.connection.commit()

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

            # Update setting in DB, refresh lists
            self.cursor.execute(f"UPDATE fireSettings SET ignoreBots = ? WHERE serverID = ?", (value, interaction.guild_id,))
            self.connection.commit()

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
            if channel.id in [channelEntry[1] for channelEntry in self.fireChannelBlacklist]:
                self.cursor.execute("DELETE FROM fireChannelBlacklist WHERE serverID = ? AND channelID = ?", (interaction.guild_id, channel.id,))
                self.connection.commit()

                await self.refreshFireLists()
                
                embed = discord.Embed(title = "Set", description = f"Removed {channel.mention} from the channel blacklist.")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                self.cursor.execute(f"INSERT INTO fireChannelBlacklist (serverID, channelID) VALUES (?, ?)", (interaction.guild_id, channel.id,))
                self.connection.commit()

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
            if role.id in [roleEntry[1] for roleEntry in self.fireRoleBlacklist]:
                self.cursor.execute("DELETE FROM fireRoleBlacklist WHERE serverID = ? AND roleID = ?", (interaction.guild_id, role.id,))
                self.connection.commit()

                await self.refreshFireLists()
                
                embed = discord.Embed(title = "Set", description = f"Removed {role.mention} from the role blacklist.")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                self.cursor.execute(f"INSERT INTO fireRoleBlacklist (serverID, roleID) VALUES (?, ?)", (interaction.guild_id, role.id,))
                self.connection.commit()

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
            class blacklistViewer(View):
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
            
            viewInstance = blacklistViewer()
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
    await bot.add_cog(fireboard(bot))
