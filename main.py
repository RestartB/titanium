# Titanium
# Made by Restart, 2024 - 2025

# Imports
import asyncio
import configparser
import datetime
import logging
import logging.handlers
import os
import traceback
from glob import glob

from utils.truncate import truncate
import aiohttp
import asqlite
import discord
from discord import Color
from discord.ext import commands

# Current Running Path
path = os.getcwd()

# Create Root Logger
dt_fmt = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}] [{levelname:<8}] {name}: {message}",
    datefmt=dt_fmt,
    style="{",
)

# Get loggers
rootLogger = logging.getLogger()
discordLogger = logging.getLogger("discord")
discordLogger.setLevel(logging.INFO)

# Make file handler
(os.mkdir("logs") if not os.path.exists("logs") else None)
handler = logging.handlers.RotatingFileHandler(
    filename="logs/titanium.log",
    encoding="utf-8",
    maxBytes=20 * 1024 * 1024,  # 20 MiB
    backupCount=5,  # Rotate through 5 files
)

# Set formatter, apply to file and console handlers
formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
)
handler.setFormatter(formatter)
rootLogger.handlers[0].setFormatter(formatter)

# Add loggers to file handler
rootLogger.addHandler(handler)
discordLogger.addHandler(handler)

logging.info("Welcome to Titanium.")
logging.info("https://github.com/restartb/titanium\n")

# Config Parser
config = configparser.RawConfigParser()

# SQL path check
logging.info("[INIT] Checking SQL path...")
basedir = os.path.dirname("content/sql/")

if not os.path.exists(basedir):
    logging.info("[INIT] Path not present. Creating path...")
    os.makedirs(basedir)

# SQL path check
logging.info("[INIT] Checking temp path...")
basedir = os.path.dirname("tmp/")

if not os.path.exists(basedir):
    logging.info("[INIT] Path not present. Creating path...")
    os.makedirs(basedir)

logging.info("[INIT] Path check complete.\n")


# ------ Config File Reader ------
def read_config_file(path) -> tuple[dict, dict]:
    # Read options section of config file, add it to dict
    try:
        config.read(path)
        tokens = dict(config.items("TOKENS"))
    except Exception:
        logging.critical(
            "[INIT] Config file malformed: Error while reading Tokens section! The file may be missing or malformed."
        )
        exit(1)

    # Read path section of config file, add it to dict
    try:
        config.read(path)
        options = dict(config.items("OPTIONS"))
    except Exception:
        logging.critical(
            "[INIT] Config file malformed: Error while reading Options section! The file may be missing or malformed."
        )
        exit(1)

    global discord_token
    discord_token = tokens["discord-bot-token"]

    return options, tokens


# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True


class TitaniumBot(commands.Bot):
    async def setup_hook(self):
        logging.info("[INIT] Reading config files.")

        # Read config files
        self.options, self.tokens = read_config_file("config.cfg")

        # Config File Vars
        try:
            self.path = path

            self.options["owner-ids"] = self.options["owner-ids"].split(",")

            if self.options["sync-on-start"] == "True":
                self.options["sync-on-start"] = True
            else:
                self.options["sync-on-start"] = False

            # Convert Dev IDs from str to int
            dev_ids = []
            for id in self.options["owner-ids"]:
                dev_ids.append(int(id))

            self.options["owner-ids"] = dev_ids

            logging.info("[INIT] Config files read.\n")
        except Exception as error:
            logging.critical("[INIT] Bad value in config file! Exiting.")
            logging.critical(error)

            exit(1)

        logging.info("[INIT] Creating SQL pools...")

        # Cache DB Pool
        open(os.path.join("content", "sql", "cache.db"), "a").close()
        self.cache_pool = await asqlite.create_pool(
            os.path.join("content", "sql", "cache.db")
        )

        # Fireboard DB Pool
        open(os.path.join("content", "sql", "fireboard.db"), "a").close()
        self.fireboard_pool = await asqlite.create_pool(
            os.path.join("content", "sql", "fireboard.db")
        )

        # Leaderboard DB Pool
        open(os.path.join("content", "sql", "lb.db"), "a").close()
        self.lb_pool = await asqlite.create_pool(
            os.path.join("content", "sql", "lb.db")
        )

        # Economy Pool
        open(os.path.join("content", "sql", "economy.db"), "a").close()
        self.economy_pool = await asqlite.create_pool(
            os.path.join("content", "sql", "economy.db")
        )

        # Tags Pool
        open(os.path.join("content", "sql", "tags.db"), "a").close()
        self.tags_pool = await asqlite.create_pool(
            os.path.join("content", "sql", "tags.db")
        )

        logging.info("[INIT] SQL pools created.\n")

        logging.info("[INIT] Loading cogs...")
        # Find all cogs in command dir
        for filename in glob(
            os.path.join("commands", "**"), recursive=True, include_hidden=False
        ):
            if not os.path.isdir(filename):
                # Determine if file is a python file
                if filename.endswith(".py") and not filename.startswith("."):
                    filename = filename.replace("\\", "/").replace("/", ".")[:-3]

                    logging.debug(f"[INIT] Loading normal cog: {filename}...")
                    await bot.load_extension(filename)
                    logging.debug(f"[INIT] Loaded normal cog: {filename}")

        logging.info("[INIT] Loaded normal cogs.\n")

        # Read cogs from private commands folder if it exists
        if os.path.exists("commands_private"):
            logging.info("[INIT] Loading private cogs...")
            # Find all cogs in private command dir
            for filename in os.listdir("commands_private"):
                # Determine if file is a python file
                if filename.endswith(".py") and not filename.startswith("."):
                    logging.debug(f"[INIT] Loading private cog: {filename}...")
                    await bot.load_extension(f"commands_private.{filename[:-3]}")
                    logging.debug(f"[INIT] Loaded private cog: {filename}")

            logging.info("[INIT] Loaded private cogs.\n")
        else:
            logging.info("[INIT] Skipping private cogs.\n")

    async def close(self):
        await self.cache_pool.close()
        await self.fireboard_pool.close()
        await self.lb_pool.close()
        await super().close()


