# RestartBot discord.py Cogs Rewrite
# restartb, 2024

# This rewrite will soon become the main version of RestartBot. It is experimental currently and may contain bugs.

# Imports
import discord
from discord.ext import commands, tasks
import os

# Client class
class aclient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.synced = False
    
    async def on_ready(self):
        await self.wait_until_ready()
        if self.synced == False:
            await tree.sync()
            self.synced = True
            print("[INIT] Commands synced.")
        print(f"[INIT] We have logged into Discord as {self.user}!")

# Define client and command tree
client = aclient()
tree = discord.app_commands.CommandTree(client)

# Sync cogs command
@tree.command(name = "sync", description = "Sync cogs.")
async def self(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral = True)
    embed = discord.Embed(title = "Syncing cogs...")
    await interaction.followup.send(embed = embed, ephemeral = True)
    
    for filename in os.listdir("./cogs"):
        if filename.endswith("py"):
            await client.load_extension(f"{filename}.py")
    
    synced = await tree.sync()
    print(f"Synced {len(synced)} command(s).")
