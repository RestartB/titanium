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

# ------ Config File Reader ------
def readconfigfile(path):
    #Make dicts global
    global tokens_dict, options_dict

    # Set up reader
    import configparser
    config = configparser.RawConfigParser()

    # Read options section of config file, add it to dict
    try:
        config.read(path)
        tokens_dict = dict(config.items('TOKENS'))
    except Exception as error:
        print("[INIT] Config file malformed: Error while reading Tokens section! The file may be missing or malformed.")
        exit()

    # Read path section of config file, add it to dict
    try:
        config.read(path)
        options_dict = dict(config.items('OPTIONS'))
    except Exception as error:
        print("[INIT] Config file malformed: Error while reading Options section! The file may be missing or malformed.")
        exit()

# Bot Setup
intents = discord.Intents.default()
bot = commands.Bot(intents = intents, command_prefix = '')

# Read config files
readconfigfile('config.cfg')

# Config File Vars
bot.path = path
bot.pathtype = pathtype

bot.token = tokens_dict['discord-bot-token']
bot.spotify_id = tokens_dict['spotify-api-id']
bot.spotify_secret = tokens_dict['spotify-api-secret']

bot.dev_ids_str = options_dict['owner-ids'].split(",")
bot.support_server = options_dict['support-server']
if options_dict['cog-dir'] == '':
    bot.cog_dir = f"{path}{pathtype}commands{pathtype}"
else:
    bot.cog_dir = options_dict['cog-dir']
bot.cog_blacklist = options_dict['cog-blacklist']
if options_dict['sync-on-start'] == 'True':
    bot.sync_on_start = True
else:
    bot.sync_on_start = False

# Convert Dev IDs from str to int
bot.dev_ids = []
for id in bot.dev_ids_str:
    bot.dev_ids.append(int(id))

# Sync bot cogs when started
@bot.event
async def on_ready():
    print("[INIT] Loading cogs...")
    # Find all cogs in command dir
    for filename in os.listdir(bot.cog_dir):
        # Determine if file is a python file
        if filename.endswith("py"):
            # Don't load it if it's in the blocklist
            if filename[:-3] in bot.cog_blacklist:
                pass
            else:
                # We load it into the bot
                await bot.load_extension(f"commands.{filename[:-3]}")
    
    # Read cogs from private commands folder if it exists
    if os.path.exists(f"{path}{pathtype}commands-private{pathtype}"):
        # Find all cogs in private command dir
        for filename in os.listdir(f"{path}{pathtype}commands-private{pathtype}"):
            # Determine if file is a python file
            if filename.endswith("py"):
                # Don't load it if it's in the blocklist
                if filename[:-3] in bot.cog_blacklist:
                    pass
                else:
                    # We load it into the bot
                    await bot.load_extension(f"commands-private.{filename[:-3]}")

    print("[INIT] Loaded cogs.")

    # Sync tree if sync on start is enabled
    if bot.sync_on_start == True:
        print("[INIT] Syncing command tree...")
        sync = await bot.tree.sync()
        print(f"[INIT] Command tree synced. {len(sync)} commands loaded.")
    else:
        print("[INIT] Skipping command tree sync. Please manually sync commands later.")

    print(f"[INIT] Bot is ready and connected as {bot.user}.")

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
bot.run(bot.token)