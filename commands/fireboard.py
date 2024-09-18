import discord
from discord import app_commands, Color
import discord.ext
import discord.ext.commands
from discord.ui import View
from discord.ext import commands
import asyncio
import sqlite3
import os
import pathlib

class fireboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Check DB exists
        open(os.path.join("content", "sql", "fireboard.db"), "a").close()
        
        self.connection = sqlite3.connect(os.path.join("content", "sql", "fireboard.db"))
        self.cursor = self.connection.cursor()
        
        if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='fireMessages';").fetchone() == None:
            # Fire Messages - messages that are active on the fireboard
            self.cursor.execute("CREATE TABLE fireMessages (serverID int, msgID int, boardMsgID int, emoji text)")

            # Fire Settings - server properties for fireboard
            self.cursor.execute("CREATE TABLE fireSettings (serverID int, reactAmount int, emoji text, channelID int)")
            
            self.connection.commit()
        
        self.fireMessages = self.cursor.execute("SELECT * FROM fireMessages").fetchall()
        self.fireSettings = self.cursor.execute("SELECT * FROM fireSettings").fetchall()
    
    # List refresh function
    async def refreshFireLists(self):
        self.fireMessages = self.cursor.execute("SELECT * FROM fireMessages").fetchall()
        self.fireSettings = self.cursor.execute("SELECT * FROM fireSettings").fetchall()

    # Listen for reactions
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        self.bot: discord.ext.commands.Bot
        
        # Only trigger if server has fireboard enabled
        if payload.guild_id in [guild[0] for guild in self.fireSettings]:
            found = False
            
            # Find server config
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
                    found = True

            if not found:
                return
            
            # Check if emoji is correct
            if str(payload.emoji) == emoji:
                try:
                    guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                except discord.errors.NotFound:
                    return

                # Get message channel
                channel: discord.TextChannel = await guild.fetch_channel(payload.channel_id)

                # Get our message
                message: discord.Message = await channel.fetch_message(payload.message_id)

                # See if the target reaction is present
                for reaction in message.reactions:
                    if str(reaction.emoji) == str(emoji):
                        if (reaction.normal_count + reaction.burst_count) >= reactAmount:
                            embed = discord.Embed(description=message.content, color=Color.random())
                            embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
                            embed.timestamp = message.created_at
                            
                            image_set = False
                            
                            for attachment in message.attachments:
                                attach_type = attachment.content_type.split("/")[0]
                                
                                # Show first image
                                if attach_type == "image":
                                    embed.set_image(url=attachment.url)
                                    image_set = True
                                    
                                    break

                            # Add attachment disclaimer
                            if not(image_set) and message.attachments:
                                embed.add_field(name = "Attachments", value=f"There are **{len(message.attachments)} attachments** on this message.")
                            elif len(message.attachments) > 1:
                                embed.add_field(name = "Attachments", value=f"There are **{len(message.attachments) - 1} more attachments** on this message. Showing first image.")

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
                                return
                            
                            # See if board message is already present
                            for fireMessage in self.fireMessages:
                                if fireMessage[1] == message.id:
                                    if str(reaction.emoji) == fireMessage[3]: # Emoji is up to date and message is present - edit message
                                        try:
                                            boardMessage = await channel.fetch_message(fireMessage[2])
                                            
                                            await boardMessage.edit(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList)
                                        except discord.errors.NotFound:
                                            boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view)
                                            
                                            # Delete old message
                                            self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                            self.connection.commit()
                                            
                                            # Insert message
                                            self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                            self.connection.commit()

                                            await self.refreshFireLists()

                                        return
                                    else: # Emoji is outdated - resend the message and delete the old one     
                                        boardMessage = await channel.fetch_message(fireMessage[2])
                                        await boardMessage.delete()

                                        boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view)

                                        # Delete old message
                                        self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                        self.connection.commit()
                                        
                                        # Insert message
                                        self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                        self.connection.commit()

                                        await self.refreshFireLists()

                                        return
                            
                            boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view)

                            # Insert message
                            self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                            self.connection.commit()

                            await self.refreshFireLists()
        else:
            return

    # Listen for reaction removal
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        self.bot: discord.ext.commands.Bot
        
        # Only trigger if message is already in the fireboard DB
        if payload.message_id in [message[1] for message in self.fireMessages]:
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
            
            if str(payload.emoji) == emoji:
                try:
                    guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                except discord.errors.NotFound:
                    return

                # Get message channel
                channel: discord.TextChannel = await guild.fetch_channel(payload.channel_id)

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
                                                return
                                            
                                            # Delete old message
                                            boardMessage = await channel.fetch_message(fireMessage[2])
                                            await boardMessage.delete()

                                            # Delete message from DB
                                            self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                            self.connection.commit()

                                            await self.refreshFireLists()

                                            return
                                        except discord.errors.NotFound:
                                            # Delete message from DB
                                            self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                            self.connection.commit()

                                            await self.refreshFireLists()

                                            return
                                return
                            else: # Message still legible for fireboard
                                embed = discord.Embed(description=message.content, color=Color.random())
                                embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
                                embed.timestamp = message.created_at
                                
                                image_set = False
                                
                                for attachment in message.attachments:
                                    attach_type = attachment.content_type.split("/")[0]
                                    
                                    # Show first image
                                    if attach_type == "image":
                                        embed.set_image(url=attachment.url)
                                        image_set = True
                                        
                                        break

                                # Add attachment disclaimer
                                if not(image_set) and message.attachments:
                                    embed.add_field(name = "Attachments", value=f"There are **{len(message.attachments)} attachments** on this message.")
                                elif len(message.attachments) > 1:
                                    embed.add_field(name = "Attachments", value=f"There are **{len(message.attachments) - 1} more attachments** on this message. Showing first image.")

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
                                    return
                                
                                # See if board message is already present
                                for fireMessage in self.fireMessages:
                                    if fireMessage[1] == message.id:
                                        if str(reaction.emoji) == fireMessage[3]: # Emoji is up to date and message is present - edit message
                                            try:
                                                boardMessage = await channel.fetch_message(fireMessage[2])

                                                await boardMessage.edit(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList)
                                            except discord.errors.NotFound:
                                                boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view)
                                                
                                                # Delete old message
                                                self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                                self.connection.commit()
                                                
                                                # Insert message
                                                self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                                self.connection.commit()

                                                await self.refreshFireLists()

                                            return
                                        else: # Emoji is outdated - resend the message and delete the old one     
                                            boardMessage = await channel.fetch_message(fireMessage[2])
                                            await boardMessage.delete()

                                            boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view)

                                            # Delete old message
                                            self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                            self.connection.commit()
                                            
                                            # Insert message
                                            self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                            self.connection.commit()

                                            await self.refreshFireLists()

                                            return
                                
                                boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | <#{payload.channel_id}>", embeds=embedList, view=view)

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
                                    return
                                
                                # Delete old message
                                boardMessage = await channel.fetch_message(fireMessage[2])
                                await boardMessage.delete()

                                # Delete message from DB
                                self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                self.connection.commit()

                                await self.refreshFireLists()

                                return
                            except discord.errors.NotFound:
                                # Delete message from DB
                                self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                self.connection.commit()

                                await self.refreshFireLists()

                                return
                    return
        else:
            return
    
    # Listen for message reaction clear
    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionClearEvent):
        self.bot: discord.ext.commands.Bot
        
        # Only trigger if message is already in the fireboard DB
        if payload.message_id in [message[1] for message in self.fireMessages]:
            # Find server config
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
            
            # Get guild
            try:
                guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
            except discord.errors.NotFound:
                return

            # Get message channel
            channel: discord.TextChannel = await guild.fetch_channel(payload.channel_id)

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
                            return
                        
                        boardMessage = await channel.fetch_message(fireMessage[2])
                        await boardMessage.delete()

                        # Delete message from DB
                        self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                        self.connection.commit()

                        await self.refreshFireLists()

                        return
                    except discord.errors.NotFound:
                        # Delete message from DB
                        self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                        self.connection.commit()

                        await self.refreshFireLists()

                        return
        else:
            return
    
    # Listen for specific emoji being cleared
    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(self, payload: discord.RawReactionClearEmojiEvent):
        self.bot: discord.ext.commands.Bot
        
        # Only trigger if message is already in the fireboard DB
        if payload.message_id in [message[1] for message in self.fireMessages]:
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
            
            # Only trigger if cleared emoji is our emoji
            if str(payload.emoji) == emoji:
                # Fetch server
                try:
                    guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                except discord.errors.NotFound:
                    return

                # Get message channel
                channel: discord.TextChannel = await guild.fetch_channel(payload.channel_id)

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
                                return
                            
                            # Delete message
                            boardMessage = await channel.fetch_message(fireMessage[2])
                            await boardMessage.delete()

                            # Delete message from DB
                            self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                            self.connection.commit()

                            await self.refreshFireLists()

                            return
                        except discord.errors.NotFound:
                            # Delete message from DB
                            self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                            self.connection.commit()

                            await self.refreshFireLists()

                            return
        else:
            return
    
    # Listen for message being deleted
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        self.bot: discord.ext.commands.Bot
        
        # Only trigger if message is already in the fireboard DB
        if payload.message_id in [message[1] for message in self.fireMessages]:
            # Fetch server config
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
            
            # Fetch server
            try:
                guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
            except discord.errors.NotFound:
                return

            # Get message channel
            channel: discord.TextChannel = await guild.fetch_channel(payload.channel_id)

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
                            return
                        
                        # Delete message
                        boardMessage = await channel.fetch_message(fireMessage[2])
                        await boardMessage.delete()

                        # Delete message from DB
                        self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                        self.connection.commit()

                        await self.refreshFireLists()

                        return
                    except discord.errors.NotFound:
                        # Delete message from DB
                        self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                        self.connection.commit()

                        await self.refreshFireLists()

                        return
        else:
            return
    
    # Listen for message being edited
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        self.bot: discord.ext.commands.Bot
        
        # Only trigger if message is already in the fireboard DB
        if payload.message_id in [message[1] for message in self.fireMessages]:
            # Fetch server config
            for server in self.fireSettings:
                if server[0] == payload.guild_id:
                    reactAmount = server[1]
                    emoji = server[2]
                    channelID = server[3]
            
            # Fetch server
            try:
                guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
            except discord.errors.NotFound:
                return
            
            # Get message channel
            channel: discord.TextChannel = await guild.fetch_channel(payload.channel_id)

            # Get our message
            message: discord.Message = await channel.fetch_message(payload.message_id)
            
            embed = discord.Embed(description=message.content, color=Color.random())
            embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
            embed.timestamp = message.created_at
            
            image_set = False
            
            for attachment in message.attachments:
                attach_type = attachment.content_type.split("/")[0]
                
                # Show first image
                if attach_type == "image":
                    embed.set_image(url=attachment.url)
                    image_set = True
                    
                    break

            # Add attachment disclaimer
            if not(image_set) and message.attachments:
                embed.add_field(name = "Attachments", value=f"There are **{len(message.attachments)} attachments** on this message.")
            elif len(message.attachments) > 1:
                embed.add_field(name = "Attachments", value=f"There are **{len(message.attachments) - 1} more attachments** on this message. Showing first image.")

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
                return
            
            # Find previous fireboard message
            try:
                for fireMessage in self.fireMessages:
                    if fireMessage[0] == payload.guild_id and fireMessage[1] == payload.message_id:
                        # Edit with updated embed - reaction amount stays the same
                        boardMessage = await channel.fetch_message(fireMessage[2])

                        await boardMessage.edit(embeds=embedList)
            except discord.errors.NotFound: # Message not found
                # Delete message from DB
                self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (payload.message_id,))
                self.connection.commit()

                await self.refreshFireLists()

                return
        else:
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
            
            # Insert to DB, refresh lists
            self.cursor.execute(f"INSERT INTO fireSettings (serverID, reactAmount, emoji, channelID) VALUES (?, ?, ?, ?)", (interaction.guild_id, reactAmount, emoji, channelID))
            self.connection.commit()

            await self.refreshFireLists()
            
            embed = discord.Embed(title = "Enabled", description="Fireboard has been enabled in the current channel.", color=Color.green())
            embed.add_field(name="Info", value=f"**Reaction Requirement:** `{reactAmount} reactions`\n**Fireboard Channel:** <#{channelID}>\n**Emoji:** {emoji}")

            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Fireboard disable command
    @fireGroup.command(name="disable", description="Disable the server fireboard.")
    async def disableFireboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check fireboard status
        if interaction.guild.id in [guild[0] for guild in self.fireSettings]:
            class spotifyEmbedView(View):
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

                    await self.botSelf.refreshFireLists()

                    embed = discord.Embed(title = "Done!", description="Fireboard was disabled.", color=Color.green())
                    
                    await self.interaction.edit_original_response(embed=embed, view=None)

            viewInstance = spotifyEmbedView(self)
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
            
            embed = discord.Embed(title="Server Fireboard Settings", description=f"**Reaction Requirement:** `{reactAmount} reactions`\n**Fireboard Channel:** <#{channelID}>\n**Emoji:** {emoji}", color=Color.random())

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

async def setup(bot):
    await bot.add_cog(fireboard(bot))