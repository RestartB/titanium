import asyncio
import logging
import os
import uuid
from typing import TYPE_CHECKING

from aiohttp import web
from discord.ext import commands
from pydantic import ValidationError
from sqlalchemy import delete

from lib.api.endpoints import (
    automod_info,
    confession_info,
    fireboard_info,
    logging_info,
    moderation_info,
    server_counters_info,
)
from lib.api.validators import (
    AutomodConfigModel,
    AutomodRuleModel,
    ConfessionConfigModel,
    FireboardConfigModel,
    GuildSettingsModel,
    LoggingConfigModel,
    ModerationConfigModel,
    ServerCountersConfigModel,
)
from lib.helpers.resolve_counter import resolve_counter
from lib.sql.sql import (
    AutomodAction,
    AutomodRule,
    FireboardBoard,
    GuildAutomodSettings,
    GuildConfessionSettings,
    GuildFireboardSettings,
    GuildLoggingSettings,
    GuildModerationSettings,
    GuildServerCounterSettings,
    GuildSettings,
    ServerCounterChannel,
    get_session,
)

if TYPE_CHECKING:
    from main import TitaniumBot


class APICog(commands.Cog):
    """API server for dashboard, website and status page"""

    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot: "TitaniumBot" = bot
        self.app = None
        self.runner = None
        self.site = None

        self.logger: logging.Logger = logging.getLogger("api")

        # Get host and port from env with defaults
        self.host = os.getenv("BOT_API_HOST", "127.0.0.1")
        self.port = int(os.getenv("BOT_API_PORT", 5000))

        self.logger.info(f"Starting API server on {self.host}:{self.port}")
        self.server_task = asyncio.create_task(self.start_server())

    async def start_server(self):
        try:
            self.app = web.Application()
            self.register_routes()

            self.runner = web.AppRunner(self.app, access_log=None)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()

            self.logger.info(
                f"API server started successfully on {self.host}:{self.port}"
            )
        except Exception as e:
            self.logger.error(f"Failed to start API server: {e}")
            exit(1)

    def register_routes(self):
        if self.app is None:
            return

        self.app.router.add_get("/", self.index)
        self.app.router.add_get("/info", self.info)
        self.app.router.add_get("/ping", self.ping)
        self.app.router.add_get("/status", self.status)
        self.app.router.add_get("/stats", self.stats)
        self.app.router.add_get("/user/{user_id}/guilds", self.mutual_guilds)
        self.app.router.add_get("/guild/{guild_id}/info", self.guild_info)
        self.app.router.add_get("/guild/{guild_id}/perms/{user_id}", self.perm_check)
        self.app.router.add_get("/guild/{guild_id}/settings", self.guild_settings)
        self.app.router.add_put(
            "/guild/{guild_id}/settings", self.update_guild_settings
        )
        self.app.router.add_get(
            "/guild/{guild_id}/module/{module_name}", self.module_get
        )
        self.app.router.add_put(
            "/guild/{guild_id}/module/{module_name}", self.module_update
        )

    async def index(self, request: web.Request) -> web.Response:
        return web.json_response({"version": "Titanium API v2"})

    async def ping(self, request: web.Request) -> web.Response:
        return web.json_response({"ping": "pong"})

    async def info(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "username": self.bot.user.name if self.bot.user else None,
                "discriminator": self.bot.user.discriminator if self.bot.user else None,
                "pfp": self.bot.user.display_avatar.url if self.bot.user else None,
            }
        )

    async def status(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "ready": self.bot.is_ready(),
                "connected": getattr(self.bot, "connected", False),
                "latency": round(self.bot.latency * 1000, 2),
                "initial_connect": (
                    self.bot.connect_time.timestamp() if self.bot.connect_time else None
                ),
                "last_disconnect": (
                    self.bot.last_disconnect.timestamp()
                    if self.bot.last_disconnect
                    else None
                ),
                "last_resume": (
                    self.bot.last_resume.timestamp() if self.bot.last_resume else None
                ),
            }
        )

    async def stats(self, request: web.Request) -> web.Response:
        await self.bot.wait_until_ready()

        return web.json_response(
            {
                "server_count": self.bot.guild_installs,
                "server_member_count": self.bot.guild_member_count,
                "user_count": self.bot.user_installs,
            }
        )

    async def mutual_guilds(self, request: web.Request) -> web.Response:
        user_id = request.match_info.get("user_id")
        if not user_id or not user_id.isdigit():
            return web.json_response({"error": "user_id required"}, status=400)

        try:
            user = await self.bot.fetch_user(int(user_id))
        except Exception:
            return web.json_response({"error": "user not found"}, status=404)

        mutual_guilds = [str(guild.id) for guild in user.mutual_guilds]
        return web.json_response(mutual_guilds)

    async def guild_info(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        return web.json_response(
            {
                "id": str(guild.id),
                "name": guild.name,
                "icon": guild.icon.url if guild.icon else None,
                "banner": guild.banner.url if guild.banner else None,
                "member_count": guild.member_count,
                "roles": [
                    {
                        "id": str(role.id),
                        "name": role.name,
                        "color": "#%02x%02x%02x" % role.colour.to_rgb(),
                        "hoist": role.hoist,
                        "position": role.position,
                    }
                    for role in reversed(guild.roles)
                    if role.id != guild.id
                ],
                "categories": [
                    {
                        "id": str(category.id) if category else None,
                        "name": category.name if category else None,
                        "position": i,
                        "channels": [
                            {
                                "id": str(channel.id),
                                "name": channel.name,
                                "type": str(channel.type),
                                "position": x,
                                "category": (
                                    str(channel.category_id)
                                    if channel.category_id
                                    else None
                                ),
                            }
                            for x, channel in enumerate(channels)
                        ],
                    }
                    for i, (category, channels) in enumerate(guild.by_category())
                ],
                "emojis": [
                    {
                        "id": str(emoji.id),
                        "label": emoji.name,
                        "url": emoji.url,
                    }
                    for emoji in guild.emojis
                ],
            }
        )

    async def perm_check(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        user_id = request.match_info.get("user_id")
        if not user_id or not user_id.isdigit():
            return web.json_response({"error": "user_id required"}, status=400)

        member = guild.get_member(int(user_id))
        if not member:
            return web.json_response(
                {
                    "dashboard_manager": False,
                    "case_manager": False,
                }
            )

        return web.json_response(
            {
                "dashboard_manager": member.guild_permissions.administrator,
                "case_manager": member.guild_permissions.manage_guild,
            }
        )

    async def guild_settings(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = self.bot.guild_configs.get(guild.id)
        prefixes = self.bot.guild_prefixes.get(guild.id)

        if not config or not prefixes:
            await self.bot.refresh_guild_config_cache(guild.id)
            config = self.bot.guild_configs.get(guild.id)
            prefixes = self.bot.guild_prefixes.get(guild.id)

            if not config or not prefixes:
                config = await self.bot.init_guild(guild.id)
                prefixes = self.bot.guild_prefixes.get(guild.id)

                if not config or not prefixes:
                    return web.json_response(
                        {"error": "Failed to retrieve server configuration"},
                        status=500,
                    )

        return web.json_response(
            {
                "modules": {
                    "moderation": config.moderation_enabled,
                    "automod": config.automod_enabled,
                    "logging": config.logging_enabled,
                    "fireboard": config.fireboard_enabled,
                    "server_counters": config.server_counters_enabled,
                    "confession": config.confession_enabled,
                },
                "settings": {
                    "loading_reaction": config.loading_reaction,
                },
                "prefixes": prefixes.prefixes,
            }
        )

    async def update_guild_settings(self, request: web.Request) -> web.Response:
        await self.bot.wait_until_ready()

        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = self.bot.guild_configs.get(guild.id)
        prefixes = self.bot.guild_prefixes.get(guild.id)

        if not config or not prefixes:
            await self.bot.refresh_guild_config_cache(guild.id)
            config = self.bot.guild_configs.get(guild.id)
            prefixes = self.bot.guild_prefixes.get(guild.id)

            if not config or not prefixes:
                config = await self.bot.init_guild(guild.id)
                prefixes = self.bot.guild_prefixes.get(guild.id)

                if not config or not prefixes:
                    return web.json_response(
                        {"error": "Failed to retrieve server configuration"},
                        status=500,
                    )

        try:
            data = await request.json()
            validated_settings = GuildSettingsModel(**data)
        except ValidationError as e:
            return web.json_response(
                {"error": "Validation failed", "details": e.errors()}, status=400
            )
        except ValueError as e:
            return web.json_response(
                {"error": "Invalid data", "message": str(e)}, status=400
            )

        async with get_session() as session:
            db_config = await session.get(GuildSettings, guild.id)
            if not db_config:
                return web.json_response(
                    {"error": "Failed to retrieve server configuration from DB"},
                    status=500,
                )
            db_config.confession_enabled = validated_settings.modules.confession
            db_config.moderation_enabled = validated_settings.modules.moderation
            db_config.automod_enabled = validated_settings.modules.automod
            db_config.logging_enabled = validated_settings.modules.logging
            db_config.fireboard_enabled = validated_settings.modules.fireboard
            db_config.server_counters_enabled = (
                validated_settings.modules.server_counters
            )
            db_config.loading_reaction = validated_settings.settings.loading_reaction

            prefixes.prefixes = validated_settings.prefixes
            session.add(db_config)
            session.add(prefixes)

        await self.bot.refresh_guild_config_cache(guild.id)

        return web.Response(status=204)

    async def module_get(self, request: web.Request) -> web.Response:
        await self.bot.wait_until_ready()

        guild_id = request.match_info.get("guild_id")
        module_name = request.match_info.get("module_name")
        module_name = module_name.lower() if module_name else None

        if not guild_id or not guild_id.isdigit() or not module_name:
            return web.json_response(
                {"error": "guild_id and module_name required"}, status=400
            )

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "Guild not found"}, status=404)

        config = self.bot.guild_configs.get(guild.id)
        if not config:
            await self.bot.refresh_guild_config_cache(guild.id)
            config = self.bot.guild_configs.get(guild.id)

            if not config:
                config = await self.bot.init_guild(guild.id)

        if module_name == "confession":
            return confession_info(self.bot, request, guild)
        elif module_name == "moderation":
            return moderation_info(self.bot, request, guild)
        elif module_name == "automod":
            return automod_info(self.bot, request, guild)
        elif module_name == "logging":
            return logging_info(self.bot, request, guild)
        elif module_name == "fireboard":
            return fireboard_info(self.bot, request, guild)
        elif module_name == "server_counters":
            return server_counters_info(self.bot, request, guild)
        else:
            return web.json_response({"error": "Module not found"}, status=404)

    async def module_update(self, request: web.Request) -> web.Response:
        await self.bot.wait_until_ready()

        guild_id_str = request.match_info.get("guild_id")
        guild_id = (
            int(guild_id_str) if guild_id_str and guild_id_str.isdigit() else None
        )
        module_name = request.match_info.get("module_name")
        module_name = module_name.lower() if module_name else None

        if not guild_id or not module_name:
            return web.json_response(
                {"error": "guild_id and module_name required"}, status=400
            )

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "Guild not found"}, status=404)

        config = self.bot.guild_configs.get(guild.id)
        if not config:
            await self.bot.refresh_guild_config_cache(guild.id)
            config = self.bot.guild_configs.get(guild.id)

            if not config:
                config = await self.bot.init_guild(guild.id)

        if module_name == "confession":
            guild_config = self.bot.guild_configs[guild.id]
            try:
                data = await request.json()
                validated_config = ConfessionConfigModel(**data)
            except ValidationError as e:
                return web.json_response(
                    {"error": "Validation failed", "details": e.errors()}, status=400
                )
            except ValueError as e:
                return web.json_response(
                    {"error": "Invalid data", "message": str(e)}, status=400
                )
            if (
                guild_config.confession_enabled
                and not validated_config.confession_channel_id
            ):
                return web.json_response(
                    {
                        "error": "Invalid data",
                        "message": "confession_channel_id is required when the confesssion_enabled for the guild",
                    },
                    status=400,
                )
            async with get_session() as session:
                db_config = await session.get(GuildConfessionSettings, guild.id)
                if not db_config:
                    db_config = GuildConfessionSettings(guild_id=guild.id)

                if validated_config.confession_channel_id is not None:
                    db_config.confession_channel_id = int(
                        validated_config.confession_channel_id
                    )
                if validated_config.confession_log_channel_id is not None:
                    db_config.confession_log_channel_id = int(
                        validated_config.confession_log_channel_id
                    )

            await self.bot.refresh_guild_config_cache(guild.id)
            return web.Response(status=204)

        elif module_name == "moderation":
            try:
                data = await request.json()
                validated_config = ModerationConfigModel(**data)
            except ValidationError as e:
                return web.json_response(
                    {"error": "Validation failed", "details": e.errors()}, status=400
                )
            except ValueError as e:
                return web.json_response(
                    {"error": "Invalid data", "message": str(e)}, status=400
                )

            async with get_session() as session:
                db_config = await session.get(GuildModerationSettings, guild.id)
                if not db_config:
                    db_config = GuildModerationSettings(guild_id=guild.id)

                db_config.delete_confirmation = validated_config.delete_confirmation
                db_config.dm_users = validated_config.dm_users

                session.add(db_config)
                await session.commit()

            await self.bot.refresh_guild_config_cache(guild.id)
            return web.Response(status=204)
        elif module_name == "automod":
            try:
                data = await request.json()
                validated_config = AutomodConfigModel(**data)
            except ValidationError as e:
                return web.json_response(
                    {"error": "Validation failed", "details": e.errors()}, status=400
                )
            except ValueError as e:
                return web.json_response(
                    {"error": "Invalid data", "message": str(e)}, status=400
                )

            async with get_session() as session:
                automod_settings = await session.get(
                    GuildAutomodSettings, int(guild_id)
                )

                if not automod_settings:
                    return web.json_response(
                        {"error": "Failed to retrieve server configuration from DB"},
                        status=500,
                    )

                for detection_config in [
                    validated_config.badword_detection,
                    validated_config.spam_detection,
                    validated_config.malicious_link_detection,
                    validated_config.phishing_link_detection,
                ]:
                    detection_config: list[AutomodRuleModel]
                    for rule_model in detection_config:
                        in_use = True
                        while in_use:
                            if rule_model.id is None:
                                rule_model.id = str(uuid.uuid4())

                            existing_rule = await session.get(
                                AutomodRule, rule_model.id
                            )
                            if existing_rule and existing_rule.guild_id != guild_id:
                                rule_model.id = str(uuid.uuid4())
                            else:
                                in_use = False

                await session.execute(
                    delete(AutomodAction).where(AutomodAction.guild_id == guild_id)
                )
                await session.execute(
                    delete(AutomodRule).where(AutomodRule.guild_id == guild_id)
                )

                for detection_config in [
                    validated_config.badword_detection,
                    validated_config.spam_detection,
                    validated_config.malicious_link_detection,
                    validated_config.phishing_link_detection,
                ]:
                    for rule_model in detection_config:
                        automod_rule = rule_model.to_sqlalchemy(guild_id)
                        session.add(automod_rule)

            await self.bot.refresh_guild_config_cache(guild_id)
            config = self.bot.guild_configs.get(guild_id)

            if config is None:
                return web.json_response(
                    {"error": "Failed to retrieve server configuration from cache"},
                    status=500,
                )

            return web.Response(status=204)
        elif module_name == "logging":
            try:
                data = await request.json()
                validated_config = LoggingConfigModel(**data)
            except ValidationError as e:
                return web.json_response(
                    {"error": "Validation failed", "details": e.errors()}, status=400
                )
            except ValueError as e:
                return web.json_response(
                    {"error": "Invalid data", "message": str(e)}, status=400
                )

            async with get_session() as session:
                db_config = await session.get(GuildLoggingSettings, guild.id)
                if not db_config:
                    db_config = GuildLoggingSettings(guild_id=guild.id)

                for field_name in LoggingConfigModel.model_fields.keys():
                    if getattr(validated_config, field_name) is not None:
                        setattr(
                            db_config,
                            field_name,
                            int(getattr(validated_config, field_name)),
                        )

                session.add(db_config)
                await session.commit()

            await self.bot.refresh_guild_config_cache(guild.id)
            return web.Response(status=204)
        elif module_name == "fireboard":
            try:
                data = await request.json()
                validated_config = FireboardConfigModel(**data)
            except ValidationError as e:
                return web.json_response(
                    {"error": "Validation failed", "details": e.errors()}, status=400
                )
            except ValueError as e:
                return web.json_response(
                    {"error": "Invalid data", "message": str(e)}, status=400
                )

            async with get_session() as session:
                db_config = await session.get(GuildSettings, guild.id)
                if not db_config:
                    return web.json_response(
                        {"error": "Failed to retrieve server configuration from DB"},
                        status=500,
                    )

                # Get existing configs
                existing_configs = await session.get(GuildFireboardSettings, guild.id)

                if not existing_configs:
                    existing_configs = GuildFireboardSettings(guild_id=guild.id)

                existing_configs.global_ignored_channels = [
                    int(channel) for channel in validated_config.global_ignored_channels
                ]
                existing_configs.global_ignored_roles = [
                    int(role) for role in validated_config.global_ignored_roles
                ]

                session.add(existing_configs)

                await session.commit()
                await session.refresh(existing_configs)

                for new_board in validated_config.boards:
                    if new_board.id is None:
                        board = FireboardBoard(
                            guild_id=guild.id,
                            channel_id=int(new_board.channel_id),
                            reaction=new_board.reaction,
                            threshold=new_board.threshold,
                            ignore_bots=new_board.ignore_bots,
                            ignore_self_reactions=new_board.ignore_self_reactions,
                            ignored_roles=[
                                int(role_id) for role_id in new_board.ignored_roles
                            ],
                            ignored_channels=[
                                int(channel_id)
                                for channel_id in new_board.ignored_channels
                            ],
                        )
                        session.add(board)
                    else:
                        existing_board = await session.get(
                            FireboardBoard, int(new_board.id)
                        )

                        if existing_board and existing_board.guild_id == guild.id:
                            existing_board.channel_id = int(new_board.channel_id)
                            existing_board.reaction = new_board.reaction
                            existing_board.threshold = new_board.threshold
                            existing_board.ignore_bots = new_board.ignore_bots
                            existing_board.ignore_self_reactions = (
                                new_board.ignore_self_reactions
                            )
                            existing_board.ignored_roles = [
                                int(role_id) for role_id in new_board.ignored_roles
                            ]
                            existing_board.ignored_channels = [
                                int(channel_id)
                                for channel_id in new_board.ignored_channels
                            ]
                            session.add(existing_board)
                        else:
                            board = FireboardBoard(
                                guild_id=guild.id,
                                channel_id=int(new_board.channel_id),
                                reaction=new_board.reaction,
                                threshold=new_board.threshold,
                                ignore_bots=new_board.ignore_bots,
                                ignore_self_reactions=new_board.ignore_self_reactions,
                                ignored_roles=[
                                    int(role_id) for role_id in new_board.ignored_roles
                                ],
                                ignored_channels=[
                                    int(channel_id)
                                    for channel_id in new_board.ignored_channels
                                ],
                            )
                            session.add(board)

            await self.bot.refresh_guild_config_cache(guild.id)
            return web.Response(status=204)
        elif module_name == "server_counters":
            try:
                data = await request.json()
                validated_config = ServerCountersConfigModel(**data)
            except ValidationError as e:
                return web.json_response(
                    {"error": "Validation failed", "details": e.errors()}, status=400
                )
            except ValueError as e:
                return web.json_response(
                    {"error": "Invalid data", "message": str(e)}, status=400
                )

            async with get_session() as session:
                db_config = await session.get(GuildSettings, guild.id)
                if not db_config:
                    return web.json_response(
                        {"error": "Failed to retrieve server configuration from DB"},
                        status=500,
                    )

                # Get existing configs
                existing_config = await session.get(
                    GuildServerCounterSettings, guild.id
                )

                if not existing_config:
                    existing_config = GuildServerCounterSettings(guild_id=guild.id)
                    session.add(existing_config)

                    await session.commit()
                    await session.refresh(existing_config)

                for new_channel in validated_config.channels:
                    if new_channel.id is None:
                        new_name = resolve_counter(
                            guild, new_channel.type, new_channel.name
                        )

                        discord_channel = await guild.create_voice_channel(
                            name=new_name,
                            reason="Creating server counter channel",
                        )

                        channel = ServerCounterChannel(
                            id=discord_channel.id,
                            guild_id=guild.id,
                            name=new_channel.name,
                            count_type=new_channel.type,
                        )
                        session.add(channel)
                    else:
                        existing_channel = await session.get(
                            ServerCounterChannel, int(new_channel.id)
                        )

                        if existing_channel and existing_channel.guild_id == guild.id:
                            existing_channel.name = new_channel.name
                            existing_channel.count_type = new_channel.type
                            session.add(existing_channel)
                        else:
                            new_name = resolve_counter(
                                guild, new_channel.type, new_channel.name
                            )

                            discord_channel = await guild.create_voice_channel(
                                name=new_name,
                                reason="Creating server counter channel",
                            )

                            channel = ServerCounterChannel(
                                id=discord_channel.id,
                                guild_id=guild.id,
                                name=new_channel.name,
                                count_type=new_channel.type,
                            )
                            session.add(channel)

            await self.bot.refresh_guild_config_cache(guild.id)
            return web.Response(status=204)
        else:
            return web.json_response({"error": "Module not found"}, status=404)

    async def cog_unload(self):
        if self.server_task:
            self.server_task.cancel()

        if self.site:
            await self.site.stop()

        if self.runner:
            await self.runner.cleanup()


async def setup(bot: "TitaniumBot"):
    await bot.add_cog(APICog(bot))
