import asyncio
import logging
import os
import uuid
from typing import TYPE_CHECKING

import discord
from aiohttp import web
from discord.ext import commands
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from lib.api.endpoints import (
    automod_info,
    bouncer_info,
    confessions_info,
    fireboard_info,
    leaderboard_info,
    logging_info,
    moderation_info,
    server_counters_info,
)
from lib.api.validators import (
    AutomodConfigModel,
    AutomodRuleModel,
    BouncerConfigModel,
    ConfessionsConfigModel,
    FireboardConfigModel,
    GuildPermissionsModel,
    GuildSettingsModel,
    LeaderboardConfigModel,
    LoggingConfigModel,
    ModerationConfigModel,
    ServerCountersConfigModel,
)
from lib.helpers.resolve_counter import resolve_counter
from lib.sql.sql import (
    AutomodAction,
    AutomodRule,
    BouncerRule,
    ErrorLog,
    FireboardBoard,
    GuildAutomodSettings,
    GuildBouncerSettings,
    GuildConfessionsSettings,
    GuildFireboardSettings,
    GuildLeaderboardSettings,
    GuildLoggingSettings,
    GuildModerationSettings,
    GuildServerCounterSettings,
    GuildSettings,
    LeaderboardLevels,
    LeaderboardUserStats,
    ModCase,
    ServerCounterChannel,
    get_session,
)

if TYPE_CHECKING:
    from main import TitaniumBot

from lib.helpers.log_error import log_error


