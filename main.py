# Titanium
# Made by Restart, 2024

# Imports
import asyncio
import datetime
import logging
import os
import traceback
from glob import glob

import aiohttp
import asqlite
import discord
from discord import Color
from discord.ext import commands

print("Welcome to Titanium.")
print("https://github.com/restartb/titanium\n")

# Current Running Path
path = os.getcwd()

# Logging handler
handler = logging.FileHandler(filename='titanium.log', encoding='utf-8', mode='w')

# SQL path check
print("[INIT] Checking SQL path...")
basedir = os.path.dirname("content/sql/")

if not os.path.exists(basedir):
    print("[INIT] Path not present. Creating path...")
    os.makedirs(basedir)

# SQL path check
print("[INIT] Checking temp path...")
basedir = os.path.dirname("tmp/")

if not os.path.exists(basedir):
    print("[INIT] Path not present. Creating path...")
    os.makedirs(basedir)

print("[INIT] Path check complete.\n")

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
        exit(1)

    # Read path section of config file, add it to dict
    try:
        config.read(path)
        options_dict = dict(config.items('OPTIONS'))
    except Exception:
        print("[INIT] Config file malformed: Error while reading Options section! The file may be missing or malformed.")
        exit(1)

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

class TitaniumBot(commands.Bot):
    async def setup_hook(self):
        print("[INIT] Creating SQL pools...")
        
        # Cache DB Pool
        open(os.path.join("content", "sql", "cache.db"), "a").close()
        self.cachePool = await asqlite.create_pool(os.path.join("content", "sql", "cache.db"))
        
        # Fireboard DB Pool
        open(os.path.join("content", "sql", "fireboard.db"), "a").close()
        self.fireboardPool = await asqlite.create_pool(os.path.join("content", "sql", "fireboard.db"))
        
        # Leaderboard DB Pool
        open(os.path.join("content", "sql", "lb.db"), "a").close()
        self.lbPool = await asqlite.create_pool(os.path.join("content", "sql", "lb.db"))

        # Isolation DB Pool
        open(os.path.join("content", "sql", "isolated.db"), "a").close()
        self.isolationPool = await asqlite.create_pool(os.path.join("content", "sql", "isolated.db"))
        
        # Edit History DB Pool
        open(os.path.join("content", "sql", "editHistory.db"), "a").close()
        self.editPool = await asqlite.create_pool(os.path.join("content", "sql", "editHistory.db"))

        # Economy Pool
        open(os.path.join("content", "sql", "economy.db"), "a").close()
        self.economyPool = await asqlite.create_pool(os.path.join("content", "sql", "economy.db"))

        print("[INIT] SQL pools created.\n")
        
        print("[INIT] Loading cogs...")
        # Find all cogs in command dir
        for filename in glob(os.path.join("commands", "**"), recursive=True, include_hidden=False):
            if os.path.isdir(filename) == False:
                # Determine if file is a python file
                if filename.endswith(".py") and not filename.startswith("."):
                    filename = filename.replace("\\", "/").replace("/", ".")[:-3]
                    
                    print(f"[INIT] Loading normal cog: {filename}...")
                    await bot.load_extension(filename)
                    print(f"[INIT] Loaded normal cog: {filename}")
        
        print("[INIT] Loaded normal cogs.\n")
        
        # Read cogs from private commands folder if it exists
        if os.path.exists(f"commands_private"):
            print("[INIT] Loading private cogs...")
            # Find all cogs in private command dir
            for filename in os.listdir(f"commands_private"):
                # Determine if file is a python file
                if filename.endswith(".py") and not filename.startswith("."):
                    print(f"[INIT] Loading private cog: {filename}...")
                    await bot.load_extension(f"commands_private.{filename[:-3]}")
                    print(f"[INIT] Loaded private cog: {filename}")

            print("[INIT] Loaded private cogs.\n")
        else:
            print("[INIT] Skipping private cogs.\n")
    
    async def close(self):
        await self.cachePool.close()
        await self.fireboardPool.close()
        await self.lbPool.close()
        await super().close()

bot = TitaniumBot(intents=intents, command_prefix='', help_command=None)

print("[INIT] Reading config files.")