bot = TitaniumBot(intents=intents, command_prefix="", help_command=None)


# Sync bot cogs when started
@bot.event
async def on_ready():
    # Sync tree if sync on start is enabled
    if bot.options["sync-on-start"]:
        # Control Server Sync
        logging.info("[INIT] Syncing control server command tree...")
        guild = bot.get_guild(1213954608632700989)
        sync = await bot.tree.sync(guild=guild)
        logging.info(
            f"[INIT] Control server command tree synced. {len(sync)} command total."
        )

        # Global Sync
        logging.info("[INIT] Syncing global command tree...")
        sync = await bot.tree.sync(guild=None)
        logging.info(f"[INIT] Global command tree synced. {len(sync)} commands total.")

    else:
        logging.info(
            "[INIT] Skipping command tree sync. Please manually sync commands later."
        )

    logging.info(f"[INIT] Bot is ready and connected as {bot.user}.\n")


# Ignore normal user messages
@bot.event
async def on_message(message):
    pass


# Cooldown / No Permissions / Error Handler
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
) -> None:
    # Unexpected Error
    if isinstance(error, discord.app_commands.errors.CommandInvokeError):
        if isinstance(error.original, discord.errors.HTTPException):
            if "automod" in str(error.original).lower():
                embed = discord.Embed(
                    title="Error",
                    description="Message has been blocked by server AutoMod policies. Server admins may have been notified.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            logging.error("*** Unexpected error occurred. ***")
            logging.error(f"{traceback.format_exc()}\n")

            if bot.options["error-webhook"] == "":
                logging.info("\nNo error webhook present. Editing user message.\n")

                embed = discord.Embed(
                    title="Unexpected Error",
                    description="An unexpected error has occurred. Try again later.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.edit_original_response(embed=embed, view=None)
            else:
                logging.info("Editing user message.")

                embed = discord.Embed(
                    title="Unexpected Error",
                    description="An unexpected error has occurred. Try again later. Info has been sent to the bot owner.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.edit_original_response(embed=embed, view=None)

                async with aiohttp.ClientSession() as session:
                    logging.info("Sending error to webhook.")
                    embed = discord.Embed(
                        title="Error",
                        description=f"```python\n{truncate(traceback.format_exc(), 4096, '```')}{'```' if len(traceback.format_exc()) > 4096 else ''}",
                        color=Color.red(),
                    )

                    embed.timestamp = datetime.datetime.now()
                    embed.set_author(name=str(bot.user))

                    embed.add_field(name="User", value=f"{interaction.user.mention}")
                    embed.add_field(name="Channel", value=interaction.channel.jump_url)
                    embed.add_field(
                        name="Time",
                        value=interaction.created_at.strftime("%d/%m/%Y, %H:%M:%S"),
                    )

                    embed.add_field(name="Command", value=interaction.command.name)

                    # Safely get parameters if they exist
                    try:
                        params = []
                        for param in interaction.command.parameters:
                            if param.name in interaction.namespace:
                                params.append(
                                    f"{param.name}: {interaction.namespace[param.name]}"
                                )
                        if params:
                            embed.add_field(name="Parameters", value=", ".join(params))
                    except Exception:
                        pass

                    try:
                        webhook = discord.Webhook.from_url(
                            str(bot.options["error-webhook"]), session=session
                        )
                        await webhook.send(embed=embed)

                        logging.info("Error sent to webhook.\n")
                    except Exception as webhookException:
                        logging.error(f"Error sending to webhook: {webhookException}\n")
    # Cooldown
    elif isinstance(error, discord.app_commands.errors.CommandOnCooldown):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(title="Cooldown", description=error, color=Color.red())
        msg = await interaction.followup.send(embed=embed)

        await asyncio.sleep(5)

        await msg.delete()
    # Missing Perms
    elif isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="Missing Permissions", description=error, color=Color.red()
        )
        msg = await interaction.followup.send(embed=embed)

        await asyncio.sleep(5)

        await msg.delete()


try:
    config.read("config.cfg")
    bot_token = dict(config.items("TOKENS"))["discord-bot-token"]

    # Run bot with token
    bot.run(bot_token, log_handler=None)
except discord.errors.PrivilegedIntentsRequired:
    logging.critical(
        "[FATAL] Bot is missing a Privileged Intent! Please ensure they are enabled in the Discord Developers web portal. Exiting..."
    )
    exit(1)