class APICog(commands.Cog):
    """API server for dashboard, website and status page"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot
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

            self.logger.info(f"API server started successfully on {self.host}:{self.port}")
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
        self.app.router.add_get("/guild/{guild_id}/cases", self.guild_cases)
        self.app.router.add_get("/guild/{guild_id}/errors", self.guild_errors)
        self.app.router.add_get("/guild/{guild_id}/leaderboard", self.guild_leaderboard)

        self.app.router.add_get("/guild/{guild_id}/perms", self.guild_perms)
        self.app.router.add_put("/guild/{guild_id}/perms", self.set_guild_perms)
        self.app.router.add_get("/guild/{guild_id}/perms/{user_id}", self.guild_perm_check)

        self.app.router.add_get("/guild/{guild_id}/settings", self.guild_settings)
        self.app.router.add_put("/guild/{guild_id}/settings", self.update_guild_settings)
        self.app.router.add_get("/guild/{guild_id}/module/{module_name}", self.module_get)
        self.app.router.add_put("/guild/{guild_id}/module/{module_name}", self.module_update)

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
                    self.bot.last_disconnect.timestamp() if self.bot.last_disconnect else None
                ),
                "last_resume": (self.bot.last_resume.timestamp() if self.bot.last_resume else None),
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

        guild_limits = self.bot.guild_limits.get(guild.id)
        if not guild_limits:
            await self.bot.refresh_guild_config_cache(guild.id)
            guild_limits = self.bot.guild_limits.get(guild.id)

        if not guild_limits:
            await self.bot.init_guild(guild.id)
            guild_limits = self.bot.guild_limits.get(guild.id)

        if not guild_limits:
            return web.json_response(
                {"error": "Failed to retrieve server limits"},
                status=500,
            )

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
                                    str(channel.category_id) if channel.category_id else None
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
                "limits": {
                    "enforcing": True,
                    "automod_rules": guild_limits.automod_rules,
                    "bad_word_list_size": guild_limits.bad_word_list_size,
                    "bouncer_rules": guild_limits.bouncer_rules,
                    "fireboards": guild_limits.fireboards,
                    "server_counters": guild_limits.server_counters,
                },
            }
        )

    async def guild_cases(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        limit = max(min(int(request.query.get("limit", 50)), 100), 1)
        offset = max(int(request.query.get("offset", 0)), 0)

        async with get_session() as session:
            # Get total count
            total_result = await session.execute(
                select(func.count()).select_from(ModCase).where(ModCase.guild_id == guild.id)
            )
            total_count = total_result.scalar() or 0

            if offset >= total_count:
                return web.json_response(
                    {
                        "total_count": total_count,
                        "cases": [],
                    }
                )

            # Get cases from DB
            result = await session.execute(
                select(ModCase)
                .where(ModCase.guild_id == guild.id)
                .order_by(ModCase.time_created.desc())
                .limit(limit)
                .offset(offset)
                .options(selectinload(ModCase.comments))
            )
            cases = result.scalars().all()

        # Get user objects to send user info
        cached_users: dict[int, discord.User | discord.Member | None] = {}
        for case in cases:
            for user_id in [case.user_id, case.creator_user_id]:
                if user_id not in cached_users:
                    member = guild.get_member(user_id)
                    if member:
                        cached_users[user_id] = member
                    else:
                        try:
                            user = await self.bot.fetch_user(user_id)
                            cached_users[user_id] = user
                        except Exception:
                            cached_users[user_id] = None

                for comment in case.comments:
                    if comment.user_id not in cached_users:
                        member = guild.get_member(comment.user_id)
                        if member:
                            cached_users[comment.user_id] = member
                        else:
                            try:
                                user = await self.bot.fetch_user(comment.user_id)
                                cached_users[comment.user_id] = user
                            except Exception:
                                cached_users[comment.user_id] = None

        cases_output = []
        for case in cases:
            user = cached_users.get(case.user_id)
            creator = cached_users.get(case.creator_user_id)

            comments_list = []
            for comment in case.comments:
                cuser = cached_users.get(comment.user_id)
                comments_list.append(
                    {
                        "id": str(comment.id),
                        "creator_id": str(comment.user_id),
                        "creator_name": cuser.name if cuser else None,
                        "creator_display": cuser.display_name if cuser else None,
                        "creator_pfp": cuser.display_avatar.url if cuser else None,
                        "content": comment.comment,
                        "time_created": comment.time_created.isoformat(),
                    }
                )

            cases_output.append(
                {
                    "id": case.id,
                    "type": case.type.value,
                    "user_id": str(case.user_id),
                    "user_name": user.name if user else None,
                    "user_display": user.display_name if user else None,
                    "user_pfp": user.display_avatar.url if user else None,
                    "creator_id": str(case.creator_user_id),
                    "creator_name": creator.name if creator else None,
                    "creator_display": creator.display_name if creator else None,
                    "creator_pfp": creator.display_avatar.url if creator else None,
                    "description": case.description,
                    "external": case.external,
                    "resolved": case.resolved,
                    "comments": comments_list,
                    "time_created": case.time_created.isoformat(),
                    "time_expires": case.time_expires.isoformat() if case.time_expires else None,
                    "time_updated": case.time_updated.isoformat() if case.time_updated else None,
                }
            )

        return web.json_response(
            {
                "total_count": total_count,
                "cases": cases_output,
            }
        )

    async def guild_errors(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        limit = max(min(int(request.query.get("limit", 50)), 100), 1)
        offset = max(int(request.query.get("offset", 0)), 0)

        async with get_session() as session:
            # Get total count
            total_result = await session.execute(
                select(func.count()).select_from(ErrorLog).where(ErrorLog.guild_id == guild.id)
            )
            total_count = total_result.scalar() or 0

            if offset >= total_count:
                return web.json_response(
                    {
                        "total_count": total_count,
                        "errors": [],
                    }
                )

            # Get errors from DB
            result = await session.execute(
                select(ErrorLog)
                .where(ErrorLog.guild_id == guild.id)
                .order_by(ErrorLog.time_occurred.desc())
                .limit(limit)
                .offset(offset)
            )
            errors = result.scalars().all()

        return web.json_response(
            {
                "total_count": total_count,
                "errors": [
                    {
                        "id": str(error.id),
                        "module": error.module,
                        "error": error.error,
                        "details": error.details,
                        "time_occurred": error.time_occurred.isoformat(),
                    }
                    for error in errors
                ],
            }
        )

    async def guild_leaderboard(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        # Get permissions
        config = await self.bot.fetch_guild_config(guild.id)

        if not config:
            config = await self.bot.init_guild(guild.id)

        if not config:
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        lb_config = config.leaderboard_settings

        if not lb_config or not config.leaderboard_enabled:
            return web.json_response({"error": "leaderboard module not enabled"}, status=403)

        limit = max(min(int(request.query.get("limit", 25)), 100), 1)
        offset = max(int(request.query.get("offset", 0)), 0)

        async with get_session() as session:
            result = await session.execute(
                select(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == guild.id)
                .order_by(LeaderboardUserStats.xp.desc())
                .limit(limit)
                .offset(offset)
            )
            leaderboard = result.scalars().all()

        return web.json_response(
            {
                "leaderboard": [
                    {
                        "user_id": str(user_stat.user_id),
                        "xp": str(user_stat.xp),
                        "level": user_stat.level,
                        "historical": user_stat.daily_snapshots,
                    }
                    for user_stat in leaderboard
                ],
            }
        )

    async def guild_perms(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)

        if not config:
            config = await self.bot.init_guild(guild.id)

        if not config:
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        return web.json_response(
            {
                "dashboard_managers": [str(role_id) for role_id in config.dashboard_managers],
                "case_managers": [str(role_id) for role_id in config.case_managers],
            }
        )

    async def set_guild_perms(self, request: web.Request) -> web.Response:
        await self.bot.wait_until_ready()

        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)

        if not config:
            config = await self.bot.init_guild(guild.id)

        if not config:
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        try:
            data = await request.json()
            validated_perms = GuildPermissionsModel(**data)
        except ValidationError as e:
            return web.json_response(
                {"error": "Validation failed", "details": e.errors()}, status=400
            )
        except ValueError as e:
            return web.json_response({"error": "Invalid data", "message": str(e)}, status=400)

        async with get_session() as session:
            db_config = await session.get(GuildSettings, guild.id)
            if not db_config:
                return web.json_response(
                    {"error": "Failed to retrieve server configuration from DB"},
                    status=500,
                )

            db_config.dashboard_managers = [
                int(role_id) for role_id in validated_perms.dashboard_managers
            ]
            db_config.case_managers = [int(role_id) for role_id in validated_perms.case_managers]

        await self.bot.refresh_guild_config_cache(guild.id)
        return web.Response(status=204)

    async def guild_perm_check(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        user_id = request.match_info.get("user_id")
        if not user_id or not user_id.isdigit():
            return web.json_response({"error": "user_id required"}, status=400)

        member: discord.Member | None = guild.get_member(int(user_id))
        if not member:
            return web.json_response(
                {
                    "dashboard_manager": False,
                    "case_manager": False,
                    "member": False,
                }
            )

        # Get permissions
        config = await self.bot.fetch_guild_config(guild.id)

        if not config:
            config = await self.bot.init_guild(guild.id)

        if not config:
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        dashboard_manager = member.guild_permissions.administrator
        case_manager = member.guild_permissions.manage_guild

        for role in member.roles:
            if role.id == guild.id:
                continue

            if role.id in config.dashboard_managers:
                dashboard_manager = True

            if role.id in config.case_managers:
                case_manager = True

        return web.json_response(
            {
                "dashboard_manager": dashboard_manager,
                "case_manager": case_manager,
                "member": True,
            }
        )

    async def guild_settings(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)
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
                    "bouncer": config.bouncer_enabled,
                    "logging": config.logging_enabled,
                    "fireboard": config.fireboard_enabled,
                    "server_counters": config.server_counters_enabled,
                    "confessions": config.confessions_enabled,
                    "leaderboard": config.leaderboard_enabled,
                },
                "settings": {
                    "loading_reaction": config.loading_reaction,
                },
                "prefixes": prefixes.prefixes,
                "permissions": {
                    "dashboard_managers": [str(role_id) for role_id in config.dashboard_managers],
                    "case_managers": [str(role_id) for role_id in config.case_managers],
                },
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

        config = await self.bot.fetch_guild_config(guild.id)
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
            return web.json_response({"error": "Invalid data", "message": str(e)}, status=400)

        async with get_session() as session:
            db_config = await session.get(GuildSettings, guild.id)
            if not db_config:
                return web.json_response(
                    {"error": "Failed to retrieve server configuration from DB"},
                    status=500,
                )

            db_config.confessions_enabled = validated_settings.modules.confessions
            db_config.moderation_enabled = validated_settings.modules.moderation
            db_config.automod_enabled = validated_settings.modules.automod
            db_config.bouncer_enabled = validated_settings.modules.bouncer
            db_config.logging_enabled = validated_settings.modules.logging
            db_config.fireboard_enabled = validated_settings.modules.fireboard
            db_config.server_counters_enabled = validated_settings.modules.server_counters
            db_config.leaderboard_enabled = validated_settings.modules.leaderboard

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
            return web.json_response({"error": "guild_id and module_name required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "Guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)

        if not config:
            config = await self.bot.init_guild(guild.id)

        if not config:
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        if module_name == "confessions":
            return confessions_info(self.bot, request, guild)
        elif module_name == "moderation":
            return moderation_info(self.bot, request, guild)
        elif module_name == "automod":
            return automod_info(self.bot, request, guild)
        elif module_name == "bouncer":
            return bouncer_info(self.bot, request, guild)
        elif module_name == "logging":
            return logging_info(self.bot, request, guild)
        elif module_name == "fireboard":
            return fireboard_info(self.bot, request, guild)
        elif module_name == "server_counters":
            return server_counters_info(self.bot, request, guild)
        elif module_name == "leaderboard":
            return leaderboard_info(self.bot, request, guild)
        else:
            return web.json_response({"error": "Module not found"}, status=404)

    async def module_update(self, request: web.Request) -> web.Response:
        await self.bot.wait_until_ready()

        guild_id_str = request.match_info.get("guild_id")
        guild_id = int(guild_id_str) if guild_id_str and guild_id_str.isdigit() else None
        module_name = request.match_info.get("module_name")
        module_name = module_name.lower() if module_name else None

        if not guild_id or not module_name:
            return web.json_response({"error": "guild_id and module_name required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "Guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)

        if not config:
            config = await self.bot.init_guild(guild.id)

        if not config:
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        try:
            data = await request.json()

            if module_name == "confessions":
                validated_config = ConfessionsConfigModel(**data)
            elif module_name == "moderation":
                validated_config = ModerationConfigModel(**data)
            elif module_name == "automod":
                validated_config = AutomodConfigModel(**data)
            elif module_name == "bouncer":
                validated_config = BouncerConfigModel(**data)
            elif module_name == "logging":
                validated_config = LoggingConfigModel(**data)
            elif module_name == "fireboard":
                validated_config = FireboardConfigModel(**data)
            elif module_name == "server_counters":
                validated_config = ServerCountersConfigModel(**data)
            elif module_name == "leaderboard":
                validated_config = LeaderboardConfigModel(**data)
        except ValidationError as e:
            error_details = []
            for error in e.errors():
                error_dict = {
                    "type": error["type"],
                    "loc": error["loc"],
                    "msg": error["msg"],
                    "input": str(error.get("input", "")),
                }
                if "ctx" in error:
                    error_dict["ctx"] = {k: str(v) for k, v in error["ctx"].items()}
                error_details.append(error_dict)

            return web.json_response(
                {"error": "Validation failed", "details": error_details}, status=400
            )
        except ValueError as e:
            return web.json_response({"error": "Invalid data", "message": str(e)}, status=400)

        if module_name == "confessions" and isinstance(validated_config, ConfessionsConfigModel):
            async with get_session() as session:
                db_config = await session.get(GuildConfessionsSettings, guild.id)
                if not db_config:
                    db_config = GuildConfessionsSettings(guild_id=guild.id)

                db_config.confessions_in_channel = validated_config.confessions_in_channel
                db_config.confessions_channel_id = (
                    int(validated_config.confessions_channel_id)
                    if validated_config.confessions_channel_id
                    else None
                )

                session.add(db_config)
        elif module_name == "moderation" and isinstance(validated_config, ModerationConfigModel):
            async with get_session() as session:
                db_config = await session.get(GuildModerationSettings, guild.id)
                if not db_config:
                    db_config = GuildModerationSettings(guild_id=guild.id)

                db_config.delete_confirmation = validated_config.delete_confirmation
                db_config.dm_users = validated_config.dm_users

                session.add(db_config)
        elif module_name == "automod" and isinstance(validated_config, AutomodConfigModel):
            async with get_session() as session:
                automod_settings = await session.get(GuildAutomodSettings, int(guild_id))

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

                            existing_rule = await session.get(AutomodRule, rule_model.id)
                            if existing_rule and existing_rule.guild_id != guild_id:
                                rule_model.id = str(uuid.uuid4())
                            else:
                                in_use = False

                await session.execute(
                    delete(AutomodAction).where(AutomodAction.guild_id == guild_id)
                )
                await session.execute(delete(AutomodRule).where(AutomodRule.guild_id == guild_id))

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
        elif module_name == "bouncer" and isinstance(validated_config, BouncerConfigModel):
            async with get_session() as session:
                db_config = await session.get(GuildBouncerSettings, guild.id)
                if not db_config:
                    db_config = GuildBouncerSettings(guild_id=guild.id)

                await session.execute(delete(BouncerRule).where(BouncerRule.guild_id == guild_id))

                for rule in validated_config.rules:
                    bouncer_rule = rule.to_sqlalchemy(guild_id)
                    session.add(bouncer_rule)

                session.add(db_config)
        elif module_name == "logging" and isinstance(validated_config, LoggingConfigModel):
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
        elif module_name == "fireboard" and isinstance(validated_config, FireboardConfigModel):
            async with get_session() as session:
                db_config = await session.get(GuildSettings, guild.id)
                if not db_config:
                    return web.json_response(
                        {"error": "Failed to retrieve server configuration from DB"},
                        status=500,
                    )

                # Get existing configs
                result = await session.execute(
                    select(GuildFireboardSettings)
                    .where(GuildFireboardSettings.guild_id == guild.id)
                    .options(selectinload(GuildFireboardSettings.fireboard_boards))
                )
                existing_configs = result.scalar_one_or_none()

                if not existing_configs:
                    existing_configs = GuildFireboardSettings(guild_id=guild.id)

                existing_configs.global_ignored_channels = [
                    int(channel) for channel in validated_config.global_ignored_channels
                ]
                existing_configs.global_ignored_roles = [
                    int(role) for role in validated_config.global_ignored_roles
                ]

                # Update existing boards and remove deleted ones
                for existing_board in existing_configs.fireboard_boards:
                    # Check if board was removed
                    if existing_board.id not in [
                        new_board.id for new_board in validated_config.boards
                    ]:
                        await session.delete(existing_board)
                        continue

                    # Update existing board
                    for new_board in validated_config.boards:
                        if new_board.id != existing_board.id:
                            continue

                        existing_board.channel_id = int(new_board.channel_id)
                        existing_board.reaction = new_board.reaction
                        existing_board.threshold = new_board.threshold
                        existing_board.ignore_bots = new_board.ignore_bots
                        existing_board.ignore_self_reactions = new_board.ignore_self_reactions
                        existing_board.ignored_roles = [
                            int(role_id) for role_id in new_board.ignored_roles
                        ]
                        existing_board.ignored_channels = [
                            int(channel_id) for channel_id in new_board.ignored_channels
                        ]

                # New boards
                for new_board in validated_config.boards:
                    channel = guild.get_channel(int(new_board.channel_id))

                    if not channel:
                        raise web.HTTPBadRequest(reason="Invalid channel ID for fireboard board")

                    # Check if board has already been handled
                    if new_board.id is not None and any(
                        existing_board.id == new_board.id
                        for existing_board in existing_configs.fireboard_boards
                    ):
                        continue

                    board = FireboardBoard(
                        guild_id=guild.id,
                        channel_id=int(new_board.channel_id),
                        reaction=new_board.reaction,
                        threshold=new_board.threshold,
                        ignore_bots=new_board.ignore_bots,
                        ignore_self_reactions=new_board.ignore_self_reactions,
                        ignored_roles=[int(role_id) for role_id in new_board.ignored_roles],
                        ignored_channels=[
                            int(channel_id) for channel_id in new_board.ignored_channels
                        ],
                    )
                    session.add(board)
        elif module_name == "server_counters" and isinstance(
            validated_config, ServerCountersConfigModel
        ):
            async with get_session() as session:
                db_config = await session.get(GuildSettings, guild.id)
                if not db_config:
                    return web.json_response(
                        {"error": "Failed to retrieve server configuration from DB"},
                        status=500,
                    )

                # Get existing configs
                result = await session.execute(
                    select(GuildServerCounterSettings)
                    .where(GuildServerCounterSettings.guild_id == guild.id)
                    .options(selectinload(GuildServerCounterSettings.channels))
                )
                existing_config = result.scalar_one_or_none()

                if not existing_config:
                    existing_config = GuildServerCounterSettings(guild_id=guild.id)

                channel_ids = []

                for new_channel in validated_config.channels:
                    if new_channel.id is not None:
                        channel_ids.append(int(new_channel.id))

                    if new_channel.id is None:
                        new_name = resolve_counter(
                            guild, new_channel.type, new_channel.name, new_channel.activity_name
                        )

                        discord_channel = await guild.create_voice_channel(
                            name=new_name,
                            reason="Creating server counter channel",
                        )
                        channel_ids.append(discord_channel.id)

                        channel = ServerCounterChannel(
                            id=discord_channel.id,
                            guild_id=guild.id,
                            name=new_channel.name,
                            count_type=new_channel.type,
                            activity_name=new_channel.activity_name,
                        )
                        session.add(channel)
                    else:
                        existing_channel = await session.get(
                            ServerCounterChannel, int(new_channel.id)
                        )

                        if existing_channel and existing_channel.guild_id == guild.id:
                            existing_channel.name = new_channel.name
                            existing_channel.count_type = new_channel.type
                            existing_channel.activity_name = new_channel.activity_name  # pyright: ignore[reportAttributeAccessIssue]

                            session.add(existing_channel)
                        else:
                            new_name = resolve_counter(
                                guild, new_channel.type, new_channel.name, new_channel.activity_name
                            )

                            try:
                                discord_channel = await guild.create_voice_channel(
                                    name=new_name,
                                    reason="Creating server counter channel",
                                )
                                channel_ids.append(discord_channel.id)
                            except discord.Forbidden:
                                await log_error(
                                    bot=self.bot,
                                    module="Server Counters",
                                    guild_id=guild.id,
                                    error="Missing permissions to create server counter channel",
                                )
                                continue
                            except discord.HTTPException as e:
                                await log_error(
                                    bot=self.bot,
                                    module="Server Counters",
                                    guild_id=guild.id,
                                    error="Unexpected Discord error when creating server counter channel",
                                    exc=e,
                                )
                                continue
                            except Exception as e:
                                await log_error(
                                    bot=self.bot,
                                    module="Server Counters",
                                    guild_id=guild.id,
                                    error="Unexpected error when creating server counter channel",
                                    exc=e,
                                )
                                continue

                            channel = ServerCounterChannel(
                                id=discord_channel.id,
                                guild_id=guild.id,
                                name=new_channel.name,
                                count_type=new_channel.type,
                                activity_name=new_channel.activity_name,
                            )
                            session.add(channel)

                await session.commit()
                await session.refresh(existing_config, ["channels"])

                # Delete removed channels
                for existing_channel in existing_config.channels:
                    if existing_channel.id not in channel_ids:
                        discord_channel = guild.get_channel(existing_channel.id)

                        if discord_channel:
                            try:
                                await discord_channel.delete(
                                    reason="Removing server counter channel"
                                )
                            except discord.Forbidden:
                                await log_error(
                                    bot=self.bot,
                                    module="Server Counters",
                                    guild_id=guild.id,
                                    error=f"Missing permissions to delete channel #{discord_channel.name} ({discord_channel.id})",
                                )
                            except discord.HTTPException as e:
                                await log_error(
                                    bot=self.bot,
                                    module="Server Counters",
                                    guild_id=guild.id,
                                    error=f"Unexpected Discord error when deleting channel #{discord_channel.name} ({discord_channel.id})",
                                    exc=e,
                                )
                            except Exception as e:
                                await log_error(
                                    bot=self.bot,
                                    module="Server Counters",
                                    guild_id=guild.id,
                                    error=f"Unexpected error when deleting channel #{discord_channel.name} ({discord_channel.id})",
                                    exc=e,
                                )

                        await session.delete(existing_channel)
        elif module_name == "leaderboard" and isinstance(validated_config, LeaderboardConfigModel):
            async with get_session() as session:
                db_config = await session.get(GuildSettings, guild.id)
                if not db_config:
                    return web.json_response(
                        {"error": "Failed to retrieve server configuration from DB"},
                        status=500,
                    )

                # Get existing configs
                result = await session.execute(
                    select(GuildLeaderboardSettings)
                    .where(GuildLeaderboardSettings.guild_id == guild.id)
                    .options(selectinload(GuildLeaderboardSettings.levels))
                )
                existing_config = result.scalar_one_or_none()

                if not existing_config:
                    existing_config = GuildLeaderboardSettings(guild_id=guild.id)

                existing_config.mode = validated_config.mode
                existing_config.base_xp = validated_config.base_xp
                existing_config.min_xp = validated_config.min_xp
                existing_config.max_xp = validated_config.max_xp
                existing_config.xp_mult = validated_config.xp_mult
                existing_config.cooldown = validated_config.cooldown
                existing_config.levelup_notifications = validated_config.levelup_notifications
                existing_config.notification_channel = (
                    int(validated_config.notification_channel)
                    if validated_config.notification_channel
                    else None
                )
                existing_config.web_leaderboard_enabled = validated_config.web_leaderboard_enabled
                existing_config.web_login_required = validated_config.web_login_required
                existing_config.delete_leavers = validated_config.delete_leavers
                existing_config.levels = [
                    LeaderboardLevels(
                        xp=level.xp_required,
                        reward_roles=level.reward_roles,
                    )
                    for level in validated_config.levels
                ]

                session.add(existing_config)
        else:
            return web.json_response({"error": "Module not found"}, status=404)

        await self.bot.refresh_guild_config_cache(guild.id)
        return web.Response(status=204)

    async def cog_unload(self):
        if self.server_task:
            self.server_task.cancel()

        if self.site:
            await self.site.stop()

        if self.runner:
            await self.runner.cleanup()


async def setup(bot: TitaniumBot):
    await bot.add_cog(APICog(bot))
