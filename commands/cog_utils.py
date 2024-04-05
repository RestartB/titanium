import discord
from discord import app_commands, Color
import discord.ext
from discord.ext import commands
import os

class cog_utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Sync cogs command
    @app_commands.command(name = "sync-cogs", description = "Sync cogs.")
    @commands.is_owner()
    async def sync_cogs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        # Loading prompt
        embed = discord.Embed(title = "Syncing cogs...", color = Color.orange())
        await interaction.followup.send(embed = embed, ephemeral = True)
        
        # Find all cogs in command dir
        for filename in os.listdir(f"{self.bot.path}{self.bot.pathtype}commands{self.bot.pathtype}"):
            # If file is a Python file...
            if filename.endswith("py"):
                # We load it into the bot
                try:
                    await self.bot.load_extension(f"commands.{filename[:-3]}")
                except discord.ext.commands.errors.ExtensionAlreadyLoaded:
                    pass
        
        sync = await self.bot.tree.sync()
        embed = discord.Embed(title =  "Success!", description = f"Cogs synced. {len(sync)} commands loaded.", color = Color.green())
        await interaction.edit_original_response(embed = embed)

    # Load cog command
    @app_commands.command(name = "load-cog", description = "Load a cog.")
    @commands.is_owner()
    async def load(self, interaction:discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral = True)

        embed = discord.Embed(title = "Loading cog...", color = Color.orange())
        await interaction.followup.send(embed = embed, ephemeral = True)

        try:
            await self.bot.load_extension(f"commands.{cog}")

            embed = discord.Embed(title = f"Loaded {cog}!", color = Color.green())
            await interaction.edit_original_response(embed = embed)
        except Exception as error:
            embed = discord.Embed(title = "Error", description = f"Error while loading {cog}.\n\n{error}", color = Color.red())
            await interaction.edit_original_response(error = error)

    # Unload cog command
    @app_commands.command(name = "unload-cog", description = "Unload a cog.")
    @commands.is_owner()
    async def unload(self, interaction:discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral = True)

        embed = discord.Embed(title = "Unloading cog...", color = Color.orange())
        await interaction.followup.send(embed = embed, ephemeral = True)

        try:
            await self.bot.unload_extension(f"commands.{cog}")

            embed = discord.Embed(title = f"Unloaded {cog}!", color = Color.green())
            await interaction.edit_original_response(embed = embed)
        except Exception as error:
            embed = discord.Embed(title = "Error", description = f"Error while unloading {cog}.\n\n{error}", color = Color.red())
            await interaction.edit_original_response(error = error)

    # Tree sync command
    @app_commands.command(name = "tree-sync", description = "Sync the command tree.")
    @commands.is_owner()
    async def tree_sync(self, interaction:discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        # Loading prompt
        embed = discord.Embed(title = "Syncing tree...", color = Color.orange())
        await interaction.followup.send(embed = embed, ephemeral = True)

        sync = await self.bot.tree.sync()
        embed = discord.Embed(title =  "Success!", description = f"Tree synced. {len(sync)} commands loaded.", color = Color.green())
        await interaction.edit_original_response(embed = embed)

async def setup(bot):
    await bot.add_cog(cog_utils(bot))