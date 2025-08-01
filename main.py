# Titanium v2
# Made by Restart, 2025

# Imports
import datetime
import logging
import logging.handlers
import os
from glob import glob

import discord
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

logging.info("Welcome to Titanium v2.")
logging.info("https://github.com/restartb/titanium\n")

# SQL path check
logging.info("[INIT] Checking SQL path...")
basedir = os.path.dirname("user-content/sql/")

if not os.path.exists(basedir):
    logging.info("[INIT] Path not present. Creating path...")
    os.makedirs(basedir)

# SQL path check
logging.info("[INIT] Checking temp path...")
basedir = os.path.dirname("user-content/tmp/")

if not os.path.exists(basedir):
    logging.info("[INIT] Path not present. Creating path...")
    os.makedirs(basedir)

logging.info("[INIT] Path check complete.\n")


# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True


class TitaniumBot(commands.Bot):
    user_installs = 0
    guild_installs = 0
    guild_member_count = 0

    connect_time: datetime.datetime

    punishing: dict[int, list[int]] = {}

    async def setup_hook(self):
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

        logging.info("[INIT] Loading cogs complete.\n")

    async def on_connect(self):
        self.connected = True

    async def on_resumed(self):
        self.connected = True
        self.last_resume = datetime.datetime.now()

    async def on_disconnect(self):
        if self.connected:
            self.connected = False
            self.last_disconnect = datetime.datetime.now()


bot = TitaniumBot(intents=intents, command_prefix="", help_command=None)
