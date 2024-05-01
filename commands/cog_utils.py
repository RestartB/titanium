import discord
from discord import app_commands, Color
import discord.ext
from discord.ext import commands

class cog_utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    cogsGroup = app_commands.Group(name="cogs", description="Control cogs. (admin only)")

    # Load cog command
    @cogsGroup.command(name = "load", description = "Load a cog.")
    async def load(self, interaction:discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral = True)

        if interaction.user.id in self.bot.dev_ids:
            embed = discord.Embed(title = "Loading cog...", color = Color.orange())
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
    @cogsGroup.command(name = "unload", description = "Unload a cog.")
    async def unload(self, interaction:discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral = True)

        if interaction.user.id in self.bot.dev_ids:
            embed = discord.Embed(title = "Unloading cog...", color = Color.orange())
            await interaction.followup.send(embed = embed, ephemeral = True)

            try:
                await self.bot.unload_extension(f"commands.{cog}")

                embed = discord.Embed(title = f"Unloaded {cog}!", color = Color.green())
                await interaction.edit_original_response(embed = embed)
            except Exception as error:
                embed = discord.Embed(title = "Error", description = f"Error while unloading {cog}.\n\n{error}", color = Color.red())
                await interaction.edit_original_response(embed = embed)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral = True)

    # Reload cog command
    @cogsGroup.command(name = "reload", description = "Reload a cog.")
    async def reload(self, interaction:discord.Interaction, cog: str):
        await interaction.response.defer(ephemeral = True)

        if interaction.user.id in self.bot.dev_ids:
            embed = discord.Embed(title = "Reloading cog...", color = Color.orange())
            await interaction.followup.send(embed = embed, ephemeral = True)

            try:
                await self.bot.reload_extension(f"commands.{cog}")

                embed = discord.Embed(title = f"Reloaded {cog}!", color = Color.green())
                await interaction.edit_original_response(embed = embed)
            except Exception as error:
                embed = discord.Embed(title = "Error", description = f"Error while reloading {cog}.\n\n{error}", color = Color.red())
                await interaction.edit_original_response(embed = embed)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral = True)
    
    # Tree sync command
    @cogsGroup.command(name = "sync", description = "Sync the command tree.")
    async def tree_sync(self, interaction:discord.Interaction):
        await interaction.response.defer(ephemeral = True)
        
        if interaction.user.id in self.bot.dev_ids:
            # Loading prompt
            embed = discord.Embed(title = "Syncing tree...", color = Color.orange())
            await interaction.followup.send(embed = embed, ephemeral = True)

            sync = await self.bot.tree.sync()
            embed = discord.Embed(title =  "Success!", description = f"Tree synced. {len(sync)} commands loaded.", color = Color.green())
            await interaction.edit_original_response(embed = embed)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral = True)

async def setup(bot):
    await bot.add_cog(cog_utils(bot))