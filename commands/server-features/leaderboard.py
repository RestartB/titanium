import os
import asqlite

import discord
import discord.ext
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View


class leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lbPool: asqlite.Pool = bot.lbPool
        self.bot.loop.create_task(self.sql_setup())
        
    async def sql_setup(self):
        async with self.lbPool.acquire() as sql:
            if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='optOut';") is None:
                await sql.execute("CREATE TABLE optOut (userID int)")
                await sql.commit()
            
            self.optOutList = []
            rawOptOutList = await sql.fetchall(f"SELECT userID FROM optOut;")

            for id in rawOptOutList:
                self.optOutList.append(id[0])

    # Refresh opt out list function
    async def refreshOptOutList(self):
        try:
            async with self.lbPool.acquire() as sql:
                await sql.execute(f"DELETE FROM optOut;")
                await sql.commit()

                for id in self.optOutList:
                    await sql.execute(f"INSERT INTO optOut (userID) VALUES (?)", (id,))
            
            return True, ""
        except Exception as e:
            return False, e
                
    # Listen for Messages
    @commands.Cog.listener()
    async def on_message(self, message):
        # Catch possible errors
        try:
            # Check if user is Bot
            if message.author.bot != True:
                if not(message.author.id in self.optOutList):
                    async with self.lbPool.acquire() as sql:
                        # Check if server is in DB
                        if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{str(message.guild.id)}';") != None:
                            # Check if user is already on leaderboard
                            if await sql.fetchone(f"SELECT userMention FROM '{message.guild.id}' WHERE userMention = '{message.author.mention}';") != None:
                                # User is on the leaderboard, update their values
                                await sql.execute(f"UPDATE '{message.guild.id}' SET messageCount = messageCount + 1, wordCount = wordCount + {len((message.content).split())}, attachmentCount = attachmentCount + {len(message.attachments)} WHERE userMention = ?", (message.author.mention))
                            else:
                                # User is not on leaderboard, add them to the leaderboard
                                await sql.execute(f"INSERT INTO '{message.guild.id}' (userMention, messageCount, wordCount, attachmentCount) VALUES (?, 1, {len((message.content).split())}, {len(message.attachments)})", (message.author.mention))
                            
                            # Commit to DB
                            await sql.commit()
                        else:
                            pass
                else:
                    pass
            else:
                pass
        except Exception as error:
            print("Error occurred while logging message for leaderboard!")
            print(error)
    
    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False)
    lbGroup = app_commands.Group(name="leaderboard", description="View the server leaderboard.", allowed_contexts=context)
    
    # Leaderboard Command
    @lbGroup.command(name = "view", description = "View the server message leaderboard.")
    @app_commands.choices(sort_type=[
        app_commands.Choice(name="Messages Sent", value="messageCount"),
        app_commands.Choice(name="Words Sent", value="wordCount"),
        app_commands.Choice(name="Attachments Sent", value="attachmentCount"),
        ])
    @app_commands.describe(sort_type = "What to sort the leaderboard by.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    @app_commands.checks.cooldown(1, 10)
    async def leaderboard(self, interaction: discord.Interaction, sort_type: app_commands.Choice[str], ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        pages = []
        
        i = 0
        pageStr = ""
        
        async with self.lbPool.acquire() as sql:
            if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{str(interaction.guild.id)}';") != None:
                vals = await sql.fetchall(f"SELECT userMention, {sort_type.value} FROM '{interaction.guild.id}' ORDER BY {sort_type.value} DESC")
                if vals != []:
                    for val in vals:
                        i += 1
                        
                        if pageStr == "":
                            pageStr += f"{i}. {val[0]}: {val[1]}"
                        else:
                            pageStr += f"\n{i}. {val[0]}: {val[1]}"

                        # If there's 10 items in the current page, we split it into a new page
                        if i % 10 == 0:
                            pages.append(pageStr)
                            pageStr = ""

                    if pageStr != "":
                        pages.append(pageStr)
                else:
                    pages.append("No Data")
                
                class Leaderboard(View):
                    def __init__(self, pages):
                        super().__init__(timeout = 900)
                        self.page = 0
                        self.pages = pages

                        self.locked = False

                        self.userID: int
                        self.message: discord.InteractionMessage

                        for item in self.children:
                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True

                    async def on_timeout(self) -> None:
                        for item in self.children:
                            item.disabled = True

                        await self.message.edit(view=self)
                
                    async def interaction_check(self, interaction: discord.Interaction):
                        if interaction.user.id != self.userID:
                            if self.locked:
                                embed = discord.Embed(title = "Error", description = "This command is locked. Only the owner can control it.", color=Color.red())
                                await interaction.response.send_message(embed=embed, ephemeral=True)
                            else:
                                return True
                        else:
                            return True
                    
                    @discord.ui.button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
                    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        self.page = 0

                        for item in self.children:
                            item.disabled = False
                            
                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True
                        
                        embed = discord.Embed(title = f"Server Leaderboard - {sort_type.name}", description = self.pages[self.page], color = Color.random())
                        embed.set_footer(text = f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)

                        await interaction.response.edit_message(embed = embed, view = self)
                    
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
                        
                        embed = discord.Embed(title = f"Server Leaderboard - {sort_type.name}", description = self.pages[self.page], color = Color.random())
                        embed.set_footer(text = f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)

                        await interaction.response.edit_message(embed = embed, view = self)
                    
                    @discord.ui.button(emoji="🔓", style=ButtonStyle.green, custom_id="lock")
                    async def lock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if interaction.user.id == self.userID:
                            self.locked = not self.locked

                            if self.locked:
                                button.emoji = "🔒"
                                button.style = ButtonStyle.red
                            else:
                                button.emoji = "🔓"
                                button.style = ButtonStyle.green
                            
                            await interaction.response.edit_message(view = self)
                        else:
                            embed = discord.Embed(title = "Error", description = "Only the command runner can toggle the page controls lock.", color=Color.red())
                            await interaction.response.send_message(embed = embed, ephemeral=True)

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

                        embed = discord.Embed(title = f"Server Leaderboard - {sort_type.name}", description = self.pages[self.page], color = Color.red())
                        embed.set_footer(text = f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)

                        await interaction.response.edit_message(embed = embed, view = self)
                    
                    @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
                    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        self.page = len(self.pages) - 1

                        for item in self.children:
                            item.disabled = False

                            if item.custom_id == "next" or item.custom_id == "last":
                                item.disabled = True
                        
                        embed = discord.Embed(title = f"Server Leaderboard - {sort_type.name}", description = self.pages[self.page], color = Color.random())
                        embed.set_footer(text = f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}", icon_url = interaction.user.display_avatar.url)

                        await interaction.response.edit_message(embed = embed, view = self)

                embed = discord.Embed(title = f"Server Leaderboard - {sort_type.name}", description=pages[0], color = Color.random())
                embed.set_footer(text = f"Controlling: @{interaction.user.name} - Page 1/{len(pages)}", icon_url = interaction.user.display_avatar.url)
                
                if len(pages) == 1:
                    await interaction.followup.send(embed = embed, ephemeral=ephemeral)
                else:
                    await interaction.followup.send(embed = embed, view = Leaderboard(pages), ephemeral=ephemeral)

                    Leaderboard.userID = interaction.user.id
                    Leaderboard.message = await interaction.original_response()
            else:
                embed = discord.Embed(title = "Not Enabled", description = "The message leaderboard is not enabled in this server. Ask an admin to enable it first.", color = Color.red())
                await interaction.followup.send(embed = embed, ephemeral=ephemeral)

    # Opt out command
    @lbGroup.command(name = "opt-out", description = "Opt out of the leaderboard globally as a user.")
    async def optOut_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        async def delete_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral = True)

            embed = discord.Embed(title = "Opting out...", description=f"{self.bot.loading_emoji} Please wait...", color = Color.orange())
            await interaction.edit_original_response(embed = embed, view = None)

            if interaction.user.id in self.optOutList:
                embed = discord.Embed(title = "Failed", description = "You have already opted out.", color = Color.red())
                await interaction.edit_original_response(embed = embed)
            else:
                self.optOutList.append(interaction.user.id)
                status, error = await self.refreshOptOutList()

                async with self.lbPool.acquire() as sql:
                    for server in await sql.fetchall(f"SELECT name FROM sqlite_master WHERE type='table' AND NOT name='optOut';"):
                        await sql.execute(f"DELETE FROM '{int(server[0])}' WHERE userMention = ?;", (interaction.user.mention))
                    
                    await sql.commit()

                if status == False:
                    raise error

                embed = discord.Embed(title = "You have opted out.", color = Color.green())
                await interaction.edit_original_response(embed = embed)
                
        view = View()
        delete_button = discord.ui.Button(label='Opt Out', style=ButtonStyle.red)
        delete_button.callback = delete_callback
        view.add_item(delete_button)

        embed = discord.Embed(title = "Are you sure?", description = "By opting out of the leaderboard, you will be unable to contribute to the Titanium leaderboard in any server. Additionally, your data will be deleted across all Titanium leaderboards.", color = Color.orange())
        await interaction.followup.send(embed = embed, view = view)
    
    # Opt out command
    @lbGroup.command(name = "opt-in", description = "Opt back in to the leaderboard globally as a user.")
    async def optIn_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        async def delete_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral = True)

            embed = discord.Embed(title = "Opting in...", description=f"{self.bot.loading_emoji} Please wait...", color = Color.orange())
            await interaction.edit_original_response(embed = embed, view = None)

            if not(interaction.user.id in self.optOutList):
                embed = discord.Embed(title = "Failed", description = "You are already opted in.", color = Color.red())
                await interaction.edit_original_response(embed = embed)
            else:
                self.optOutList.remove(interaction.user.id)
                status, error = await self.refreshOptOutList()

                if status == False:
                    raise error

                embed = discord.Embed(title = "You have opted in.", color = Color.green())
                await interaction.edit_original_response(embed = embed)
                
        view = View()
        delete_button = discord.ui.Button(label='Opt In', style=ButtonStyle.green)
        delete_button.callback = delete_callback
        view.add_item(delete_button)

        embed = discord.Embed(title = "Are you sure?", description = "By opting in to the leaderboard, you will be able to contribute to the Titanium leaderboard in any server again.", color = Color.orange())
        await interaction.followup.send(embed = embed, view = view)
    
    # Privacy command
    @lbGroup.command(name = "privacy", description = "View the leaderboard privacy disclaimer.")
    async def privacy(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)

        title = "Leaderboard Privacy Disclaimer"
        description = "The leaderboard system tracks the following information:"
        description += "\n\n-User Mention\n-Message Count\n-Word Count\n-Attachment Count\n-Server ID"
        description += "Message content is temporarily stored while word count is processed. "
        description += "A list of attachments in the target message is also temporarily stored, so we can work out how many attachments are in your message. "
        description += "Message content and attachment data can not be viewed at any point during the tracking process, and is deleted immediately after it has been processed."
        description += "The leaderboard does not contain any sensitive information, such as:"
        description += "\n\n-User PFP\n-Message Content\n-Attachment Data"
        
        embed = discord.Embed(title = title, description = description)
        # embed.add_field(name = "Opting Out", value="If you wish to opt out, use the following commands:\n**/lb-control opt-out - to opt out\n**/lb-control opt-in** - to opt back in")
        await interaction.followup.send(embed = embed)
    
    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False)
    perms = discord.Permissions()
    lbCtrlGroup = app_commands.Group(name="lb-setup", description="Set up the leaderboard - server admins only.", allowed_contexts=context, default_permissions=perms)
    
    # Enable LB command
    @lbCtrlGroup.command(name = "enable", description = "Enable the message leaderboard.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def enable_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        embed = discord.Embed(title = "Enabling...", description=f"{self.bot.loading_emoji} Enabling the leaderboard...", color = Color.orange())
        await interaction.edit_original_response(embed = embed)

        async with self.lbPool.acquire() as sql:
            if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{str(interaction.guild.id)}';") != None:
                embed = discord.Embed(title = "Success", description = "Already enabled for this server.", color = Color.green())
                await interaction.edit_original_response(embed = embed)
            else:
                await sql.execute(f"CREATE TABLE '{interaction.guild.id}' (userMention text, messageCount integer, wordCount integer, attachmentCount integer)")
                await sql.commit()
                
                embed = discord.Embed(title = "Success", description = "Enabled message leaderboard for this server.", color = Color.green())
                await interaction.edit_original_response(embed = embed)
    
    # Disable LB command
    @lbCtrlGroup.command(name = "disable", description = "Disable the message leaderboard.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def disable_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        async def delete_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral = True)

            embed = discord.Embed(title = "Disabling...", description=f"{self.bot.loading_emoji} Disabling the leaderboard...", color = Color.orange())
            await interaction.edit_original_response(embed = embed, view = None)

            async with self.lbPool.acquire() as sql:
                if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{interaction.guild.id}';") == None:
                    embed = discord.Embed(title = "Failed", description = "Leaderboard is already disabled in this server.", color = Color.red())
                    await interaction.edit_original_response(embed = embed)
                else:
                    await sql.execute(f"DROP TABLE '{interaction.guild.id}'")
                    await sql.commit()

                    embed = discord.Embed(title = "Disabled.", color = Color.green())
                    await interaction.edit_original_response(embed = embed)
                
        view = View()
        delete_button = discord.ui.Button(label='Delete', style=ButtonStyle.red)
        delete_button.callback = delete_callback
        view.add_item(delete_button)

        embed = discord.Embed(title = "Are you sure?", description = "The leaderboard will be disabled, and data for this server will be deleted!", color = Color.orange())
        await interaction.followup.send(embed = embed, view = view)
    
    # Reset LB command
    @lbCtrlGroup.command(name = "reset", description = "Resets the message leaderboard.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def reset_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)

        async with self.lbPool.acquire() as sql:
            if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{interaction.guild.id}';") == None:
                embed = discord.Embed(title = "Disabled", description = "Leaderboard is disabled in this server.", color = Color.red())
                await interaction.edit_original_response(embed = embed)
            else:
                async def delete_callback(interaction: discord.Interaction):
                    await interaction.response.defer(ephemeral = True)

                    embed = discord.Embed(title = "Resetting...", description=f"{self.bot.loading_emoji} Resetting the leaderboard...", color = Color.orange())
                    await interaction.edit_original_response(embed = embed, view = None)

                    await sql.execute(f"DELETE FROM '{interaction.guild.id}';")
                    await sql.commit()

                    embed = discord.Embed(title = "Reset.", color = Color.green())
                    await interaction.edit_original_response(embed = embed)
                        
                view = View()
                delete_button = discord.ui.Button(label='Reset', style=ButtonStyle.red)
                delete_button.callback = delete_callback
                view.add_item(delete_button)

                embed = discord.Embed(title = "Are you sure?", description = "The leaderboard will be reset and all data will be removed!", color = Color.orange())
                await interaction.edit_original_response(embed = embed, view = view)

    # Reset LB command
    @lbCtrlGroup.command(name = "reset-user", description = "Resets a user on the leaderboard.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def reset_userlb(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral = True)

        async with self.lbPool.acquire() as sql:
            if await sql.fetchone(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{interaction.guild.id}';") == None:
                embed = discord.Embed(title = "Disabled", description = "Leaderboard is disabled in this server.", color = Color.red())
                await interaction.edit_original_response(embed = embed)
            else:
                async def delete_callback(interaction: discord.Interaction):
                    await interaction.response.defer(ephemeral = True)

                    embed = discord.Embed(title = "Removing...", description=f"{self.bot.loading_emoji} Target: {user.mention}", color = Color.orange())
                    await interaction.edit_original_response(embed = embed, view = None)

                    await sql.execute(f"DELETE FROM '{interaction.guild.id}' WHERE userMention = '{user.mention}';")
                    await sql.commit()

                    embed = discord.Embed(title = "Removed.", color = Color.green())
                    await interaction.edit_original_response(embed = embed)
                        
                view = View()
                delete_button = discord.ui.Button(label='Remove', style=ButtonStyle.red)
                delete_button.callback = delete_callback
                view.add_item(delete_button)

                embed = discord.Embed(title = "Are you sure?", description = f"Are you sure you want to remove {user.mention} from the leaderboard?", color = Color.orange())
                await interaction.edit_original_response(embed = embed, view = view)
        
async def setup(bot):
    await bot.add_cog(leaderboard(bot))