import discord
from discord import app_commands, Color
import discord.ext.commands
from discord.ui import View
from discord.ext import commands
import asyncio
import sqlite3

import discord.ext

class fireboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.connection = sqlite3.connect(f"{self.bot.path}{self.bot.pathtype}content{self.bot.pathtype}sql{self.bot.pathtype}fireboard.db")
        self.cursor = self.connection.cursor()
        
        if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='fireMessages';").fetchone() == None:
            # Fire Messages - messages that are active on the fireboard
            self.cursor.execute("CREATE TABLE fireMessages (serverID int, msgID int, boardMsgID int, emoji text)")

            # Fire Settings - server properties for fireboard
            self.cursor.execute("CREATE TABLE fireSettings (serverID int, reactAmount int, emoji text, channelID int)")
            
            self.connection.commit()
        
        self.fireMessages = self.cursor.execute("SELECT * FROM fireMessages").fetchall()
        self.fireSettings = self.cursor.execute("SELECT * FROM fireSettings").fetchall()
    
    async def refreshFireLists(self):
        self.fireMessages = self.cursor.execute("SELECT * FROM fireMessages").fetchall()
        self.fireSettings = self.cursor.execute("SELECT * FROM fireSettings").fetchall()

    # Listen for reactions
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        self.bot: discord.ext.commands.Bot
        
        for server in self.fireSettings:
            if server[0] == payload.guild_id:
                reactAmount = server[1]
                emoji = server[2]
                channelID = server[3]
        
        if str(payload.emoji) == emoji:
            # Check if fireboard channel is present - if it isn't, remove server from DB
            try:
                guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                channel: discord.TextChannel = await guild.fetch_channel(payload.channel_id)
            except discord.errors.NotFound:
                self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                self.connection.commit()
                return

            # Get our message
            message: discord.Message = await channel.fetch_message(payload.message_id)

            # See if the target reaction is present
            for reaction in message.reactions:
                if str(reaction.emoji) == str(emoji):
                    if (reaction.normal_count + reaction.burst_count) >= reactAmount:
                        embed = discord.Embed(description=message.content, color=Color.random())
                        embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
                        
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
                        
                        channel: discord.TextChannel = await guild.fetch_channel(channelID)
                        
                        # See if board message is already present
                        for fireMessage in self.fireMessages:
                            if fireMessage[1] == message.id:
                                if str(reaction.emoji) == fireMessage[3]: # Emoji is up to date and message is present - edit message
                                    try:
                                        boardMessage = await channel.fetch_message(fireMessage[2])
                                        
                                        await boardMessage.edit(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | {channel.mention}", embed=embed)
                                    except discord.errors.NotFound:
                                        boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | {channel.mention}", embed=embed, view=view)
                                        
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

                                    boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | {channel.mention}", embed=embed, view=view)

                                    # Delete old message
                                    self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                    self.connection.commit()
                                    
                                    # Insert message
                                    self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                    self.connection.commit()

                                    await self.refreshFireLists()

                                    return
                        
                        boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | {channel.mention}", embed=embed, view=view)

                        # Insert message
                        self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                        self.connection.commit()

                        await self.refreshFireLists()

    # Listen for reaction removal
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        self.bot: discord.ext.commands.Bot
        
        for server in self.fireSettings:
            if server[0] == payload.guild_id:
                reactAmount = server[1]
                emoji = server[2]
                channelID = server[3]
        
        if str(payload.emoji) == emoji:
            # Check if fireboard channel is present - if it isn't, remove server from DB
            try:
                guild: discord.Guild = await self.bot.fetch_guild(payload.guild_id)
                channel: discord.TextChannel = await guild.fetch_channel(payload.channel_id)
            except discord.errors.NotFound:
                self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (payload.guild_id,))
                self.connection.commit()
                return

            # Get our message
            message: discord.Message = await channel.fetch_message(payload.message_id)

            # See if the target reaction is present
            for reaction in message.reactions:
                if str(reaction.emoji) == str(emoji):
                    if (reaction.normal_count + reaction.burst_count) < reactAmount:
                        # See if board message is already present
                        for fireMessage in self.fireMessages:
                            if fireMessage[1] == message.id:
                                try:
                                    channel: discord.TextChannel = await guild.fetch_channel(channelID)
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
                        embed = discord.Embed(description=message.content, color=Color.random())
                        embed.set_author(name=message.author.name, icon_url=message.author.display_avatar.url)
                        
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
                        
                        channel: discord.TextChannel = await guild.fetch_channel(channelID)
                        
                        # See if board message is already present
                        for fireMessage in self.fireMessages:
                            if fireMessage[1] == message.id:
                                if str(reaction.emoji) == fireMessage[3]: # Emoji is up to date and message is present - edit message
                                    try:
                                        boardMessage = await channel.fetch_message(fireMessage[2])

                                        await boardMessage.edit(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | {channel.mention}", embed=embed)
                                    except discord.errors.NotFound:
                                        boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | {channel.mention}", embed=embed, view=view)
                                        
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

                                    boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | {channel.mention}", embed=embed, view=view)

                                    # Delete old message
                                    self.cursor.execute(f"DELETE FROM fireMessages WHERE msgID = ?", (message.id,))
                                    self.connection.commit()
                                    
                                    # Insert message
                                    self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                                    self.connection.commit()

                                    await self.refreshFireLists()

                                    return
                        
                        boardMessage = await channel.send(content=f"**{reaction.normal_count + reaction.burst_count} {emoji}** | {message.author.mention} | {channel.mention}", embed=embed, view=view)

                        # Insert message
                        self.cursor.execute(f"INSERT INTO fireMessages (serverID, msgID, boardMsgID, emoji) VALUES (?, ?, ?, ?)", (message.guild.id, message.id, boardMessage.id, str(reaction.emoji)))
                        self.connection.commit()

                        await self.refreshFireLists()
    
    # Listen for channel being deleted
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        for server in self.fireSettings:
            if server[0] == channel.guild.id:
                if server[3] == channel.id:
                    self.cursor.execute(f"DELETE FROM fireMessages WHERE serverID = ?", (channel.guild.id,))
                    self.cursor.execute(f"DELETE FROM fireSettings WHERE serverID = ?", (channel.guild.id,))
                    self.connection.commit()

                    await self.refreshFireLists()

                    return
    
    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False)
    perms = discord.Permissions()
    fireGroup = app_commands.Group(name="fireboard", description="Control the fireboard.", allowed_contexts=context, default_permissions=perms)
    
    @fireGroup.command(name="enable", description="Enable the fireboard in the current channel.")
    async def enableFireboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        for server in self.fireSettings:
            if server[0] == interaction.guild.id:
                embed = discord.Embed(title = "Fireboard is already enabled.", color=Color.green())
                await interaction.followup.send(embed=embed, ephemeral=True)

                return
        
        reactAmount = 3
        emoji = "🔥"
        channelID = interaction.channel_id
        
        self.cursor.execute(f"INSERT INTO fireSettings (serverID, reactAmount, emoji, channelID) VALUES (?, ?, ?, ?)", (interaction.guild_id, reactAmount, emoji, channelID))
        self.connection.commit()

        await self.refreshFireLists()
        
        embed = discord.Embed(title = "Enabled", description="Fireboard has been enabled in the current channel.", color=Color.green())
        embed.add_field(name="Info", value=f"**Reaction Requirement:** `{reactAmount} reactions`\n**Fireboard Channel:** <#{channelID}>\n**Emoji:** {emoji}")

        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @fireGroup.command(name="disable", description="Disable the server fireboard.")
    async def disableFireboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        for server in self.fireSettings:
            if server[0] == interaction.guild.id:
                class spotifyEmbedView(View):
                    def __init__(self, bot):
                        super().__init__(timeout=60)

                        self.bot = bot.bot
                    
                    async def on_timeout(self) -> None:
                        self.interaction: discord.Interaction
                        
                        for item in self.children:
                            item.disabled = True

                        embed = discord.Embed(title = "Timeout", description="You didn't press the button in time.", color=Color.red())
                        
                        await self.interaction.edit_original_response(embed=embed, view=self)
                    
                    @discord.ui.button(label=f'Disable', style=discord.ButtonStyle.red, row = 0)
                    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
                        await interaction.response.defer(ephemeral=True)
                        
                        self.connection: sqlite3.Connection
                        self.cursor: sqlite3.Cursor

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
            
                embed = discord.Embed(title = "Are you sure?", description="All data about this server's fireboard will be deleted. The fireboard will be disabled. This is a destructive action!", color=Color.orange())

                await interaction.followup.send(embed=embed, view=viewInstance, ephemeral=True)

                return

        embed = discord.Embed(title = "Fireboard is not enabled.", color=Color.green())

        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @fireGroup.command(name="info", description="View fireboard config for this server.")
    async def fireboardInfo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        for server in self.fireSettings:
            if server[0] == interaction.guild_id:
                reactAmount = server[1]
                emoji = server[2]
                channelID = server[3]
        
        embed = discord.Embed(title="Server Fireboard Settings", description=f"**Reaction Requirement:** `{reactAmount} reactions`\n**Fireboard Channel:** <#{channelID}>\n**Emoji:** {emoji}", color=Color.random())

        await interaction.followup.send(embed=embed, ephemeral=True)
                
    @fireGroup.command(name="emoji", description="Set a custom fireboard emoji.")
    async def fireboardEmoji(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        
        embed = discord.Embed(title = "Waiting for Reaction", description=f"{self.bot.loading_emoji} React with this message with your target emoji to set the fireboard emoji.", color=Color.orange())
        
        msg = await interaction.followup.send(embed=embed, ephemeral=False)

        def check(reaction, user):
            return user == interaction.user and reaction.message.id == msg.id
            
        # Wait for a reaction
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)

            reaction: discord.Reaction = reaction
            
            self.cursor.execute(f"UPDATE fireSettings SET emoji = ? WHERE serverID = ?", (str(reaction.emoji), interaction.guild_id,))
            self.connection.commit()
            
            embed = discord.Embed(title = "Emoji Set", description=f"Set emoji to **{str(reaction.emoji)}.**", color=Color.green())
            
            await self.refreshFireLists()
            await interaction.edit_original_response(embed=embed)
        except asyncio.TimeoutError:
            embed = discord.Embed(title = "Timed Out", description="You didn't react in time.", color=Color.red())
            
            await interaction.edit_original_response(embed=embed)
    
    @fireGroup.command(name="channel", description="Set the channel for fireboard messages to be sent in.")
    async def fireboardChannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(title="Channel Set", description=f"Fireboard channel has been set to **{channel.mention}.**", color=Color.green())

        self.cursor.execute(f"UPDATE fireSettings SET channelID = ? WHERE serverID = ?", (channel.id, interaction.guild_id,))
        self.connection.commit()

        await self.refreshFireLists()
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @fireGroup.command(name="requirement", description="Set required reaction amount for message to be posted on the fireboard.")
    async def fireboardRequirement(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(title="Set", description=f"Reaction requirement has been set to **{amount} reactions.**", color=Color.green())

        self.cursor.execute(f"UPDATE fireSettings SET reactAmount = ? WHERE serverID = ?", (amount, interaction.guild_id,))
        self.connection.commit()

        await self.refreshFireLists()
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(fireboard(bot))