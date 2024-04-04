# RestartBot discord.py Cogs Rewrite
# Restart, 2024

# This rewrite will soon become the main version of RestartBot. It is experimental currently and may contain bugs.

# Imports
import discord
from discord.ext import commands, tasks
from discord import Color
import os
import asyncio

# Current Running Path
path = os.getcwd()

# Set path type
if f"{os.name}" == "nt":
    pathtype = "\\"
    print(f"[INIT] OS name is {os.name}, path type {pathtype}")
else:
    pathtype = "/"
    print(f"[INIT] OS name is {os.name}, path type {pathtype}")

# Open Token Files
discord_token_file = open(f"{path}{pathtype}tokens{pathtype}discord_token.txt", "r")
discord_token = discord_token_file.read()
discord_token_file.close()

intents = discord.Intents.default()
bot = commands.Bot(intents = intents, command_prefix = '')

bot.path = path
bot.pathtype = pathtype

# Sync bot cogs when started
@bot.event
async def on_ready():
    print("[INIT] Syncing cogs...")
    # Find all cogs in command dir
    for filename in os.listdir(f"{path}{pathtype}commands{pathtype}"):
        # If file is a Python file...
        if filename.endswith("py"):
            print(filename)
            # We load it into the bot
            await bot.load_extension(f"commands.{filename[:-3]}")
    
    sync = await bot.tree.sync()
    print(f"[INIT] Cogs synced. {len(sync)} commands loaded.")

# Cooldown Handler
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
    await interaction.response.defer(ephemeral=True)
    if isinstance(error, discord.app_commands.errors.CommandOnCooldown):
        embed = discord.Embed(title = "Cooldown", description = error, color = Color.red())
        msg = await interaction.followup.send(embed = embed, ephemeral = True)
        await asyncio.sleep(5)
        await msg.delete()

# Run bot with token
bot.run(discord_token)