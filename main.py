# Titanium v2
# Made by Restart, 2025

# Imports
import logging
import logging.handlers
import os
from glob import glob

import discord
from discord.ext import commands
from dotenv import load_dotenv

from lib.sql import init_db

load_dotenv()

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

logging.info("Welcome to Titanium - v2")
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

    punishing: dict[int, list[int]] = {}

    async def setup_hook(self):
        logging.info("[INIT] Initializing database...")
        await init_db()
        logging.info("[INIT] Database initialized.\n")

        logging.info("[INIT] Getting custom emojis...")
        try:
            success_emoji = os.getenv("SUCCESS_EMOJI")
            if success_emoji is not None:
                self.success_emoji = await self.fetch_application_emoji(
                    int(success_emoji)
                )
            else:
                self.success_emoji = "✅"

            error_emoji = os.getenv("ERROR_EMOJI")
            if error_emoji is not None:
                self.error_emoji = await self.fetch_application_emoji(int(error_emoji))
            else:
                self.error_emoji = "❌"

            loading_emoji = os.getenv("LOADING_EMOJI")
            if loading_emoji is not None:
                self.loading_emoji = await self.fetch_application_emoji(
                    int(loading_emoji)
                )
            else:
                self.loading_emoji = "⏳"

            warn_emoji = os.getenv("WARN_EMOJI")
            if warn_emoji is not None:
                self.warn_emoji = await self.fetch_application_emoji(int(warn_emoji))
            else:
                self.warn_emoji = "⚠️"
        except discord.HTTPException as e:
            logging.error(f"[INIT] Failed to fetch emojis: {e}")
            raise

        logging.info("[INIT] Loading cogs...")
        # Find all cogs in command dir
        for filename in glob(
            os.path.join("cogs", "**"), recursive=True, include_hidden=False
        ):
            if not os.path.isdir(filename):
                # Determine if file is a python file
                if filename.endswith(".py") and not filename.startswith("."):
                    filename = filename.replace("\\", "/").replace("/", ".")[:-3]

                    logging.debug(f"[INIT] Loading normal cog: {filename}...")
                    await bot.load_extension(filename)
                    logging.debug(f"[INIT] Loaded normal cog: {filename}")
        logging.info("[INIT] Loading cogs complete.\n")


bot = TitaniumBot(intents=intents, command_prefix="t!")

if __name__ == "__main__":
    logging.info("[INIT] Starting Titanium bot...")
    try:
        token = os.getenv("BOT_TOKEN")

        if token is None:
            raise discord.LoginFailure("No bot token provided in .env file.")

        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        logging.error("[INIT] Invalid bot token provided. Please check your .env file.")
    except Exception as e:
        logging.error(f"[INIT] An error occurred while starting the bot: {e}")
