# Titanium v2
# Made by Restart, 2025

# Imports
import asyncio
import datetime
import logging
import os
import sys
from glob import glob
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from lib.classes.automod_message import AutomodMessage
from lib.helpers.hybrid_adapters import SlashCommandOnly
from lib.helpers.log_error import log_error
from lib.setup_logger import setup_logging
from v1_to_v2.migrate import migrate_v1_to_v2

# load the env variables
load_dotenv()

from lib.sql.sql import (  # noqa: E402
    AvailableWebhook,
    FireboardMessage,
    GuildAutomodSettings,
    GuildBouncerSettings,
    GuildConfessionsSettings,
    GuildFireboardSettings,
    GuildLeaderboardSettings,
    GuildLimits,
    GuildLoggingSettings,
    GuildModerationSettings,
    GuildPrefixes,
    GuildServerCounterSettings,
    GuildSettings,
    OptOutIDs,
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
logging.info("https://github.com/restartb/titanium")


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
    guild_limits: dict[int, GuildLimits] = {}
    available_webhooks: dict[int, list[AvailableWebhook]] = {}
    automod_messages: dict[int, dict[int, list[AutomodMessage]]] = {}
    fireboard_messages: dict[int, list[FireboardMessage]] = {}

    punishing: dict[int, list[int]] = {}

    malicious_links: list[str] = []
    phishing_links: list[str] = []
    nsfw_links: list[str] = []

    opt_out: list[int] = []

    async def refresh_opt_out(self) -> None:
        cache_logger.info("Refreshing opt-out IDs...")

        async with get_session() as session:
            stmt = select(OptOutIDs)
            result = await session.execute(stmt)
            opt_out_ids = result.scalars().all()
            self.opt_out.clear()

            for opt_out in opt_out_ids:
                self.opt_out.append(opt_out.id)

        cache_logger.info("Opt-out IDs refreshed.")

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

            # Guild limits
            stmt = select(GuildLimits).options(selectinload("*"))
            result = await session.execute(stmt)
            limit_configs = result.scalars().all()
            self.guild_limits.clear()

            for config in limit_configs:
                self.guild_limits[config.id] = config

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
            stmt = (
                select(GuildPrefixes)
                .where(GuildPrefixes.guild_id == guild_id)
                .options(selectinload("*"))
            )
            result = await session.execute(stmt)
            prefix_config = result.scalar()

            if prefix_config:
                self.guild_prefixes[prefix_config.guild_id] = prefix_config

            # Guild limits
            stmt = select(GuildLimits).where(GuildLimits.id == guild_id).options(selectinload("*"))
            result = await session.execute(stmt)
            limit_config = result.scalar()

            if limit_config:
                self.guild_limits[limit_config.id] = limit_config

            # Available webhooks
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

    async def init_guild(self, guild_id: int, refresh: bool = True) -> GuildSettings | None:
        db_logger.info(f"Initializing guild {guild_id}...")

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

            stmt = insert(GuildBouncerSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildLoggingSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildFireboardSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildServerCounterSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildLeaderboardSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildConfessionsSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildPrefixes).values(guild_id=guild_id, prefixes=["t!"])
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            stmt = insert(GuildLimits).values(id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
            await session.execute(stmt)

        if refresh:
            await self.refresh_guild_config_cache(guild_id)

        db_logger.info(f"Guild {guild_id} initialized.")
        return self.guild_configs.get(guild_id)

    async def fetch_guild_config(self, guild_id: int) -> GuildSettings | None:
        guild_settings = self.guild_configs.get(guild_id)

        if not guild_settings:
            await self.refresh_guild_config_cache(guild_id)
            guild_settings = self.guild_configs.get(guild_id)

        return guild_settings

    async def setup_hook(self):
        await init_db()
        await self.refresh_all_caches()

        init_logger.info("Getting custom emojis...")
        try:
            info_emoji = os.getenv("INFO_EMOJI")
            if info_emoji and info_emoji.strip() != "":
                self.info_emoji = await self.fetch_application_emoji(int(info_emoji))
            else:
                self.info_emoji = "ℹ️"

            success_emoji = os.getenv("SUCCESS_EMOJI")
            if success_emoji and success_emoji.strip() != "":
                self.success_emoji = await self.fetch_application_emoji(int(success_emoji))
            else:
                self.success_emoji = "✅"

            error_emoji = os.getenv("ERROR_EMOJI")
            if error_emoji and error_emoji.strip() != "":
                self.error_emoji = await self.fetch_application_emoji(int(error_emoji))
            else:
                self.error_emoji = "❌"

            loading_emoji = os.getenv("LOADING_EMOJI")
            if loading_emoji and loading_emoji.strip() != "":
                self.loading_emoji = await self.fetch_application_emoji(int(loading_emoji))
            else:
                self.loading_emoji = "⏳"

            warn_emoji = os.getenv("WARN_EMOJI")
            if warn_emoji and warn_emoji.strip() != "":
                self.warn_emoji = await self.fetch_application_emoji(int(warn_emoji))
            else:
                self.warn_emoji = "⚠️"

            explicit_emoji = os.getenv("EXPLICIT_EMOJI")
            if explicit_emoji and explicit_emoji.strip() != "":
                self.explicit_emoji = await self.fetch_application_emoji(int(explicit_emoji))
            else:
                self.explicit_emoji = "🇪"
        except discord.HTTPException as e:
            init_logger.error("Failed to fetch emojis", exc_info=e)
            raise
        init_logger.info("Custom emojis loaded.")

        init_logger.info("Loading cogs...")
        # Find all cogs in command dir
        for filename in glob(os.path.join("cogs", "**"), recursive=True, include_hidden=False):
            if not os.path.isdir(filename):
                # Determine if file is a python file
                if filename.endswith(".py") and not filename.startswith("."):
                    filename = filename.replace("\\", "/").replace("/", ".")[:-3]

                    init_logger.debug(f"Loading normal cog: {filename}...")

                    try:
                        await bot.load_extension(filename)
                        init_logger.debug(f"Loaded normal cog: {filename}")
                    except Exception as e:
                        init_logger.error(f"Failed to load normal cog: {filename}", exc_info=e)

                        continue
        init_logger.info("Loading cogs complete.")

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
    intents=intents,
    command_prefix=get_prefix,
    strip_after_prefix=True,
    case_insensitive=True,
    max_messages=2500,
    help_command=None,
)


@bot.event
async def on_ready():
    init_logger.info(f"Bot is ready and connected as {bot.user}.")


@bot.event
async def on_command_error(ctx: commands.Context["TitaniumBot"], error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound) or isinstance(error, commands.NotOwner):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Not Found",
            description=f"The command `{ctx.invoked_with}` does not exist.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction and ctx.bot.loading_emoji in [
            r.emoji for r in ctx.message.reactions
        ]:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    elif isinstance(error, commands.errors.MissingPermissions):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Missing Permissions",
            description=error,
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction and ctx.bot.loading_emoji in [
            r.emoji for r in ctx.message.reactions
        ]:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    elif isinstance(error, commands.errors.NoPrivateMessage):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Server Only Command",
            description="This command can only be used in servers.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction and ctx.bot.loading_emoji in [
            r.emoji for r in ctx.message.reactions
        ]:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    elif isinstance(error, commands.errors.BadArgument):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Bad Argument",
            description=str(error).replace(str(error)[0], str(error)[0].upper(), 1),
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction and ctx.bot.loading_emoji in [
            r.emoji for r in ctx.message.reactions
        ]:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Argument Missing",
            description=f"You are missing the `{error.param.name}` argument.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction and ctx.bot.loading_emoji in [
            r.emoji for r in ctx.message.reactions
        ]:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    elif isinstance(error, commands.errors.MissingRequiredAttachment):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Attachment Missing",
            description=f"You are missing a required attachment (`{error.param.name}`) for this command.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)

        if not ctx.interaction and ctx.bot.loading_emoji in [
            r.emoji for r in ctx.message.reactions
        ]:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    elif isinstance(error, SlashCommandOnly):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Slash Command Only",
            description="This command is only available as a slash command. Please use the slash command version instead.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)
    else:
        try:
            error_id = await log_error(
                module="Commands",
                guild_id=ctx.guild.id if ctx.guild else None,
                error=f"Unexpected error in prefix command /{ctx.command.qualified_name if ctx.command else 'unknown'}.",
                exc=error,
            )
        except Exception as log_exc:
            error_id = "Unknown"
            logging.error("Failed to log error to database", exc_info=log_exc)
            logging.exception(error)

        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Error",
            description="An error occurred while executing the command. Please try again later.",
            colour=discord.Colour.red(),
        )

        embed.add_field(
            name="Error ID",
            value=f"`{error_id}`",
            inline=False,
        )

        await ctx.reply(embed=embed)

        if not ctx.interaction and ctx.bot.loading_emoji in [
            r.emoji for r in ctx.message.reactions
        ]:
            await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
):
    if not isinstance(error, discord.app_commands.CommandNotFound):
        try:
            error_id = await log_error(
                module="Commands",
                guild_id=interaction.guild.id if interaction.guild else None,
                error=f"Unexpected error in interaction /{interaction.command.qualified_name if interaction.command else 'unknown'}.",
                exc=error,
            )
        except Exception as log_exc:
            error_id = "Unknown"
            logging.error("Failed to log error to database", exc_info=log_exc)
            logging.exception(error)

        embed = discord.Embed(
            title=f"{bot.error_emoji} Interaction Error",
            description="An error occurred while processing the interaction. Please try again later.",
            colour=discord.Colour.red(),
        )

        embed.add_field(
            name="Error ID",
            value=f"`{error_id}`",
            inline=False,
        )

        await interaction.edit_original_response(embed=embed, view=None)


if __name__ == "__main__":
    if "--migrate" in sys.argv:
        asyncio.run(init_db())
        sys.exit(0)

    if "--v1tov2" in sys.argv:
        asyncio.run(migrate_v1_to_v2(bot, init_db))
        sys.exit(0)

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
        logging.error("An error occurred while starting the bot", exc_info=e)
