import asqlite
import discord
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View

import sqlite3
from datetime import datetime


class editHistory(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.editPool: asqlite.Pool = bot.editPool
        self.enabledServers = []

        # Sync server list
        self.bot.loop.create_task(self.syncServerList())
    
        # Isolate option
        self.editHistoryCTX = app_commands.ContextMenu(
            name="View Edit History",
            callback=self.editHistoryCallback,
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False),
        )

        # Isolate option
        self.editHistoryPrivateCTX = app_commands.ContextMenu(
            name="View Edit History (Private)",
            callback=self.editHistoryCallbackPrivate,
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False),
        )

        # Set context menu permissions
        self.editHistoryCTX.default_permissions = discord.Permissions(manage_messages=True)
        self.editHistoryPrivateCTX.default_permissions = discord.Permissions(manage_messages=True)

        # Add context menu items to tree
        self.bot.tree.add_command(self.editHistoryCTX)
        self.bot.tree.add_command(self.editHistoryPrivateCTX)
    
    # Synchronize server list
    async def syncServerList(self):
        async with self.editPool.acquire() as sql:
            try: # Table exists
                self.enabledServers = [server[0] for server in await sql.fetchall("SELECT * FROM settings")]
            except sqlite3.OperationalError: # Table does not exist, create it
                await sql.execute("CREATE TABLE settings (guildID int)")
                await sql.commit()

                self.enabledServers = []
    
    # Listen for message being edited
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        if payload.guild_id is not None:
            if payload.guild_id in self.enabledServers:
                if payload.data["edited_timestamp"] is not None:
                    async with self.editPool.acquire() as sql:
                        try: # Check if table exists
                            await sql.fetchone(f"SELECT * FROM '{payload.guild_id}-{payload.message_id}'")
                        except sqlite3.OperationalError: # Table does not exist
                            await sql.execute(f"CREATE TABLE '{payload.guild_id}-{payload.message_id}' (editID INTEGER PRIMARY KEY AUTOINCREMENT, timestamp int, content text)")
                            
                            # Add original message
                            if payload.cached_message is not None: # Message is cached
                                createdTimestamp = int(payload.cached_message.created_at.timestamp())
                                
                                if payload.cached_message.edited_at is None: # Message is not edited
                                    await sql.execute(f"INSERT INTO '{payload.guild_id}-{payload.message_id}' (editID, timestamp, content) VALUES (0, ?, ?)", (createdTimestamp, payload.cached_message.content))
                                else: # Message is edited
                                    # Add initial message and edited message
                                    await sql.execute(f"INSERT INTO '{payload.guild_id}-{payload.message_id}' (editID, timestamp, content) VALUES (0, ?, ?)", (createdTimestamp, "Message content unavailable."))
                                    await sql.execute(f"INSERT INTO '{payload.guild_id}-{payload.message_id}' (timestamp, content) VALUES (?, ?)", (createdTimestamp, payload.cached_message.content))
                            else: # Message is not cached
                                createdTimestamp = int(datetime.strptime(payload.data["timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp())
                                editedOfflineTimestamp = int(datetime.strptime(payload.data["edited_timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp())

                                if payload.data["edited_timestamp"] is None: # Message is not edited
                                    await sql.execute(f"INSERT INTO '{payload.guild_id}-{payload.message_id}' (editID, timestamp, content) VALUES (0, ?, ?)", (createdTimestamp, "Message content unavailable."))
                                else: # Message is edited
                                    # Add initial message and edited message
                                    await sql.execute(f"INSERT INTO '{payload.guild_id}-{payload.message_id}' (editID, timestamp, content) VALUES (0, ?, ?)", (createdTimestamp, "Message content unavailable."))
                                    await sql.execute(f"INSERT INTO '{payload.guild_id}-{payload.message_id}' (timestamp, content) VALUES (?, ?)", (editedOfflineTimestamp, "Message content unavailable."))
                        finally: # Add edit to table
                            editedTimestamp = int(datetime.strptime(payload.data["edited_timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp())
                            
                            if (payload.data["content"] is not None) and payload.data["content"] != "": # Normal edit
                                # Add edit
                                await sql.execute(f"INSERT INTO '{payload.guild_id}-{payload.message_id}' (timestamp, content) VALUES (?, ?)", (editedTimestamp, payload.data["content"]))
                            else: # Embed or attachment edit
                                # Add edit
                                await sql.execute(f"INSERT INTO '{payload.guild_id}-{payload.message_id}' (timestamp, content) VALUES (?, ?)", (editedTimestamp, "No content, likely an embed or attachment edit."))
    
    # Listen for message being deleted
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if payload.guild_id is not None:
            if payload.guild_id in self.enabledServers:
                async with self.editPool.acquire() as sql:
                    try: # Check if table exists
                        await sql.fetchone(f"SELECT * FROM '{payload.guild_id}-{payload.message_id}'")

                        await sql.execute(f"DROP TABLE '{payload.guild_id}-{payload.message_id}'")

                        await sql.commit()
                    except sqlite3.OperationalError:
                        return

    # Edit history callback
    async def editHistoryCallback(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.defer()

        if interaction.guild_id in self.enabledServers: # Edit history is enabled
            # Hand off to history function with ephemeral disabled
            await self.editHistory(interaction, message, ephemeral=False)
        else:
            embed = discord.Embed(title="Edit History", description="Edit history is not enabled for this server.", color=Color.red())
            await interaction.followup.send(embed=embed)
    
    # Private edit history callback
    async def editHistoryCallbackPrivate(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.defer(ephemeral=True)

        if interaction.guild_id in self.enabledServers: # Edit history is enabled
            # Hand off to history function with ephemeral enabled
            await self.editHistory(interaction, message, ephemeral=True)
        else:
            embed = discord.Embed(title="Edit History", description="Edit history is not enabled for this server.", color=Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Edit history function
    async def editHistory(self, interaction: discord.Interaction, message: discord.Message, ephemeral: bool=True):
        async with self.editPool.acquire() as sql:
            target = await sql.fetchall(f"SELECT * FROM '{interaction.guild_id}-{message.id}'")
            
            if target is not None:
                historyPages = []
                
                # edit[0] = edit ID
                # edit[1] = timestamp
                # edit[2] = message content
                
                # Work through each edit
                for edit in target:
                    if edit[0] == 0: # Original message
                        historyPages.append(f"**Original Message Created <t:{edit[1]}:R> (<t:{edit[1]}:f>)**\n{edit[2]}")
                    else: # Edit
                        historyPages.append(f"**Edited <t:{edit[1]}:R> (<t:{edit[1]}:f>)**\n{edit[2]}")
                
                # Edit Page view
                class editPages(View):
                    def __init__(self, pages: list):
                        super().__init__(timeout = 600) # 10 minute timeout
                        
                        self.page = 0
                        self.pages: list = pages

                        self.response: discord.InteractionMessage
                        self.ogID: int

                        self.locked = False

                        # First and previous buttons will always start disabled
                        for item in self.children:
                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True
                    
                    # Disable all buttons on timeout
                    async def on_timeout(self) -> None:
                        for item in self.children:
                            if item.style != ButtonStyle.url:
                                item.disabled = True

                        # Edit message with disabled view
                        await self.response.edit(view=self)
                
                    # Block others from controlling when lock is active
                    async def interaction_check(self, interaction: discord.Interaction):
                        if interaction.user.id != self.ogID:
                            if self.locked:
                                embed = discord.Embed(title = "Error", description = "This command is locked. Only the owner can control it.", color=Color.red())
                                await interaction.response.send_message(embed = embed, ephemeral=True, delete_after=5)
                            else:
                                return True
                        else:
                            return True
                    
                    # First page
                    @discord.ui.button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
                    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        self.page = 0

                        for item in self.children:
                            item.disabled = False
                            
                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True
                        
                        embed = discord.Embed(title = "Edit History", description = self.pages[self.page], color = Color.random())
                        embed.set_footer(text = f"Page {self.page + 1}/{len(self.pages)}")
                        
                        await interaction.response.edit_message(embed = embed, view = self)
                    
                    # Previous page
                    @discord.ui.button(emoji="⏪", style=ButtonStyle.gray, custom_id="prev")
                    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if self.page - 1 == 0:
                            self.page -= 1

                            for item in self.children:
                                item.disabled = False

                                if item.custom_id == "first" or item.custom_id == "prev":
                                    item.disabled = True
                        else:
                            self.page -= 1

                            for item in self.children:
                                item.disabled = False
                        
                        embed = discord.Embed(title = "Edit History", description = self.pages[self.page], color = Color.random())
                        embed.set_footer(text = f"Page {self.page + 1}/{len(self.pages)}")
                        
                        await interaction.response.edit_message(embed = embed, view = self)
                    
                    # Lock / unlock button
                    @discord.ui.button(emoji="🔓", style=ButtonStyle.green, custom_id="lock")
                    async def lock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if interaction.user.id == self.ogID:
                            self.locked = not self.locked

                            if self.locked == True:
                                button.emoji = "🔒"
                                button.style = ButtonStyle.red
                            else:
                                button.emoji = "🔓"
                                button.style = ButtonStyle.green
                            
                            await interaction.response.edit_message(view = self)
                        else:
                            embed = discord.Embed(title = "Error", description = "Only the command runner can toggle the page controls lock.", color=Color.red())
                            await interaction.response.send_message(embed = embed, ephemeral = True, delete_after=5)

                    # Next page
                    @discord.ui.button(emoji="⏩", style=ButtonStyle.gray, custom_id="next")
                    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if (self.page + 1) == (len(self.pages) - 1):
                            self.page += 1

                            for item in self.children:
                                item.disabled = False
                                
                                if item.custom_id == "next" or item.custom_id == "last":
                                    item.disabled = True
                        else:
                            self.page += 1

                            for item in self.children:
                                item.disabled = False
                        
                        embed = discord.Embed(title = "Edit History", description = self.pages[self.page], color = Color.random())
                        embed.set_footer(text = f"Page {self.page + 1}/{len(self.pages)}")
                        
                        await interaction.response.edit_message(embed = embed, view = self)
                    
                    # Last page
                    @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
                    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        self.page = len(self.pages) - 1

                        for item in self.children:
                            item.disabled = False

                            if item.custom_id == "next" or item.custom_id == "last":
                                item.disabled = True
                        
                        embed = discord.Embed(title = "Edit History", description = self.pages[self.page], color = Color.random())
                        embed.set_footer(text = f"Page {self.page + 1}/{len(self.pages)}")
                        
                        await interaction.response.edit_message(embed = embed, view = self)
                
                # Create view
                view = editPages(historyPages)
                view.response = interaction.response
                view.ogID = interaction.user.id

                # Send message
                if len(historyPages) == 1:
                    embed = discord.Embed(title = "Edit History", description = historyPages[0], color = Color.random())
                    embed.set_footer(text = "Page 1/1")
                    
                    await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
                else:
                    embed = discord.Embed(title = "Edit History", description = historyPages[0], color = Color.random())
                    embed.set_footer(text = f"Page 1/{len(historyPages)}")
                    
                    await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
            else:
                embed = discord.Embed(title = "Edit History", description = historyPages[0], color = Color.random())
                embed.set_footer(text = f"Page 1/{len(historyPages)}")

                await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
    
    # Edit history control command group
    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False)
    installs = discord.app_commands.AppInstallationType(guild=True, user=False)
    perms = discord.Permissions()
    editHistoryGroup = app_commands.Group(name="edit-history", description="Control the edit history feature.", default_permissions=perms, allowed_contexts=context, allowed_installs=installs)

    # Enable edit history command
    @editHistoryGroup.command(name="enable", description="Enable the edit history feature.")
    async def enable_edit_history(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check if the edit history is already enabled for this server
        if interaction.guild_id in self.enabledServers: # Already enabled
            embed = discord.Embed(title="Edit History", description="Edit history is already enabled for this server.", color=Color.green())
            await interaction.followup.send(embed=embed)
        else: # Not enabled
            # Acquire a connection from the edit pool
            async with self.editPool.acquire() as sql:
                # Insert the guild ID into the settings table to enable edit history
                await sql.execute("INSERT INTO settings (guildID) VALUES (?)", (interaction.guild_id,))

            # Synchronize the server list
            await self.syncServerList()
            
            embed = discord.Embed(title="Edit History", description="Enabled edit history for this server.", color=Color.green())
            await interaction.followup.send(embed=embed)

    # Disable edit history command
    @editHistoryGroup.command(name="disable", description="Disable the edit history feature.")
    async def disable_edit_history(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check if the edit history is enabled for this server
        if interaction.guild_id in self.enabledServers: # Enabled
            # Define a callback function to handle the deletion process
            async def delete_callback(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)

                embed = discord.Embed(title="Disabling...", description=f"{self.bot.loading_emoji} Disabling edit history...", color=Color.orange())
                await interaction.edit_original_response(embed=embed, view=None)

                # Acquire a connection from the edit pool
                async with self.editPool.acquire() as sql:
                    # Drop all tables related to the guild
                    for table in await sql.fetchall(f"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '{interaction.guild.id}-%';"):
                        await sql.execute(f"DROP TABLE '{table}'")
                        await sql.commit()
                    
                    # Delete the guild ID from the settings table
                    await sql.execute("DELETE FROM settings WHERE guildID = ?", (interaction.guild_id,))
                    await sql.commit()
                
                # Synchronize the server list
                await self.syncServerList()
                
                embed = discord.Embed(title="Disabled.", color=Color.green())
                await interaction.edit_original_response(embed=embed)
                    
            # Create a view with a delete button
            view = View()
            delete_button = discord.ui.Button(label='Delete', style=ButtonStyle.red)
            delete_button.callback = delete_callback
            view.add_item(delete_button)

            # Create embed
            embed = discord.Embed(title="Are you sure?", description="Edit history will be disabled, and data for this server will be deleted!", color=Color.orange())
            await interaction.followup.send(embed=embed, view=view)   
        else: # Not enabled
            embed = discord.Embed(title="Edit History", description="Edit history is already disabled for this server.", color=Color.red())
            await interaction.followup.send(embed=embed)  

async def setup(bot):
    await bot.add_cog(editHistory(bot))