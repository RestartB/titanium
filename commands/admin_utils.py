import discord
from discord import app_commands, Color
import discord.ext
from discord.ext import commands
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
            embed = discord.Embed(title = "Loading cog...", description=f"{self.bot.loading_emoji} Loading {cog}.", color = Color.orange())
            await interaction.followup.send(embed = embed, ephemeral = True)

            try:
                await self.bot.load_extension(f"commands.{cog}")

                embed = discord.Embed(title = f"Loaded {cog}!", color = Color.green())
                await interaction.edit_original_response(embed = embed)
            except Exception as error:
                embed = discord.Embed(title = "Error", description = f"Error while loading {cog}.\n\n{error}", color = Color.red())
                await interaction.edit_original_response(embed = embed)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral = True)

    # Unload cog command
    @adminGroup.command(name = "unload", description = "Admin Only: unload a cog.")
    async def unload(self, interaction:discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral = True)

        if interaction.user.id in self.bot.dev_ids:
            embed = discord.Embed(title = "Unloading cog...", description=f"{self.bot.loading_emoji} Unloading {cog}.", color = Color.orange())
            await interaction.followup.send(embed = embed, ephemeral = True)

            try:
                if cog != "reminders":
                    await self.bot.unload_extension(f"commands.{cog}")

                    embed = discord.Embed(title = f"Unloaded {cog}!", color = Color.green())
                    await interaction.edit_original_response(embed = embed)
                else:
                    embed = discord.Embed(title = "Error", description = f"Error while unloading {cog}.\n\nCog is protected from unloading. Please reload the bot without the cog present to unload.", color = Color.red())
                    await interaction.edit_original_response(embed = embed)
            except Exception as error:
                embed = discord.Embed(title = "Error", description = f"Error while unloading {cog}.\n\n{error}", color = Color.red())
                await interaction.edit_original_response(embed = embed)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral = True)

    # Reload cog command
    @adminGroup.command(name = "reload", description = "Admin Only: reload a cog.")
    async def reload(self, interaction:discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral = True)

        if interaction.user.id in self.bot.dev_ids:
            embed = discord.Embed(title = "Reloading cog...", description=f"{self.bot.loading_emoji} Reloading {cog}.", color = Color.orange())
            await interaction.followup.send(embed = embed, ephemeral = True)

            try:
                if cog != "reminders":
                    await self.bot.reload_extension(f"commands.{cog}")

                    embed = discord.Embed(title = f"Reloaded {cog}!", color = Color.green())
                    await interaction.edit_original_response(embed = embed)
                else:
                    embed = discord.Embed(title = "Error", description = f"Error while unloading {cog}.\n\nCog is protected from reloading.", color = Color.red())
                    await interaction.edit_original_response(embed = embed)
            except Exception as error:
                embed = discord.Embed(title = "Error", description = f"Error while reloading {cog}.\n\n{error}", color = Color.red())
                await interaction.edit_original_response(embed = embed)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral = True)
    
    # Tree sync command
    @adminGroup.command(name = "sync", description = "Admin Only: sync the command tree.")
    async def tree_sync(self, interaction:discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        if interaction.user.id in self.bot.dev_ids:
            # Loading prompt
            embed = discord.Embed(title = "Syncing tree...", description=f"{self.bot.loading_emoji} This may take a moment.", color = Color.orange())
            await interaction.followup.send(embed = embed, ephemeral = True)

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
            await interaction.followup.send(embed = embed, ephemeral = True)
    
    # Clear Console command
    @adminGroup.command(name = "clear-console", description = "Admin Only: clear the console.")
    async def clear_console(self, interaction: discord.Interaction,):
        await interaction.response.defer(ephemeral = True)
        
        if interaction.user.id in self.bot.dev_ids:
            os.system('cls' if os.name=='nt' else 'clear')

            await interaction.followup.send(f"Cleared the console.", ephemeral = True)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral = True)
    
    # Send Message command
    @adminGroup.command(name = "send-message", description = "Admin Only: send debug message.")
    async def send_message(self, interaction: discord.Interaction, message: str, channel_id: str):
        await interaction.response.defer(ephemeral = True)
        
        if interaction.user.id in self.bot.dev_ids:
            channel = self.bot.get_channel(int(channel_id))
            embed = discord.Embed(title="Message from Bot Admin", description=message, color=Color.random())
            embed.timestamp = datetime.datetime.now()
            
            await channel.send(message)

            await interaction.followup.send(f"Message sent to channel ID {channel_id}.\n\nContent: {message}", ephemeral = True)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral = True)
    
    # Server List command
    @adminGroup.command(name = "server-list", description = "Admin Only: get a list of all server guilds.")
    async def server_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)

        embed = discord.Embed(title=f"Error Test", description="Error in 3 seconds...")
        await interaction.followup.send(embed=embed)

        await asyncio.sleep(3)
        raise Exception
    
    # Error Test command
    @adminGroup.command(name = "error-test", description = "Admin Only: test the error handler. This WILL cause an error to occur!")
    async def error_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)

        embed = discord.Embed(title=f"Error Test", description="Error in 3 seconds...")
        await interaction.followup.send(embed=embed)

        await asyncio.sleep(3)
        raise Exception

async def setup(bot):
    await bot.add_cog(cog_utils(bot))