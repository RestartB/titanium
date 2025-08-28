# Titanium v2
# Made by Restart, 2025

# Imports
import datetime
import logging
import logging.handlers
import os
import traceback
from glob import glob

import discord
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()

from lib.classes.automod_message import AutomodMessage  # noqa: E402
from lib.sql import (  # noqa: E402
    ServerAutomodSettings,
    ServerPrefixes,
    ServerSettings,
    get_session,
    init_db,
)

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

logging.info("Welcome to Titanium • v2")
logging.info("https://github.com/restartb/titanium\n")

# Temp path check
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

    server_configs: dict[int, ServerSettings] = {}
    server_prefixes: dict[int, ServerPrefixes] = {}
    server_automod_configs: dict[int, ServerAutomodSettings] = {}
    automod_messages: dict[int, dict[int, list[AutomodMessage]]] = {}

    punishing: dict[int, list[int]] = {}

    malicious_links: list[str] = []
    phishing_links: list[str] = []

    async def setup_hook(self):
        logging.info("[INIT] Initializing database...")
        await init_db()
        logging.info("[INIT] Database initialized.\n")

        logging.info("[INIT] Getting server configs...")
        async with get_session() as session:
            # Server settings
            stmt = select(ServerSettings)
            result = await session.execute(stmt)
            configs = result.scalars().all()

            for config in configs:
                self.server_configs[config.guild_id] = config

            # Automod settings
            stmt = select(ServerAutomodSettings)
            result = await session.execute(stmt)
            configs = result.scalars().all()

            for config in configs:
                self.server_automod_configs[config.guild_id] = config

            # Server prefixes
            stmt = select(ServerPrefixes)
            result = await session.execute(stmt)
            configs = result.scalars().all()

            for config in configs:
                self.server_prefixes[config.guild_id] = config
        logging.info("[INIT] Server configs loaded.")

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
        logging.info("[INIT] Custom emojis loaded.\n")

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

    async def on_connect(self):
        self.connected = True

    async def on_resumed(self):
        self.connected = True
        self.last_resume = datetime.datetime.now()

    async def on_disconnect(self):
        if self.connected:
            self.connected = False
            self.last_disconnect = datetime.datetime.now()


async def get_prefix(bot: TitaniumBot, message: discord.Message):
    base = []

    if message.guild:
        prefixes: ServerPrefixes = bot.server_prefixes.get(message.guild.id)

        if prefixes and prefixes.prefixes is not None:
            base.extend(prefixes.prefixes)
        else:
            base.append("t!")
    else:
        base.append("t!")

    return commands.when_mentioned_or(*base)(bot, message)


bot = TitaniumBot(intents=intents, command_prefix=get_prefix)


@bot.event
async def on_ready():
    logging.info(f"[INIT] Bot is ready and connected as {bot.user}.\n")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound) or isinstance(
        error, commands.NotOwner
    ):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Not Found",
            description=f"The command `{ctx.invoked_with}` does not exist.",
            color=discord.Color.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    elif isinstance(error, commands.errors.MissingPermissions):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Missing Permissions",
            description=error,
            color=discord.Color.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    elif isinstance(error, commands.errors.NoPrivateMessage):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Server Only Command",
            description="This command can only be used in servers.",
            color=discord.Color.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    else:
        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Error",
            description="An error occurred while executing the command. Please try again later.",
            color=discord.Color.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)

        logging.error(f"Error in command {ctx.command}: {error}")
        logging.error(
            "".join(traceback.format_exception(type(error), error, error.__traceback__))
        )


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
):
    if isinstance(error, discord.app_commands.CommandNotFound):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Not Found",
            description="The command does not exist.",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Error",
            description="An error occurred while executing the command. Please try again later.",
            color=discord.Color.red(),
        )
        await interaction.edit_original_response(embed=embed, view=None)

        logging.error(
            f"Error in command {interaction.command.name if interaction.command else 'unknown'}: {error}"
        )
        logging.error(
            "".join(traceback.format_exception(type(error), error, error.__traceback__))
        )


if __name__ == "__main__":
    logging.info("[INIT] Starting Titanium bot...")
    try:
        token = os.getenv("BOT_TOKEN")

        if token is None:
            raise discord.LoginFailure("No bot token provided in .env file.")

        bot.connect_time = datetime.datetime.now()
        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        logging.error("[INIT] Invalid bot token provided. Please check your .env file.")
    except Exception as e:
        logging.error(f"[INIT] An error occurred while starting the bot: {e}")
