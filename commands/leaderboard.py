import discord
from discord import app_commands, Color
import discord.ext
from discord.ui import View
from discord.ext import commands
import sqlite3

import discord.ext.tasks

class leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.connection = sqlite3.connect(f"{self.bot.path}{self.bot.pathtype}content{self.bot.pathtype}sql{self.bot.pathtype}lb.db")
        self.cursor = self.connection.cursor()

    # Listen for Messages
    @commands.Cog.listener()
    async def on_message(self, message):
        # Catch possible errors
        try:
            # Check if user is Bot
            if message.author.bot != True:
                # Check if server is in DB
                if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{str(message.guild.id)}';").fetchone() != None:
                    # Check if user is already on leaderboard
                    if self.cursor.execute(f"SELECT userMention FROM '{message.guild.id}' WHERE userMention = '{message.author.mention}';").fetchone() != None:
                        # User is on the leaderboard, update their values
                        self.cursor.execute(f"UPDATE '{message.guild.id}' SET messageCount = messageCount + 1, wordCount = wordCount + {len((message.content).split())} WHERE userMention = '{message.author.mention}'")
                    else:
                        # User is not on leaderboard, add them to the leaderboard
                        self.cursor.execute(f"INSERT INTO '{message.guild.id}' (userMention, messageCount, wordCount) VALUES ('{message.author.mention}', 1, {len((message.content).split())})")
                    
                    # Commit to DB
                    self.connection.commit()
                else:
                    pass
            else:
                pass
        # This should never happen, but if there is an error, log it
        except Exception as error:
            print("Error occurred while logging message for leaderboard!")
            print(error)
    
    # Leaderboard Command
    @app_commands.command(name = "leaderboard", description = "View the server message leaderboard.")
    @app_commands.choices(sort_type=[
        app_commands.Choice(name="Messages Sent", value="messageCount"),
        app_commands.Choice(name="Words Sent", value="wordCount"),
        ])
    @app_commands.checks.cooldown(1, 10)
    async def leaderboard(self, interaction: discord.Interaction, sort_type: app_commands.Choice[str]):
        await interaction.response.defer()
        
        user_id = interaction.user.id
        
        pages = []
        
        # Send initial embed
        embed = discord.Embed(title = "Loading...")
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)

        # try:
        i = 0
        page_str = ""
        
        if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{str(interaction.guild.id)}';").fetchone() != None:
            vals = self.cursor.execute(f"SELECT userMention, {sort_type.value} FROM '{interaction.guild.id}' ORDER BY {sort_type.value} DESC").fetchall()
            if vals != []:
                for val in vals:
                    i += 1
                    
                    if page_str == "":
                        page_str += f"{i}. {val[0]}: {val[1]}"
                    else:
                        page_str += f"\n{i}. {val[0]}: {val[1]}"

                    # If there's 10 items in the current page, we split it into a new page
                    if i % 10 == 0:
                        pages.append(pageStr)
                        pageStr = ""

                if page_str != "":
                    pages.append(page_str)
            else:
                pages.append("No Data")
            
            class Leaderboard(View):
                def __init__(self, pages):
                    super().__init__()
                    self.page = 0
                    self.pages = pages
            
                @discord.ui.button(label="<", style=discord.ButtonStyle.green, custom_id="prev")
                async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if user_id == interaction.user.id:
                        if self.page > 0:
                            self.page -= 1
                        else:
                            self.page = len(self.pages) - 1
                        embed = discord.Embed(title = f"Server Leaderboard - {sort_type.name}", description = self.pages[self.page], color = Color.random())
                        embed.set_footer(text = f"Requested by {interaction.user.name} - Page {self.page}/{len(self.pages)}", icon_url = interaction.user.avatar.url)
                        await interaction.response.edit_message(embed = embed)
                    else:
                        embed = discord.Embed(title = f"Error", description = f"{interaction.user.mention}, you are not the command runner.", color = Color.red())
                        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                        await interaction.channel.send(embed = embed, delete_after = 5.0, view = None)
                        await interaction.channel.send(f"{interaction.user.mention}", delete_after=5.0)

                @discord.ui.button(label=">", style=discord.ButtonStyle.green, custom_id="next")
                async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if user_id == interaction.user.id:
                        if self.page < len(self.pages) - 1:
                            self.page += 1
                        else:
                            self.page = 0
                        embed = discord.Embed(title = f"Server Leaderboard - {sort_type.name}", description = self.pages[self.page], color = Color.red())
                        embed.set_footer(text = f"Requested by {interaction.user.name} - Page {self.page}/{len(self.pages)}", icon_url = interaction.user.avatar.url)
                        await interaction.response.edit_message(embed = embed)
                    else:
                        embed = discord.Embed(title = f"Error", description = f"{interaction.user.mention}, you are not the command runner.", color = Color.red())
                        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                        await interaction.channel.send(embed = embed, delete_after = 5.0, view = None)
                        await interaction.channel.send(f"{interaction.user.mention}", delete_after=5.0)

            embed = discord.Embed(title = f"Server Leaderboard - {sort_type.name}", description=pages[0], color = Color.random())
            embed.set_footer(text = f"Requested by {interaction.user.name} - Page 1/{len(pages)}", icon_url = interaction.user.avatar.url)
            
            if len(pages) == 1:
                await interaction.edit_original_response(embed = embed)
            else:
                await interaction.edit_original_response(embed = embed, view = Leaderboard(pages))
        else:
            embed = discord.Embed(title = "Not Enabled", description = "The message leaderboard is not enabled in this server.", color = Color.red())
            await interaction.edit_original_response(embed = embed)
        # except Exception:
        #     embed = discord.Embed(title = "Unexpected Error", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
        #     await interaction.edit_original_response(embed = embed, view = None)
    
    lbGroup = app_commands.Group(name="lb-control", description="Control the leaderboard.")
    
    # Enable LB command
    @lbGroup.command(name = "enable", description = "Enable the message leaderboard.")
    @app_commands.default_permissions(administrator = True)
    async def enable_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        embed = discord.Embed(title = "Enabling...", color = Color.orange())
        await interaction.edit_original_response(embed = embed)

        try:
            if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{str(interaction.guild.id)}';").fetchone() != None:
                embed = discord.Embed(title = "Success", description = "Already enabled for this server.", color = Color.green())
                await interaction.edit_original_response(embed = embed)
            else:
                self.cursor.execute(f"CREATE TABLE '{interaction.guild.id}' (userMention text, messageCount integer, wordCount integer)")
                embed = discord.Embed(title = "Success", description = "Enabled message leaderboard for this server.", color = Color.green())
                await interaction.edit_original_response(embed = embed)
        except Exception:
            embed = discord.Embed(title = "Unexpected Error", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
            await interaction.edit_original_response(embed = embed, view = None)
    
    # Disable LB command
    @lbGroup.command(name = "disable", description = "Disable the message leaderboard.")
    @app_commands.default_permissions(administrator = True)
    async def disable_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        async def delete_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral = True)

            embed = discord.Embed(title = "Disabling...", color = Color.orange())
            await interaction.edit_original_response(embed = embed, view = None)

            try:
                if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{interaction.guild.id}';").fetchone() == None:
                    embed = discord.Embed(title = "Failed", description = "Leaderboard is already disabled in this server.", color = Color.red())
                    await interaction.edit_original_response(embed = embed)
                else:
                    self.cursor.execute(f"DROP TABLE '{interaction.guild.id}'")
                    embed = discord.Embed(title = "Disabled.", color = Color.green())
                    await interaction.edit_original_response(embed = embed)
            except Exception:
                embed = discord.Embed(title = "Unexpected Error", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
                await interaction.edit_original_response(embed = embed, view = None)
                
        view = View()
        delete_button = discord.ui.Button(label='Delete', style=discord.ButtonStyle.red)
        delete_button.callback = delete_callback
        view.add_item(delete_button)

        embed = discord.Embed(title = "Are you sure?", description = "The leaderboard will be disabled, and data for this server will be deleted!", color = Color.orange())
        await interaction.followup.send(embed = embed, view = view, ephemeral = True)
    
    # Reset LB command
    @lbGroup.command(name = "reset", description = "Resets the message leaderboard.")
    @app_commands.default_permissions(administrator = True)
    async def reset_lb(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        embed = discord.Embed(title = "Loading...", color = Color.orange())
        await interaction.followup.send(embed = embed, ephemeral = True)
        
        if self.cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{interaction.guild.id}';").fetchone() == None:
            embed = discord.Embed(title = "Disabled", description = "Leaderboard is disabled in this server.", color = Color.red())
            await interaction.edit_original_response(embed = embed)
        else:
            async def delete_callback(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral = True)

                embed = discord.Embed(title = "Resetting...", color = Color.orange())
                await interaction.edit_original_response(embed = embed, view = None)

                try:
                    self.cursor.execute(f"DELETE FROM '{interaction.guild.id}';")
                    embed = discord.Embed(title = "Reset.", color = Color.green())
                    await interaction.edit_original_response(embed = embed)
                except Exception:
                    embed = discord.Embed(title = "Unexpected Error", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
                    await interaction.edit_original_response(embed = embed, view = None)
                    
            view = View()
            delete_button = discord.ui.Button(label='Reset', style=discord.ButtonStyle.red)
            delete_button.callback = delete_callback
            view.add_item(delete_button)

            embed = discord.Embed(title = "Are you sure?", description = "The leaderboard will be reset and all data will be removed!", color = Color.orange())
            await interaction.edit_original_response(embed = embed, view = view)
        
async def setup(bot):
    await bot.add_cog(leaderboard(bot))