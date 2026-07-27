# Titanium v2
# Made by Restart, 2025-

# Copyright (C) 2026, RestartB
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License or the LICENCE file for more details.


# Imports
import asyncio
import datetime
import logging
import os
import sys
from glob import glob
from typing import Awaitable, Callable

import discord
from discord.ext import commands
from discord.utils import utcnow
from dotenv import load_dotenv
from rapidfuzz import fuzz, process, utils
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload
from topgg.client import DBLClient

import lib.helpers.hybrid as adapters
from lib.classes import img_tools
from lib.classes.automod_message import AutomodMessage
from lib.embeds.general import guild_only
from lib.helpers.hybrid import SlashCommandOnly
from lib.helpers.log_error import log_error
from lib.setup_logger import setup_logging
from v1_to_v2.migrate import migrate_v1_to_v2

# load the env variables
load_dotenv()

from lib.sql.sql import (  # noqa: E402
    AvailableWebhook,
    ErrorLog,
    FireboardMessage,
    GuildSettings,
    LeaderboardUserStats,
    ModCase,
    OptOutIDs,
    ScheduledTask,
    get_guild_settings_child_tables,
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

init_logger.info("Welcome to Titanium v2")
init_logger.info("https://github.com/restartb/titanium")


# titanium needs the message content intent and members intent to function
# without these the bot will not run
# if your bot is in over 100 servers, please get these approved in the discord dev portal first
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class TitaniumBot(commands.Bot):
    user_installs: int = 0
    guild_installs: int = 0
    guild_member_count: int = 0

    connected: bool = False
    connect_time: datetime.datetime
    last_disconnect: datetime.datetime | None
    last_resume: datetime.datetime | None
    api_latency: float = 0.0

    guild_configs: dict[int, GuildSettings] = {}
    available_webhooks: dict[int, list[AvailableWebhook]] = {}
    automod_messages: dict[int, dict[int, list[AutomodMessage]]] = {}
    fireboard_messages: dict[int, list[FireboardMessage]] = {}

    punishing: dict[int, list[int]] = {}

    malicious_links: list[str] = []
    phishing_links: list[str] = []
    nsfw_links: list[str] = []
    explicit_phrases: list[str] = []

    opt_out: list[int] = []

    trusted_servers: list[int] = []

    pre_not_found: (
        Callable[
            [
                commands.Context["TitaniumBot"],
                commands.CommandNotFound
                | commands.NotOwner
                | adapters.GroupCommandNotFoundException,
            ],
            Awaitable[bool],
        ]
        | None
    ) = None

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
        cache_logger.info("Refreshing all guild config caches...")

        async with get_session() as session:
            guild_ids = (await session.execute(select(GuildSettings.guild_id))).scalars().all()
            for guild_id in guild_ids:
                await self._ensure_guild_settings_child_tables(session, guild_id)

            # Settings
            stmt = select(GuildSettings).options(selectinload("*"))
            result = await session.execute(stmt)
            configs = result.scalars().all()
            self.guild_configs.clear()

            for config in configs:
                self.guild_configs[config.guild_id] = config

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
        cache_logger.debug(f"Refreshing guild config cache for guild {guild_id}...")

        async with get_session() as session:
            guild_exists = await session.scalar(
                select(GuildSettings.guild_id).where(GuildSettings.guild_id == guild_id)
            )
            if guild_exists:
                await self._ensure_guild_settings_child_tables(session, guild_id)

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

            # Available webhooks
            stmt = (
                select(AvailableWebhook)
                .where(AvailableWebhook.guild_id == guild_id)
                .options(selectinload("*"))
            )
            result = await session.execute(stmt)
            webhook_configs = result.scalars().all()

            self.available_webhooks.pop(guild_id, None)
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

            self.fireboard_messages.pop(guild_id, None)
            for message in fireboard_messages:
                self.fireboard_messages.setdefault(message.guild_id, []).append(message)

        cache_logger.debug(f"Guild config cache for guild {guild_id} refreshed.")

    def remove_cached_config(self, guild_id: int) -> None:
        self.guild_configs.pop(guild_id, None)
        self.available_webhooks.pop(guild_id, None)
        self.automod_messages.pop(guild_id, None)
        self.fireboard_messages.pop(guild_id, None)
        self.punishing.pop(guild_id, None)

    async def _ensure_guild_settings_child_tables(self, session, guild_id: int) -> None:
        for model, primary_key in get_guild_settings_child_tables():
            stmt = insert(model).values({primary_key: guild_id})
            stmt = stmt.on_conflict_do_nothing(index_elements=[primary_key])
            await session.execute(stmt)

    async def init_guild(self, guild_id: int, refresh: bool = True) -> GuildSettings | None:
        db_logger.debug(f"Initializing guild {guild_id}...")

        async with get_session() as session:
            stmt = insert(GuildSettings).values(guild_id=guild_id)
            stmt = stmt.on_conflict_do_nothing(index_elements=["guild_id"])
            await session.execute(stmt)

            await self._ensure_guild_settings_child_tables(session, guild_id)

        if refresh:
            await self.refresh_guild_config_cache(guild_id)

        db_logger.debug(f"Guild {guild_id} initialized.")
        return self.guild_configs.get(guild_id)

    async def fetch_guild_config(
        self, guild_id: int, create_config: bool = True
    ) -> GuildSettings | None:
        guild_settings = self.guild_configs.get(guild_id)

        if not guild_settings:
            await self.refresh_guild_config_cache(guild_id)
            guild_settings = self.guild_configs.get(guild_id)

        if not guild_settings and create_config:
            guild_settings = await self.init_guild(guild_id)

        return guild_settings

    async def delete_guild_config(self, guild_id: int) -> None:
        # delete db entries
        async with get_session() as session:
            stmt = delete(GuildSettings).where(GuildSettings.guild_id == guild_id)
            await session.execute(stmt)

            stmt = delete(ErrorLog).where(ErrorLog.guild_id == guild_id)
            await session.execute(stmt)

            stmt = delete(AvailableWebhook).where(AvailableWebhook.guild_id == guild_id)
            await session.execute(stmt)

            stmt = delete(LeaderboardUserStats).where(LeaderboardUserStats.guild_id == guild_id)
            await session.execute(stmt)

            stmt = delete(ModCase).where(ModCase.guild_id == guild_id)
            await session.execute(stmt)

            stmt = delete(ScheduledTask).where(ScheduledTask.guild_id == guild_id)
            await session.execute(stmt)

        # clear from in-memory caches
        self.remove_cached_config(guild_id)

    async def setup_hook(self):
        await init_db()
        await self.refresh_opt_out()
        await self.refresh_all_caches()

        self.trusted_servers = (
            [int(x) for x in os.getenv("TRUSTED_SERVERS", "").split(",")]
            if os.getenv("TRUSTED_SERVERS")
            else []
        )

        token = os.getenv("TOPGG_TOKEN")
        if token:
            self.topgg_client = DBLClient(bot=self, token=token, autopost=True)

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

            menu_emoji = os.getenv("MENU_EMOJI")
            if menu_emoji and menu_emoji.strip() != "":
                self.menu_emoji = await self.fetch_application_emoji(int(menu_emoji))
            else:
                self.menu_emoji = "⚙️"
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

    async def on_ready(self):
        init_logger.info(f"Bot is ready and connected as {bot.user}.")

    async def on_connect(self):
        self.connected = True

    async def on_resumed(self):
        self.connected = True
        self.last_resume = utcnow()

    async def on_disconnect(self):
        if self.connected:
            self.connected = False
            self.last_disconnect = utcnow()

    async def on_error(self, event: str, *args, **kwargs):
        exc = sys.exc_info()[1]
        if not isinstance(exc, Exception):
            exc = None

        try:
            await log_error(
                bot=self,
                module=event,
                guild_id=None,
                error="Uncaught Error",
                store_err=False,
                exc=exc,
            )
        except Exception:
            if exc:
                logging.exception(exc)
            else:
                logging.error(f"Unexpected error in {event}")

    async def on_autopost_error(self, exception: Exception) -> None:
        await log_error(
            bot=self,
            module="top.gg Autopost",
            guild_id=None,
            error="Error",
            store_err=False,
            exc=exception,
        )


async def get_prefix(bot: TitaniumBot, message: discord.Message):
    if message.guild:
        config = await bot.fetch_guild_config(message.guild.id)

        if config:
            base = config.prefixes
        else:
            base = ["t!"]
    else:
        base = ["t!"]

    return commands.when_mentioned_or(*base)(bot, message)


bot = TitaniumBot(
    intents=intents,
    command_prefix=get_prefix,
    strip_after_prefix=True,
    case_insensitive=True,
    max_messages=2500,
    help_command=None,
    chunk_guilds_at_startup=False,
)


@bot.check
async def check(ctx: commands.Context["TitaniumBot"]):
    if ctx.interaction or not ctx.guild:
        return True

    config = await ctx.bot.fetch_guild_config(ctx.guild.id)

    if not config:
        return True

    if not config.allow_prefix:
        if not config.send_not_allowed:
            return False

        embed = discord.Embed(
            title=f"{ctx.bot.error_emoji} Not Allowed",
            description="Prefix commands have been disabled in this server.",
            colour=discord.Colour.red(),
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        await ctx.reply(embed=embed)
        return False

    if ctx.channel.id in config.blocked_channels:
        if not config.send_not_allowed:
            return False

        embed = discord.Embed(
            title=f"{ctx.bot.error_emoji} Not Allowed",
            description="You are not allowed to run prefix commands in this channel.",
            colour=discord.Colour.red(),
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        await ctx.reply(embed=embed)
        return False

    if isinstance(ctx.author, discord.Member) and any(
        role.id in config.blocked_roles for role in ctx.author.roles
    ):
        if not config.send_not_allowed:
            return False

        embed = discord.Embed(
            title=f"{ctx.bot.error_emoji} Not Allowed",
            description="You have a role which blocks you from running prefix commands in this server.",
            colour=discord.Colour.red(),
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        await ctx.reply(embed=embed)
        return False

    return True


@bot.event
async def on_command_error(ctx: commands.Context["TitaniumBot"], error: commands.CommandError):
    original_error = getattr(error, "original", error)

    if isinstance(original_error, (img_tools.ImageTooSmallError, img_tools.OperationTooLargeError)):
        description = (
            "The provided image is too small for this operation."
            if isinstance(original_error, img_tools.ImageTooSmallError)
            else "The resulting image would be too large to process. Please ensure that the result image is below 10000x10000px."
        )
        embed = discord.Embed(
            title=f"{bot.error_emoji} Error",
            description=description,
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed)
    elif (
        isinstance(error, commands.CommandNotFound)
        or isinstance(error, commands.NotOwner)
        or isinstance(error, adapters.GroupCommandNotFoundException)
    ):
        if ctx.bot.pre_not_found:
            if await ctx.bot.pre_not_found(ctx, error):
                return

        if isinstance(error, adapters.GroupCommandNotFoundException):
            command_name = error.command_name
        else:
            command_name = ctx.invoked_with or "unknown"

        embed = discord.Embed(
            title=f"{bot.error_emoji} Command Not Found",
            description=f"The command `{command_name}` does not exist.",
            colour=discord.Colour.red(),
        )

        command_list = [
            command.qualified_name
            for command in ctx.bot.walk_commands()
            if not command.hidden
            and not (
                isinstance(command, commands.Group)
                and not isinstance(command, commands.HybridGroup)
            )
            and not (isinstance(command, commands.HybridGroup) and not command.fallback)
        ]

        did_you_mean = await asyncio.to_thread(
            process.extract,
            command_name,
            command_list,
            scorer=fuzz.WRatio,
            limit=3,
            score_cutoff=65,
            processor=utils.default_process,
        )

        if did_you_mean:
            embed.add_field(
                name="Did you mean:", value=", ".join([f"`{value[0]}`" for value in did_you_mean])
            )

        await ctx.reply(embed=embed)
    elif isinstance(error, commands.errors.CommandOnCooldown):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Cooldown",
            description=error,
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)
    elif isinstance(error, commands.errors.MissingPermissions):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Missing Permissions",
            description=error,
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)
    elif isinstance(error, commands.errors.BotMissingPermissions):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Bot Missing Permissions",
            description=error,
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)
    elif isinstance(error, commands.errors.NoPrivateMessage):
        await ctx.reply(embed=guild_only(bot), ephemeral=True)
    elif isinstance(error, commands.HybridCommandError) and isinstance(
        error.original, discord.app_commands.TransformerError
    ):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Bad Argument",
            description=str(error.original).replace(
                str(error.original)[0], str(error.original)[0].upper(), 1
            ),
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)
    elif isinstance(error, (commands.errors.BadArgument, commands.errors.ArgumentParsingError)):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Bad Argument",
            description=str(error).replace(str(error)[0], str(error)[0].upper(), 1),
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)
    elif isinstance(error, commands.errors.BadLiteralArgument):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Bad Argument",
            description=f"Couldn't find your input for the `{error.param.name}` argument in `{'`, `'.join([str(lit) for lit in error.literals])}`.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Argument Missing",
            description=f"You are missing the `{error.param.name}` argument.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)
    elif isinstance(error, commands.errors.MissingRequiredAttachment):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Attachment Missing",
            description=f"You are missing a required attachment (`{error.param.name}`) for this command.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)
    elif isinstance(error, SlashCommandOnly):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Slash Command Only",
            description="This command is only available as a slash command.",
            colour=discord.Colour.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)
    elif isinstance(error, commands.errors.CheckFailure):
        return
    else:
        try:
            error_id = await log_error(
                bot=ctx.bot,
                module="Commands",
                guild_id=ctx.guild.id if ctx.guild else None,
                user=ctx.author,
                error=f"Unexpected error in prefix command {ctx.clean_prefix}{ctx.command.qualified_name if ctx.command else 'unknown'}.",
                dev_info=f"Full command: `{ctx.message.content}`",
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

        await ctx.reply(embed=embed, ephemeral=True)

    # stop loading reaction
    await adapters._stop_loading(ctx)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction["TitaniumBot"], error: discord.app_commands.AppCommandError
):
    original_error = getattr(error, "original", error)

    if isinstance(original_error, (img_tools.ImageTooSmallError, img_tools.OperationTooLargeError)):
        description = (
            "The provided image is too small for this operation."
            if isinstance(original_error, img_tools.ImageTooSmallError)
            else "The resulting image would be too large to process. Please ensure that the result image is below 10000x10000px."
        )
        embed = discord.Embed(
            title=f"{bot.error_emoji} Error",
            description=description,
            colour=discord.Colour.red(),
        )
        await interaction.edit_original_response(embed=embed)
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Cooldown",
            description=error,
            colour=discord.Colour.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, discord.app_commands.MissingPermissions):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Missing Permissions",
            description=error,
            colour=discord.Colour.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, discord.app_commands.BotMissingPermissions):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Bot Missing Permissions",
            description=error,
            colour=discord.Colour.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, discord.app_commands.TransformerError):
        embed = discord.Embed(
            title=f"{bot.error_emoji} Bad Argument",
            description=str(error),
            colour=discord.Colour.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, discord.app_commands.CheckFailure):
        return
    elif not isinstance(error, discord.app_commands.CommandNotFound):
        params = []
        if interaction.command and not isinstance(
            interaction.command, discord.app_commands.ContextMenu
        ):
            try:
                for param in interaction.command.parameters:
                    if param.name not in interaction.namespace:
                        continue
                    params.append(f"{param.name}: {interaction.namespace[param.name]}")
            except Exception:
                pass

        try:
            error_id = await log_error(
                bot=interaction.client,
                module="Commands",
                guild_id=interaction.guild.id if interaction.guild else None,
                user=interaction.user,
                error=f"Unexpected error in interaction /{interaction.command.qualified_name if interaction.command else 'unknown'}.",
                dev_info=f"Full command: `/{interaction.command.qualified_name if interaction.command else 'unknown'} {' '.join(params)}`",
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

        try:
            await interaction.edit_original_response(embed=embed, view=None)
        except discord.NotFound:
            await interaction.response.send_message(embed=embed, ephemeral=True)


if __name__ == "__main__":
    if "--migrate" in sys.argv:
        init_logger.info("Starting Titanium in migration mode...")
        asyncio.run(init_db())
        sys.exit(0)

    try:
        token = os.getenv("BOT_TOKEN")

        if token is None:
            raise discord.LoginFailure("No bot token provided in .env file.")

        if "--v1tov2" in sys.argv:
            init_logger.info("Starting Titanium in v1 to v2 mode...")

            async def migration_hook():
                await init_db()

                async def run_migration():
                    await bot.wait_until_ready()
                    await migrate_v1_to_v2(bot)

                bot.loop.create_task(run_migration())

            bot.setup_hook = migration_hook
            bot.run(token, log_handler=None)
            sys.exit(0)

        init_logger.info("Starting Titanium bot...")

        bot.connect_time = utcnow()
        bot.last_disconnect = None
        bot.last_resume = None

        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        init_logger.critical("Invalid bot token provided. Please check your .env file.")
    except Exception as e:
        init_logger.critical("An error occurred while starting the bot", exc_info=e)
