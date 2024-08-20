# TitaniumCore
# Made by Restart, 2024

# Imports
import discord
from discord.ext import commands
from discord import Color
import os
import asyncio
import logging
from discord_webhook import AsyncDiscordWebhook, DiscordEmbed

print("Welcome to TitaniumCore.")
print("https://github.com/restartb/titaniumcore\n")

# Current Running Path
path = os.getcwd()

# Logging handler
handler = logging.FileHandler(filename='titanium.log', encoding='utf-8', mode='w')

# Set path type
if f"{os.name}" == "nt":
    pathtype = "\\"
    print(f"[INIT] OS name is {os.name}, path type {pathtype}\n")
else:
    pathtype = "/"
    print(f"[INIT] OS name is {os.name}, path type {pathtype}\n")

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
intents.members = True
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
    bot.control_server = options_dict['control-guild']
    bot.error_webhook = str(options_dict['error-webhook'])

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
    
    bot.loading_emoji = str(options_dict['loading-emoji'])
    bot.explicit_emoji = str(options_dict['explicit-emoji'])

    ## Convert Dev IDs from str to int
    # bot.blocked_ids = []
    # for id in bot.blocked_ids_str:
        # bot.blocked_ids.append(int(id))
    
    print("[INIT] Config files read.\n")
except Exception as error:
    print("[INIT] Bad value in config file! Exiting.")
    print(error)
    exit()

# Sync bot cogs when started
@bot.event
async def on_ready():
    # support_invite = await bot.fetch_invite(bot.support_server)
    # control_server = support_invite.guild
    # bot.control_server_id = control_server.id
    
    print("[INIT] Loading cogs...")
    # Find all cogs in command dir
    for filename in os.listdir(bot.cog_dir):
        # Determine if file is a python file
        if filename.endswith("py"):
            print(f"[INIT] Loading normal cog: {filename}...")
            await bot.load_extension(f"commands.{filename[:-3]}")
            print(f"[INIT] Loaded normal cog: {filename}")
    
    print("[INIT] Loaded normal cogs.\n")
    
    # Read cogs from private commands folder if it exists
    if os.path.exists(f"{path}{pathtype}commands_private{pathtype}"):
        print("[INIT] Loading private cogs...")
        # Find all cogs in private command dir
        for filename in os.listdir(f"{path}{pathtype}commands_private{pathtype}"):
            # Determine if file is a python file
            if filename.endswith("py"):
                # We load it into the bot
                print(f"[INIT] Loading private cog: {filename}...")
                await bot.load_extension(f"commands_private.{filename[:-3]}")
                print(f"[INIT] Loaded private cog: {filename}")

        print("[INIT] Loaded private cogs.\n")
    else:
        print("[INIT] Skipping private cogs.\n")

    # Sync tree if sync on start is enabled
    if bot.sync_on_start == True:
        # Global Sync
        print("[INIT] Syncing global command tree...")
        sync = await bot.tree.sync()
        print(f"[INIT] Global command tree synced.")
        
        # Control Server Sync
        print("[INIT] Syncing control server command tree...")
        guild = bot.get_guild(1213954608632700989)
        bot.tree.copy_global_to(guild=guild)
        sync = await bot.tree.sync(guild=guild)
        print(f"[INIT] Control server command tree synced. {len(sync)} commands total.")
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
            embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
            
            await interaction.edit_original_response(embed = embed, view=None)
        else:
            embed = discord.Embed(title = "Unexpected Error", description = "An unexpected error has occurred. Try again later. Info has been sent to the bot owner.", color = Color.red())
            embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
            
            await interaction.edit_original_response(embed = embed, view=None)

            webhookEmbed = DiscordEmbed(title="Error")
            webhookEmbed.set_timestamp()
            webhookEmbed.set_author(name=str(bot.user))

            webhookEmbed.add_embed_field(name="User", value=f"{interaction.user.mention}")
            webhookEmbed.add_embed_field(name="Channel", value=interaction.channel.jump_url)
            webhookEmbed.add_embed_field(name="Time", value=interaction.created_at.strftime("%d/%m//%Y, %H:%M:%S"))

            webhookEmbed.add_embed_field(name="Command", value=interaction.command.name)
            # webhookEmbed.add_embed_field(name="Arguments", value=", ".join(interaction.command.parameters))
            
            webhook = AsyncDiscordWebhook(url=str(bot.error_webhook), rate_limit_retry=True)
            webhook.add_embed(webhookEmbed)
            await webhook.execute()
    # Cooldown
    elif isinstance(error, discord.app_commands.errors.CommandOnCooldown):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(title = "Cooldown", description = error, color = Color.red())
        msg = await interaction.followup.send(embed = embed, ephemeral = True)
        await asyncio.sleep(5)
        await msg.delete()
    # Missing Perms
    elif isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(title = "Missing Permissions", description = error, color = Color.red())
        msg = await interaction.followup.send(embed = embed, ephemeral = True)
        await asyncio.sleep(5)
        await msg.delete()

try:
    # Run bot with token
    bot.run(bot.token, log_level=logging.ERROR)
except discord.errors.PrivilegedIntentsRequired:
    print("[FATAL] Bot is missing the Message Content and/or Server Members intent! Please enable it in the Discord Developers web portal. Exiting...")
    exit()