# Read config files
readconfigfile('config.cfg')

# Config File Vars
try:
    bot.path = path

    bot.token = tokens_dict['discord-bot-token']
    bot.spotify_id = tokens_dict['spotify-api-id']
    bot.spotify_secret = tokens_dict['spotify-api-secret']
    # bot.reviewdb_token = tokens_dict['reviewdb-token']
    
    bot.dev_ids_str = options_dict['owner-ids'].split(",")
    bot.support_server = options_dict['support-server']
    bot.control_server = options_dict['control-guild']
    bot.error_webhook = str(options_dict['error-webhook'])

    if options_dict['cog-dir'] == '':
        bot.cog_dir = "commands"
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
    
    bot.loading_emoji = str(options_dict['loading-emoji'])
    bot.explicit_emoji = str(options_dict['explicit-emoji'])
    
    print("[INIT] Config files read.\n")
except Exception as error:
    print("[INIT] Bad value in config file! Exiting.")
    print(error)
    exit()

# Sync bot cogs when started
@bot.event
async def on_ready():
    # Sync tree if sync on start is enabled
    if bot.sync_on_start == True:
        # Control Server Sync
        print("[INIT] Syncing control server command tree...")
        guild = bot.get_guild(1213954608632700989)
        sync = await bot.tree.sync(guild=guild)
        print(f"[INIT] Control server command tree synced. {len(sync)} command total.")
        
        # Global Sync
        print("[INIT] Syncing global command tree...")
        sync = await bot.tree.sync(guild=None)
        print(f"[INIT] Global command tree synced. {len(sync)} commands total.")
        
    else:
        print("[INIT] Skipping command tree sync. Please manually sync commands later.")
    
    print(f"[INIT] Bot is ready and connected as {bot.user}.")

# Ignore normal user messages
@bot.event
async def on_message(message):
    pass

# Cooldown / No Permissions / Error Handler
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
    # Unexpected Error
    if isinstance(error, discord.app_commands.errors.CommandInvokeError):
        if bot.error_webhook == "":
            embed = discord.Embed(title = "Unexpected Error", description = "An unexpected error has occurred. Try again later.", color = Color.red())
            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
            
            await interaction.edit_original_response(embed = embed, view=None)
        else:
            embed = discord.Embed(title = "Unexpected Error", description = "An unexpected error has occurred. Try again later. Info has been sent to the bot owner.", color = Color.red())
            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
            
            await interaction.edit_original_response(embed = embed, view=None)

            async with aiohttp.ClientSession() as session:
                embed = discord.Embed(title="Error", description=f"""```python\n{traceback.format_exc()}```""", color=Color.red())
                
                embed.timestamp = datetime.datetime.now()
                embed.set_author(name=str(bot.user))

                embed.add_field(name="User", value=f"{interaction.user.mention}")
                embed.add_field(name="Channel", value=interaction.channel.jump_url)
                embed.add_field(name="Time", value=interaction.created_at.strftime("%d/%m/%Y, %H:%M:%S"))

                embed.add_field(name="Command", value=interaction.command.name)
                embed.add_field(name="Parameters", value=", ".join(f"{param.name}: {interaction.namespace[param.name]}" for param in interaction.command.parameters))

                webhook = discord.Webhook.from_url(str(bot.error_webhook), session=session)
                await webhook.send(embed=embed)
    # Cooldown
    elif isinstance(error, discord.app_commands.errors.CommandOnCooldown):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(title = "Cooldown", description = error, color = Color.red())
        msg = await interaction.followup.send(embed = embed)
        
        await asyncio.sleep(5)
        
        await msg.delete()
    # Missing Perms
    elif isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(title = "Missing Permissions", description = error, color = Color.red())
        msg = await interaction.followup.send(embed = embed)
        
        await asyncio.sleep(5)
        
        await msg.delete()

try:
    # Run bot with token
    bot.run(bot.token, log_handler=handler, log_level=logging.INFO)
except discord.errors.PrivilegedIntentsRequired:
    print("[FATAL] Bot is missing the Message Content and/or Server Members intent! Please enable it in the Discord Developers web portal. Exiting...")
    exit()
