# Titanium v2
# Made by Restart, 2025

# Imports
import datetime
import logging
import os
from glob import glob
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from lib.classes.automod_message import AutomodMessage
from lib.setup_logger import setup_logging

# load the env variables
load_dotenv()

from lib.sql.sql import (  # noqa: E402
    AvailableWebhook,
    FireboardMessage,
    GuildAutomodSettings,
    GuildFireboardSettings,
    GuildLimits,
    GuildLoggingSettings,
    GuildModerationSettings,
    GuildPrefixes,
    GuildSettings,
    get_session,
    init_db,
)

# Current Running Path
path = os.getcwd()

# setup the logging
setup_logging()

init_logger: logging.Logger = logging.getLogger("init")
cache_logger: logging.Logger = logging.getLogger("cache")
db_logger: logging.Logger = logging.getLogger("db")

logging.info("Welcome to Titanium - v2 Development Version")
logging.info("https://github.com/restartb/titanium\n")


# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True


class TitaniumBot(commands.Bot):
    user_installs: int = 0
    guild_installs: int = 0
    guild_member_count: int = 0

    connect_time: datetime.datetime
    last_disconnect: Optional[datetime.datetime]
    last_resume: Optional[datetime.datetime]

    guild_configs: dict[int, GuildSettings] = {}
    guild_prefixes: dict[int, GuildPrefixes] = {}
    available_webhooks: dict[int, list[AvailableWebhook]] = {}
    automod_messages: dict[int, dict[int, list[AutomodMessage]]] = {}
    fireboard_messages: dict[int, list[FireboardMessage]] = {}

    punishing: dict[int, list[int]] = {}

    malicious_links: list[str] = []
    phishing_links: list[str] = []

    async def refresh_all_caches(self) -> None:
        cache_logger.info("Refreshing guild config caches...")

        async with get_session() as session:
            # Settings
            stmt = select(GuildSettings).options(selectinload("*"))
            result = await session.execute(stmt)
            configs = result.scalars().all()
            self.guild_configs.clear()

            for config in configs:
                self.guild_configs[config.guild_id] = config

            # Server prefixes
            stmt = select(GuildPrefixes).options(selectinload("*"))
            result = await session.execute(stmt)
            prefix_configs = result.scalars().all()
            self.guild_prefixes.clear()

            for config in prefix_configs:
                self.guild_prefixes[config.guild_id] = config

            # Available webhooks
            stmt = select(AvailableWebhook).options(selectinload("*"))
            result = await session.execute(stmt)
            webhook_configs = result.scalars().all()
            self.available_webhooks.clear()

            for webhook in webhook_configs:
                self.available_webhooks.setdefault(webhook.guild_id, []).append(webhook)

            # Fireboard messages
            stmt = select(FireboardMessage).options(selectinload("*"))
            result = await session.execute(stmt)
            fireboard_messages = result.scalars().all()
            self.fireboard_messages.clear()

            for message in fireboard_messages:
                self.fireboard_messages.setdefault(message.guild_id, []).append(message)

        cache_logger.info("Guild configs refreshed.")

    async def refresh_guild_config_cache(self, guild_id: int) -> None:
        cache_logger.info(f"Refreshing guild config cache for guild {guild_id}...")
        async with get_session() as session:
            # Settings
            if guild_id in self.guild_configs:
                del self.guild_configs[guild_id]

            stmt = (
                select(GuildSettings)
                .where(GuildSettings.guild_id == guild_id)
                .options(selectinload("*"))
            )
            result = await session.execute(stmt)
            config = result.scalar()
            if config:
                self.guild_configs[config.guild_id] = config

            # Server prefixes
            if guild_id in self.guild_prefixes:
                del self.guild_prefixes[guild_id]

            stmt = (
                select(GuildPrefixes)
                .where(GuildPrefixes.guild_id == guild_id)
                .options(selectinload("*"))
            )
            result = await session.execute(stmt)
            prefix_config = result.scalar()

            if prefix_config:
                self.guild_prefixes[prefix_config.guild_id] = prefix_config

            # Available webhooks
            if guild_id in self.available_webhooks:
                del self.available_webhooks[guild_id]

            stmt = (
                select(AvailableWebhook)
                .where(AvailableWebhook.guild_id == guild_id)
                .options(selectinload("*"))
            )
            result = await session.execute(stmt)
            webhook_configs = result.scalars().all()

            for webhook in webhook_configs:
                self.available_webhooks.setdefault(webhook.guild_id, []).append(webhook)

            # Fireboard messages
            if guild_id in self.fireboard_messages:
                del self.fireboard_messages[guild_id]

            stmt = (
                select(FireboardMessage)
                .where(FireboardMessage.guild_id == guild_id)
                .options(selectinload("*"))
            )
            result = await session.execute(stmt)
            fireboard_messages = result.scalars().all()
            self.fireboard_messages.clear()

            for message in fireboard_messages:
                self.fireboard_messages.setdefault(message.guild_id, []).append(message)

        cache_logger.info(f"Guild config cache for guild {guild_id} refreshed.")

    async def init_guild(self, guild_id: int) -> GuildSettings | None:
        db_logger.info(f"[INIT] Initializing guild {guild_id}...")

        async with get_session() as session:
            stmt = insert(GuildSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildModerationSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildAutomodSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildLoggingSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildFireboardSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildPrefixes).values(guild_id=guild_id, prefixes=["t!"])
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildLimits).values(id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
            await session.execute(stmt)

        await self.refresh_guild_config_cache(guild_id)

        db_logger.info(f"[INIT] Guild {guild_id} initialized.")
        return self.guild_configs.get(guild_id)

    async def setup_hook(self):
        try:
            await init_db()
        except Exception:
            raise

        await self.refresh_all_caches()

        init_logger.info("Getting custom emojis...")
        try:
            success_emoji = os.getenv("SUCCESS_EMOJI")
            if success_emoji and success_emoji.strip() != "":
                self.success_emoji = await self.fetch_application_emoji(
                    int(success_emoji)
                )
            else:
                self.success_emoji = "✅"

            error_emoji = os.getenv("ERROR_EMOJI")
            if error_emoji and error_emoji.strip() != "":
                self.error_emoji = await self.fetch_application_emoji(int(error_emoji))
            else:
                self.error_emoji = "❌"

            loading_emoji = os.getenv("LOADING_EMOJI")
            if loading_emoji and loading_emoji.strip() != "":
                self.loading_emoji = await self.fetch_application_emoji(
                    int(loading_emoji)
                )
            else:
                self.loading_emoji = "⏳"

            warn_emoji = os.getenv("WARN_EMOJI")
            if warn_emoji and warn_emoji.strip() != "":
                self.warn_emoji = await self.fetch_application_emoji(int(warn_emoji))
            else:
                self.warn_emoji = "⚠️"
        except discord.HTTPException as e:
            init_logger.error("Failed to fetch emojis")
            init_logger.exception(e)
            raise
        init_logger.info("Custom emojis loaded.\n")

        init_logger.info("Loading cogs...")
        # Find all cogs in command dir
        for filename in glob(
            os.path.join("cogs", "**"), recursive=True, include_hidden=False
        ):
            if not os.path.isdir(filename):
                # Determine if file is a python file
                if filename.endswith(".py") and not filename.startswith("."):
                    filename = filename.replace("\\", "/").replace("/", ".")[:-3]

                    init_logger.debug(f"Loading normal cog: {filename}...")
                    await bot.load_extension(filename)
                    init_logger.debug(f"Loaded normal cog: {filename}")
        init_logger.info("Loading cogs complete.\n")

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
        prefixes: GuildPrefixes = bot.guild_prefixes.get(message.guild.id)

        if prefixes and prefixes.prefixes is not None:
            base.extend(prefixes.prefixes)
        else:
            base.append("t!")
    else:
        base.append("t!")

    return commands.when_mentioned_or(*base)(bot, message)


bot = TitaniumBot(
    intents=intents, command_prefix=get_prefix, case_insensitive=True, max_messages=2500
)


@bot.event
async def on_ready():
    init_logger.info(f"Bot is ready and connected as {bot.user}.\n")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound) or isinstance(
        error, commands.NotOwner
    ):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Not Found",
            description=f"The command `{ctx.invoked_with}` does not exist.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    elif isinstance(error, commands.errors.MissingPermissions):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Missing Permissions",
            description=error,
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    elif isinstance(error, commands.errors.NoPrivateMessage):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Server Only Command",
            description="This command can only be used in servers.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    else:
        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Error",
            description="An error occurred while executing the command. Please try again later.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)

        logging.error(f"Error in command {ctx.command}: {error}")
        logging.exception(error)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
):
    if isinstance(error, discord.app_commands.CommandNotFound):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Not Found",
            description="The command does not exist.",
            colour=discord.Colour.red(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Error",
            description="An error occurred while executing the command. Please try again later.",
            colour=discord.Colour.red(),
        )
        await interaction.edit_original_response(embed=embed, view=None)

        logging.error(
            f"Error in command {interaction.command.name if interaction.command else 'unknown'}"
        )
        logging.exception(error)


if __name__ == "__main__":
    logging.info("Starting Titanium bot...")
    try:
        token = os.getenv("BOT_TOKEN")

        if token is None:
            raise discord.LoginFailure("No bot token provided in .env file.")

        bot.connect_time = datetime.datetime.now()
        bot.last_disconnect = None
        bot.last_resume = None

        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        logging.error("Invalid bot token provided. Please check your .env file.")
    except Exception as e:
        logging.error("An error occurred while starting the bot:")
        logging.exception(e)
