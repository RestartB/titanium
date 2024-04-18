# RestartBot v2
# Made by Restart, 2024

# Welcome to the rewritten version of RestartBot, now using cogs.

# Imports
import discord
from discord.ext import commands
from discord import Color
import os
import asyncio
import logging

print("Welcome to RestartBot!")

# Current Running Path
path = os.getcwd()

# Logging handler
handler = logging.FileHandler(filename='discord_critical.log', encoding='utf-8', mode='w')

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
    except Exception:
        print("[INIT] Config file malformed: Error while reading Tokens section! The file may be missing or malformed.")
        exit()

    # Read path section of config file, add it to dict
    try:
        config.read(path)
        options_dict = dict(config.items('OPTIONS'))
    except Exception:
        print("[INIT] Config file malformed: Error while reading Options section! The file may be missing or malformed.")
        exit()

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(intents = intents, command_prefix = '')

print("[INIT] Reading config files.")

# Read config files
readconfigfile('config.cfg')

# Config File Vars
try:
    bot.path = path
    bot.pathtype = pathtype

    bot.token = tokens_dict['discord-bot-token']
    bot.spotify_id = tokens_dict['spotify-api-id']
    bot.spotify_secret = tokens_dict['spotify-api-secret']

    bot.dev_ids_str = options_dict['owner-ids'].split(",")
    bot.support_server = options_dict['support-server']
    bot.cog_blacklist = options_dict['cog-blacklist']
    # bot.blocked_ids_str = options_dict['user-blacklist'].split(",")

    if options_dict['cog-dir'] == '':
        bot.cog_dir = f"{path}{pathtype}commands{pathtype}"
    else:
        bot.cog_dir = options_dict['cog-dir']
    
    if options_dict['sync-on-start'] == 'True':
        bot.sync_on_start = True
    else:
        bot.sync_on_start = False

    # Convert Dev IDs from str to int
    bot.dev_ids = []
    for id in bot.dev_ids_str:
        bot.dev_ids.append(int(id))

    ## Convert Dev IDs from str to int
    # bot.blocked_ids = []
    # for id in bot.blocked_ids_str:
        # bot.blocked_ids.append(int(id))
    
    print("[INIT] Config files read.")
except Exception as error:
    print("[INIT] Bad value in config file! Exiting.")
    print(error)
    exit()

# Sync bot cogs when started
@bot.event
async def on_ready():
    while True:
        user_input = input("Select cog to load: ")
        await bot.load_extension(f"commands.{user_input}")

# Ignore normal user messages
@bot.event
async def on_message(message):
    pass

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
bot.run(bot.token, log_handler=handler, log_level=logging.CRITICAL)