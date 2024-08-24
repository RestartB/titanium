import discord
from discord import app_commands, Color, ButtonStyle
import discord.ext
from discord.ext import commands
from discord.ui import View

import os
import utils.return_ctrlguild as ctrl
import asyncio
import datetime

class cog_utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=False)
    perms = discord.Permissions()

    target = ctrl.return_ctrlguild()
    adminGroup = app_commands.Group(name="admin", description="Control the bot. (admin only)", allowed_contexts=context, guild_ids=[target], default_permissions=perms)
    
    # Load cog command
    @adminGroup.command(name = "load", description = "Admin Only: load a cog.")
    async def load(self, interaction:discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral = True)

        if interaction.user.id in self.bot.dev_ids:
            try:
                await self.bot.load_extension(f"commands.{cog}")

                embed = discord.Embed(title = f"Loaded {cog}!", color = Color.green())
                await interaction.followup.send(embed = embed)
            except Exception as error:
                embed = discord.Embed(title = "Error", description = f"Error while loading {cog}.\n\n{error}", color = Color.red())
                await interaction.followup.send(embed = embed)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed)

    # Unload cog command
    @adminGroup.command(name = "unload", description = "Admin Only: unload a cog.")
    async def unload(self, interaction:discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral = True)

        if interaction.user.id in self.bot.dev_ids:
            try:
                if cog != "reminders":
                    await self.bot.unload_extension(f"commands.{cog}")

                    embed = discord.Embed(title = f"Unloaded {cog}!", color = Color.green())
                    await interaction.followup.send(embed = embed)
                else:
                    embed = discord.Embed(title = "Error", description = f"Error while unloading {cog}.\n\nCog is protected from unloading. Please reload the bot without the cog present to unload.", color = Color.red())
                    await interaction.followup.send(embed = embed)
            except Exception as error:
                embed = discord.Embed(title = "Error", description = f"Error while unloading {cog}.\n\n{error}", color = Color.red())
                await interaction.followup.send(embed = embed)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed)

    # Reload cog command
    @adminGroup.command(name = "reload", description = "Admin Only: reload a cog.")
    async def reload(self, interaction:discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral = True)

        if interaction.user.id in self.bot.dev_ids:
            try:
                if cog != "reminders":
                    await self.bot.reload_extension(f"commands.{cog}")

                    embed = discord.Embed(title = f"Reloaded {cog}!", color = Color.green())
                    await interaction.followup.send(embed = embed)
                else:
                    embed = discord.Embed(title = "Error", description = f"Error while unloading {cog}.\n\nCog is protected from reloading.", color = Color.red())
                    await interaction.followup.send(embed = embed)
            except Exception as error:
                embed = discord.Embed(title = "Error", description = f"Error while reloading {cog}.\n\n{error}", color = Color.red())
                await interaction.followup.send(embed = embed)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed)
    
    # Tree sync command
    @adminGroup.command(name = "sync", description = "Admin Only: sync the command tree.")
    async def tree_sync(self, interaction:discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        if interaction.user.id in self.bot.dev_ids:
            # Loading prompt
            embed = discord.Embed(title = "Syncing tree...", description=f"{self.bot.loading_emoji} This may take a moment.", color = Color.orange())
            await interaction.followup.send(embed = embed)

            # Global Sync
            print("[INIT] Syncing global command tree...")
            sync = await self.bot.tree.sync()
            print(f"[INIT] Global command tree synced.")
            
            # Control Server Sync
            print("[INIT] Syncing control server command tree...")
            guild = self.bot.get_guild(1213954608632700989)
            self.bot.tree.copy_global_to(guild=guild)
            sync = await self.bot.tree.sync(guild=guild)

            embed = discord.Embed(title =  "Success!", description = f"Tree synced. {len(sync)} commands loaded.", color = Color.green())
            await interaction.edit_original_response(embed = embed)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed)
    
    # Clear Console command
    @adminGroup.command(name = "clear-console", description = "Admin Only: clear the console.")
    async def clear_console(self, interaction: discord.Interaction,):
        await interaction.response.defer(ephemeral = True)
        
        if interaction.user.id in self.bot.dev_ids:
            os.system('cls' if os.name=='nt' else 'clear')

            await interaction.followup.send(f"Cleared the console.")
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed)
    
    # Send Message command
    @adminGroup.command(name = "send-message", description = "Admin Only: send debug message.")
    async def send_message(self, interaction: discord.Interaction, message: str, channel_id: str):
        await interaction.response.defer(ephemeral = True)
        
        if interaction.user.id in self.bot.dev_ids:
            channel = self.bot.get_channel(int(channel_id))
            
            embed = discord.Embed(title="Message from Bot Admin", description=message, color=Color.random())
            embed.timestamp = datetime.datetime.now()
            
            await channel.send(embed=embed)

            await interaction.followup.send(f"Message sent to channel ID {channel_id}.\n\nContent: {message}")
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed)
    
    # Server List command
    @adminGroup.command(name = "server-list", description = "Admin Only: get a list of all server guilds.")
    async def server_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)

        if interaction.user.id in self.bot.dev_ids:
            page = []
            pages = []
            
            for i, server in enumerate(self.bot.guilds):
                page.append(f"{i + 1}. {server} ({server.id}) ({server.member_count} members)")
                
                if (i + 1) % 20 == 0:
                    pages.append(page)
                    page = []
            
            if page != []:
                pages.append(page)
            
            class serversPageView(View):
                def __init__(self, pages):
                    super().__init__(timeout = 10800)
                    
                    self.page = 0
                    self.pages = pages

                    for item in self.children:
                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True
                
                async def on_timeout(self) -> None:
                    for item in self.children:
                        item.disabled = True

                    await self.message.edit(view=self)
            
                @discord.ui.button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
                async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.page = 0

                    for item in self.children:
                        item.disabled = False
                        
                        if item.custom_id == "first" or item.custom_id == "prev":
                            item.disabled = True
                    
                    embed = discord.Embed(title="Bot Servers", description="\n".join(self.pages[self.page]), color=Color.random())
                    embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)}")

                    await interaction.response.edit_message(embed = embed, view = self)
                
                @discord.ui.button(emoji="⏪", style=ButtonStyle.gray, custom_id="prev")
                async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if self.page - 1 == 0:
                        self.page -= 1

                        for item in self.children:
                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True
                    else:
                        self.page -= 1

                        for item in self.children:
                            item.disabled = False
                    
                    embed = discord.Embed(title="Bot Servers", description="\n".join(self.pages[self.page]), color=Color.random())
                    embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)}")

                    await interaction.response.edit_message(embed = embed, view = self)

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
                    
                    embed = discord.Embed(title="Bot Servers", description="\n".join(self.pages[self.page]), color=Color.random())
                    embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)}")
                    
                    await interaction.response.edit_message(embed = embed, view = self)
                
                @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
                async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.page = len(self.pages) - 1

                    for item in self.children:
                        item.disabled = False

                        if item.custom_id == "next" or item.custom_id == "last":
                            item.disabled = True
                    
                    embed = discord.Embed(title="Bot Servers", description="\n".join(self.pages[self.page]), color=Color.random())
                    embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)}")
                    
                    await interaction.response.edit_message(embed = embed, view = self)
                
            embed = discord.Embed(title="Bot Servers", description="\n".join(pages[0]), color=Color.random())
            embed.set_footer(text=f"Page 1/{len(pages)}")
            
            if len(pages) == 1:
                await interaction.edit_original_response(embed = embed)
            else:
                await interaction.edit_original_response(embed = embed, view = serversPageView(pages))
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed)
    
    # Error Test command
    @adminGroup.command(name = "error-test", description = "Admin Only: test the error handler. This WILL cause an error to occur!")
    async def error_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)

        if interaction.user.id in self.bot.dev_ids:
            embed = discord.Embed(title=f"Error Test", description="Error in 3 seconds...")
            await interaction.followup.send(embed=embed)

            await asyncio.sleep(3)
            raise Exception
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed)

async def setup(bot):
    await bot.add_cog(cog_utils(bot))