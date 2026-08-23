import asyncio
import logging
import os
import uuid
from typing import TYPE_CHECKING

import discord
from aiohttp import web
from discord.ext import commands
from prometheus_client.aiohttp import make_aiohttp_handler
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from lib.api.endpoints import (
    automod_info,
    bouncer_info,
    confessions_info,
    fireboard_info,
    leaderboard_info,
    logging_info,
    moderation_info,
    rep_info,
    server_counters_info,
    tags_info,
)
from lib.api.validators import (
    AutomodConfigModel,
    BouncerConfigModel,
    CaseComment,
    ConfessionsConfigModel,
    FireboardConfigModel,
    GuildPermissionsModel,
    GuildSettingsModel,
    LeaderboardConfigModel,
    LoggingConfigModel,
    ModerationConfigModel,
    RepConfigModel,
    ServerCountersConfigModel,
    TagModel,
    TagsConfigModel,
)
from lib.classes.case_manager import CaseNotFoundException, GuildModCaseManager
from lib.classes.guild_logger import LOGGING_EVENT_MAP, LOGGING_EVENTS
from lib.enums.moderation import CaseType
from lib.enums.server_counters import ServerCounterType
from lib.helpers.cache import get_or_fetch_member
from lib.helpers.log_error import log_error
from lib.helpers.resolve_counter import resolve_counter
from lib.sql.sql import (
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
    GuildRepSettings,
    GuildServerCounterSettings,
    GuildSettings,
    GuildTagSettings,
    LeaderboardLevels,
    LeaderboardUserStats,
    ModCase,
    ModCaseComment,
    ServerCounterChannel,
    Tag,
    UserRep,
    get_session,
)

if TYPE_CHECKING:
    from main import TitaniumBot


class APICog(commands.Cog):
    """API server for dashboard, website and status page"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot
        self.app = None
        self.runner = None
        self.site = None

        self.logger: logging.Logger = logging.getLogger("api")

        self.perm_cache: dict[tuple[int, int], tuple[float, dict]] = {}
        self.perm_locks: dict[tuple[int, int], asyncio.Lock] = {}
        self.PERM_CACHE_TTL = 60

        # Get host and port from env with defaults
        self.host = os.getenv("BOT_API_HOST", "127.0.0.1")
        self.port = int(os.getenv("BOT_API_PORT", "5000"))
        self.api_secret = os.getenv("BOT_API_TOKEN")

        if not self.api_secret:
            self.logger.warning(
                "No BOT_API_TOKEN has been provided, this is not a secure configuration!"
            )

    async def cog_load(self) -> None:
        self.logger.info(f"Starting API server on {self.host}:{self.port}")
        self.server_task = asyncio.create_task(self.start_server())

    def __format_validation_error(self, e: ValidationError) -> dict:
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

        return {"error": "Validation failed", "details": error_details}

    @web.middleware
    async def auth_middleware(self, request: web.Request, handler) -> web.Response:
        # Allow public endpoints / no token set
        if request.path in ["/", "/info", "/ping", "/status", "/stats"] or not self.api_secret:
            return await handler(request)

        await self.bot.wait_until_ready()

        auth_header = request.headers.get("Authorization")
        if auth_header != f"Bearer {self.api_secret}":
            return web.json_response({"error": "Unauthorized"}, status=401)

        return await handler(request)

    async def start_server(self):
        try:
            self.app = web.Application(middlewares=[self.auth_middleware])
            self.register_routes()

            self.runner = web.AppRunner(self.app, access_log=None)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()

            self.logger.info(f"API server started successfully on {self.host}:{self.port}")
        except Exception as e:
            self.logger.error(f"Failed to start API server: {e}")

    def register_routes(self):
        if self.app is None:
            return

        self.app.router.add_get("/metrics", make_aiohttp_handler())

        self.app.router.add_get("/", self.index)
        self.app.router.add_get("/info", self.info)
        self.app.router.add_get("/ping", self.ping)
        self.app.router.add_get("/status", self.status)
        self.app.router.add_get("/stats", self.stats)

        self.app.router.add_get("/info/logging", self.logging_types)

        self.app.router.add_post("/user/{user_id}/guilds", self.mutual_guilds)
        self.app.router.add_get("/user/{user_id}/inguild/{guild_id}", self.in_guild)

        self.app.router.add_get("/guild/{guild_id}", self.guild_branding)
        self.app.router.add_get("/guild/{guild_id}/inguild", self.bot_in_guild)
        self.app.router.add_get("/guild/{guild_id}/info", self.guild_info)
        self.app.router.add_get("/guild/{guild_id}/errors", self.guild_errors)
        self.app.router.add_get("/guild/{guild_id}/leaderboard", self.guild_leaderboard)
        self.app.router.add_get("/guild/{guild_id}/rep", self.guild_rep_leaderboard)

        self.app.router.add_get("/guild/{guild_id}/cases", self.guild_cases)
        self.app.router.add_get("/guild/{guild_id}/cases/{case_id}", self.guild_case)
        self.app.router.add_get(
            "/guild/{guild_id}/cases/{case_id}/comments", self.guild_case_comments
        )
        self.app.router.add_post(
            "/guild/{guild_id}/cases/{case_id}/comments", self.guild_case_add_comment
        )
        self.app.router.add_patch(
            "/guild/{guild_id}/cases/{case_id}/comments/{comment_id}", self.guild_case_edit_comment
        )
        self.app.router.add_delete(
            "/guild/{guild_id}/cases/{case_id}/comments/{comment_id}",
            self.guild_case_delete_comment,
        )

        self.app.router.add_get("/guild/{guild_id}/tags", self.guild_tags)
        self.app.router.add_post("/guild/{guild_id}/tags", self.guild_create_tag)
        self.app.router.add_patch("/guild/{guild_id}/tags/{tag_id}", self.guild_edit_tag)
        self.app.router.add_delete("/guild/{guild_id}/tags/{tag_id}", self.guild_delete_tag)

        self.app.router.add_get("/guild/{guild_id}/perms", self.guild_perms)
        self.app.router.add_put("/guild/{guild_id}/perms", self.set_guild_perms)
        self.app.router.add_get("/guild/{guild_id}/perms/{user_id}", self.guild_perm_check)

        self.app.router.add_get("/guild/{guild_id}/settings", self.guild_settings)
        self.app.router.add_put("/guild/{guild_id}/settings", self.update_guild_settings)
        self.app.router.add_get("/guild/{guild_id}/module/{module_name}", self.module_get)
        self.app.router.add_put("/guild/{guild_id}/module/{module_name}", self.module_update)

    def __can_see_channel(self, member: discord.Member, channel: discord.abc.GuildChannel) -> bool:
        return channel.permissions_for(member).view_channel if member else False

    def __case_info_json(
        self,
        case: ModCase,
        user: discord.User | discord.Member | None,
        creator: discord.User | discord.Member | None,
        comments: list[ModCaseComment] | None = None,
    ) -> dict:
        data = {
            "id": case.id,
            "type": case.type.value,
            "user_id": str(case.user_id),
            "user_name": user.name if user else None,
            "user_discrim": user.discriminator if user and user.bot else None,
            "user_display": user.display_name if user else None,
            "user_pfp": user.display_avatar.url if user else None,
            "creator_id": str(case.creator_user_id),
            "creator_name": creator.name if creator else None,
            "creator_discrim": creator.discriminator if creator and creator.bot else None,
            "creator_display": creator.display_name if creator else None,
            "creator_pfp": creator.display_avatar.url if creator else None,
            "description": case.description,
            "external": case.external,
            "resolved": case.resolved,
            "time_created": case.time_created.isoformat(),
            "time_expires": case.time_expires.isoformat() if case.time_expires else None,
            "time_updated": case.time_updated.isoformat() if case.time_updated else None,
        }

        if comments is not None:
            data["comments"] = comments

        return data

    async def index(self, request: web.Request) -> web.Response:
        return web.json_response({"version": "Titanium API v2"})

    async def ping(self, request: web.Request) -> web.Response:
        return web.json_response({"ping": "pong"})

    async def info(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "username": self.bot.user.name if self.bot.user else "Titanium",
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
        if not self.bot.is_ready():
            return web.Response(status=503)

        return web.json_response(
            {
                "server_count": self.bot.guild_installs,
                "server_member_count": self.bot.guild_member_count,
                "user_count": self.bot.user_installs,
            }
        )

    async def logging_types(self, request: web.Request) -> web.Response:
        return web.json_response(
            [
                {
                    "event": event.event,
                    "name": event.name,
                    "description": event.description,
                    "category": event.category,
                }
                for event in LOGGING_EVENTS
            ]
        )

    async def mutual_guilds(self, request: web.Request) -> web.Response:
        user_id = request.match_info.get("user_id")
        if not user_id or not user_id.isdigit():
            return web.json_response({"error": "user_id required"}, status=400)

        try:
            body: dict = await request.json()
            guild_ids: list[str] = body.get("user_guilds", [])
        except Exception:
            return web.json_response({"error": "invalid payload"}, status=400)

        bot_guild_ids: set[int] = {guild.id for guild in self.bot.guilds}
        mutual_guild_ids: list[str] = [
            str(guild_id) for guild_id in bot_guild_ids if str(guild_id) in guild_ids
        ]
        delegate_guild_ids: list[str] = []

        for mutual_id in mutual_guild_ids:
            guild = self.bot.get_guild(int(mutual_id))
            if not guild:
                continue

            member = guild.get_member(int(user_id))
            if not member:
                continue

            config = await self.bot.fetch_guild_config(guild.id)
            if not config:
                raise RuntimeError("No guild config returned")

            delegate_roles = config.case_managers + config.dashboard_managers
            if any(role.id in delegate_roles for role in member.roles):
                delegate_guild_ids.append(mutual_id)

        return web.json_response({"mutual": mutual_guild_ids, "delegate": delegate_guild_ids})

    async def in_guild(self, request: web.Request) -> web.Response:
        user_id = request.match_info.get("user_id")
        guild_id = request.match_info.get("guild_id")

        if not user_id or not user_id.isdigit():
            return web.json_response({"error": "user_id required"}, status=400)

        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))

        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        if await get_or_fetch_member(self.bot, guild, int(user_id)):
            return web.json_response({"in_guild": True}, status=200)
        else:
            return web.json_response({"in_guild": False}, status=200)

    async def bot_in_guild(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id", "")

        if not self.bot.get_guild(int(guild_id)):
            return web.json_response({"in_guild": False}, status=200)

        return web.json_response({"in_guild": True}, status=200)

    async def guild_branding(self, request: web.Request) -> web.Response:
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
                "splash": guild.discovery_splash.url if guild.discovery_splash else None,
                "member_count": guild.member_count,
            }
        )

    async def guild_info(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        user_id = request.query.get("user", None)
        member = None
        if user_id:
            member = await get_or_fetch_member(self.bot, guild, int(user_id))
        if not member:
            return web.json_response({"error": "member not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)
        if not config:
            return web.json_response(
                {"error": "Failed to retrieve server limits"},
                status=500,
            )
        guild_limits = config.limits

        return web.json_response(
            {
                "roles": [
                    {
                        "id": str(role.id),
                        "name": role.name,
                        "colour": "#{:02x}{:02x}{:02x}".format(*role.colour.to_rgb()),
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
                            for x, channel in enumerate(
                                [
                                    channel
                                    for channel in channels
                                    if channel.permissions_for(member).view_channel
                                ]
                            )
                        ],
                    }
                    for i, (category, channels) in enumerate(
                        [
                            category
                            for category in guild.by_category()
                            if not category[0] or category[0].permissions_for(member).view_channel
                        ]
                    )
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
                    "enforcing": guild_limits.enforcing,
                    "automod_rules": guild_limits.automod_rules,
                    "bad_word_list_size": guild_limits.bad_word_list_size,
                    "bouncer_rules": guild_limits.bouncer_rules,
                    "fireboards": guild_limits.fireboards,
                    "leaderboard_levels": guild_limits.leaderboard_levels,
                    "server_counters": guild_limits.server_counters,
                    "tags": guild_limits.tags,
                },
                "bot_permissions": str(guild.me.guild_permissions.value),
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

            # no need to get errors if we know there will be none
            if offset >= total_count or total_count == 0:
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

    async def guild_cases(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        guild_config = await self.bot.fetch_guild_config(guild.id)
        if not guild_config or not guild_config.moderation_enabled:
            return web.json_response({"error": "moderation module is disabled"}, status=403)

        limit = max(min(int(request.query.get("limit", 50)), 100), 1)
        offset = max(int(request.query.get("offset", 0)), 0)

        async with get_session() as session:
            # Get total count
            total_result = await session.execute(
                select(func.count()).select_from(ModCase).where(ModCase.guild_id == guild.id)
            )
            total_count = total_result.scalar() or 0

            # no need to get cases if we know there will be none
            if offset >= total_count or total_count == 0:
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
            )
            cases = result.scalars().all()

        # Get user objects to send user info
        cached_users: dict[int, discord.User | discord.Member | None] = {}
        for case in cases:
            if case.creator_user_id not in cached_users:
                cached_users[case.creator_user_id] = await get_or_fetch_member(
                    self.bot, guild, case.creator_user_id
                )

            if case.type in [CaseType.KICK, CaseType.BAN]:
                case_user = guild.get_member(case.user_id)
                cached_users[case.user_id] = (
                    case_user if case_user else self.bot.get_user(case.user_id)
                )
            else:
                if case.user_id not in cached_users:
                    cached_users[case.user_id] = await get_or_fetch_member(
                        self.bot, guild, case.user_id
                    )

        cases_output = []
        for case in cases:
            user = cached_users.get(case.user_id)
            creator = cached_users.get(case.creator_user_id)

            cases_output.append(self.__case_info_json(case=case, user=user, creator=creator))

        return web.json_response(
            {
                "total_count": total_count,
                "cases": cases_output,
            }
        )

    async def guild_case(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        case_id = request.match_info.get("case_id")
        if not case_id:
            return web.json_response({"error": "case_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        guild_config = await self.bot.fetch_guild_config(guild.id)
        if not guild_config or not guild_config.moderation_enabled:
            return web.json_response({"error": "moderation module is disabled"}, status=403)

        async with get_session() as session:
            # Get case from db
            result = await session.execute(
                select(ModCase)
                .where(ModCase.guild_id == guild.id)
                .where(ModCase.id == case_id)
                .options(selectinload(ModCase.comments))
            )
            case = result.scalar_one()

        if not case:
            return web.json_response({"error": "case not found"}, status=404)

        # Get user objects to send user info
        cached_users: dict[int, discord.User | discord.Member | None] = {}
        cached_users[case.creator_user_id] = await get_or_fetch_member(
            self.bot, guild, case.creator_user_id
        )

        if case.type in [CaseType.KICK, CaseType.BAN]:
            case_user = guild.get_member(case.user_id)
            cached_users[case.user_id] = case_user if case_user else self.bot.get_user(case.user_id)
        else:
            if case.user_id not in cached_users:
                cached_users[case.user_id] = await get_or_fetch_member(
                    self.bot, guild, case.user_id
                )

        for comment in case.comments:
            if comment.user_id in cached_users:
                continue

            cached_users[comment.user_id] = await get_or_fetch_member(
                self.bot, guild, comment.user_id
            )

        user = cached_users.get(case.user_id)
        creator = cached_users.get(case.creator_user_id)

        # TODO: remove this, move to comments endpoint
        comments_list = []
        for comment in case.comments:
            cuser = cached_users.get(comment.user_id)
            comments_list.append(
                {
                    "id": str(comment.id),
                    "creator_id": str(comment.user_id),
                    "creator_name": cuser.name if cuser else None,
                    "creator_discrim": cuser.discriminator if cuser and cuser.bot else None,
                    "creator_display": cuser.display_name if cuser else None,
                    "creator_pfp": cuser.display_avatar.url if cuser else None,
                    "content": comment.comment,
                    "time_created": comment.time_created.isoformat(),
                }
            )

        return web.json_response(
            self.__case_info_json(case=case, user=user, creator=creator, comments=comments_list)
        )

    async def guild_case_comments(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        case_id = request.match_info.get("case_id")
        if not case_id:
            return web.json_response({"error": "case_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        guild_config = await self.bot.fetch_guild_config(guild.id)
        if not guild_config or not guild_config.moderation_enabled:
            return web.json_response({"error": "moderation module is disabled"}, status=403)

        limit = max(min(int(request.query.get("limit", 50)), 100), 1)
        offset = max(int(request.query.get("offset", 0)), 0)

        async with get_session() as session:
            # Get total count
            total_result = await session.execute(
                select(func.count())
                .select_from(ModCaseComment)
                .where(ModCaseComment.guild_id == guild.id, ModCaseComment.case_id == case_id)
            )
            total_count = total_result.scalar() or 0

            # no need to get comments if we know there will be none
            if offset >= total_count or total_count == 0:
                return web.json_response(
                    {
                        "total_count": total_count,
                        "comments": [],
                    }
                )

            # Get comments from db
            result = await session.execute(
                select(ModCaseComment)
                .where(ModCaseComment.guild_id == guild.id, ModCaseComment.case_id == case_id)
                .limit(limit)
                .offset(offset)
            )
            comments = result.scalars().all()

        if not comments:
            return web.json_response({"total_count": total_count, "comments": []}, status=200)

        # Get user objects to send user info
        cached_users: dict[int, discord.User | discord.Member | None] = {}
        for comment in comments:
            if comment.user_id in cached_users:
                continue

            cached_users[comment.user_id] = await get_or_fetch_member(
                self.bot, guild, comment.user_id
            )

        comments_list = []
        for comment in comments:
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

        return web.json_response({"total_count": total_count, "comments": comments_list})

    async def guild_case_add_comment(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        case_id = request.match_info.get("case_id")
        if not case_id:
            return web.json_response({"error": "case_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        guild_config = await self.bot.fetch_guild_config(guild.id)
        if not guild_config or not guild_config.moderation_enabled:
            return web.json_response({"error": "moderation module is disabled"}, status=403)

        try:
            data: dict = await request.json()
            validated_tag = CaseComment(**data)
        except ValidationError as e:
            return web.json_response(self.__format_validation_error(e), status=400)

        member = await get_or_fetch_member(
            bot=self.bot, guild=guild, user_id=int(validated_tag.user)
        )

        if not member:
            return web.json_response({"error": "creator not found"}, status=404)

        async with get_session() as session:
            manager = GuildModCaseManager(self.bot, guild, session)

            try:
                case = await manager.get_case_by_id(case_id)
            except CaseNotFoundException:
                return web.json_response({"error": "case not found"}, status=404)

            comment = await case.add_comment(
                member=member, content=validated_tag.content, bot=self.bot, guild=guild
            )

        return web.json_response({"id": str(comment.id)})

    async def guild_case_edit_comment(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        case_id = request.match_info.get("case_id")
        if not case_id:
            return web.json_response({"error": "case_id required"}, status=400)

        comment_id = request.match_info.get("comment_id")
        if not comment_id:
            return web.json_response({"error": "comment_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        guild_config = await self.bot.fetch_guild_config(guild.id)
        if not guild_config or not guild_config.moderation_enabled:
            return web.json_response({"error": "moderation module is disabled"}, status=403)

        try:
            data: dict = await request.json()
            validated_comment = CaseComment(**data)
        except ValidationError as e:
            return web.json_response(self.__format_validation_error(e), status=400)

        async with get_session(autocommit=False) as session:
            manager = GuildModCaseManager(self.bot, guild, session)

            try:
                case = await manager.get_case_by_id(case_id)
            except CaseNotFoundException:
                return web.json_response({"error": "case not found"}, status=404)

            comment = await case.get_user_comment(
                user=int(validated_comment.user), comment=uuid.UUID(comment_id)
            )
            if not comment:
                return web.json_response({"error": "comment not found"}, status=404)
            await comment.edit_comment(content=validated_comment.content)

        await self.bot.refresh_guild_config_cache(guild.id)
        return web.Response(status=204)

    async def guild_case_delete_comment(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        case_id = request.match_info.get("case_id")
        if not case_id:
            return web.json_response({"error": "case_id required"}, status=400)

        comment_id = request.match_info.get("comment_id")
        if not comment_id:
            return web.json_response({"error": "comment_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        guild_config = await self.bot.fetch_guild_config(guild.id)
        if not guild_config or not guild_config.moderation_enabled:
            return web.json_response({"error": "moderation module is disabled"}, status=403)

        async with get_session() as session:
            manager = GuildModCaseManager(self.bot, guild, session)

            try:
                case = await manager.get_case_by_id(case_id)
            except CaseNotFoundException:
                return web.json_response({"error": "case not found"}, status=404)

            body: dict = await request.json()
            comment = await case.get_user_comment(
                user=int(body["user"]), comment=uuid.UUID(comment_id)
            )

            if not comment:
                return web.json_response({"error": "comment not found"}, status=404)
            await comment.delete_comment()

        return web.Response(status=204)

    async def guild_tags(self, request: web.Request) -> web.Response:
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
                select(func.count())
                .select_from(Tag)
                .where(Tag.guild_id == guild.id, Tag.is_user.is_(False))
            )
            total_count = total_result.scalar() or 0

            # no need to get tags if we know there will be none
            if offset >= total_count or total_count == 0:
                return web.json_response(
                    {
                        "total_count": total_count,
                        "tags": [],
                    }
                )

            # Get tags from db
            result = await session.execute(
                select(Tag)
                .where(Tag.guild_id == guild.id, Tag.is_user.is_(False))
                .limit(limit)
                .offset(offset)
            )
            tags = result.scalars().all()

        if not tags:
            return web.json_response({"total_count": total_count, "tags": []}, status=200)

        # Get user objects to send user info
        cached_users: dict[int, discord.User | discord.Member | None] = {}
        for tag in tags:
            if tag.owner_id not in cached_users:
                cached_users[tag.owner_id] = await get_or_fetch_member(
                    self.bot, guild, tag.owner_id
                )

            if tag.modified_by and tag.modified_by not in cached_users:
                cached_users[tag.modified_by] = await get_or_fetch_member(
                    self.bot, guild, tag.modified_by
                )

        tags_list: list[dict] = []
        for tag in tags:
            cuser = cached_users.get(tag.owner_id)
            muser = cached_users.get(tag.modified_by) if tag.modified_by else None

            tags_list.append(
                {
                    "id": str(tag.id),
                    "name": tag.name,
                    "content": tag.content,
                    "creator_id": str(tag.owner_id),
                    "creator_name": cuser.name if cuser else None,
                    "creator_display": cuser.display_name if cuser else None,
                    "creator_pfp": cuser.display_avatar.url if cuser else None,
                    "modified_by_id": str(tag.modified_by) if tag.modified_by else None,
                    "modified_by_name": muser.name if muser else None,
                    "modified_by_display": muser.display_name if muser else None,
                    "modified_by_pfp": muser.display_avatar.url if muser else None,
                }
            )

        return web.json_response({"total_count": total_count, "tags": tags_list})

    async def guild_create_tag(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        try:
            data = await request.json()
            validated_tag = TagModel(**data)
        except ValidationError as e:
            return web.json_response(self.__format_validation_error(e), status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)
        if not config or not config.tag_settings:
            return web.json_response({"error": "failed to get guild config"}, status=500)

        if not config.tags_enabled:
            return web.json_response({"error": "tags are disabled in this server"}, status=403)

        if config.limits.enforcing and len(config.tag_settings.tags) >= config.limits.tags:
            return web.json_response(
                {
                    "error": "Limit exceeded",
                    "message": "You have gone over your limit for server tags.",
                },
                status=403,
            )

        member = await get_or_fetch_member(self.bot, guild, int(validated_tag.user))
        if not member:
            return web.json_response({"error": "user not found"}, status=404)

        async with get_session(autocommit=False) as session:
            new_tag = Tag(
                name=validated_tag.name,
                content=validated_tag.content,
                owner_id=member.id,
                guild_id=guild.id,
                is_user=False,
            )

            session.add(new_tag)

            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()

                err_code = getattr(e.orig, "sqlstate", getattr(e.orig, "pgcode", None))
                if err_code == "23505":  # 23505 = unique_violation
                    return web.json_response({"error": "tag_in_use"}, status=404)

                raise

        await self.bot.refresh_guild_config_cache(guild.id)
        return web.Response(status=204)

    async def guild_edit_tag(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        tag_id = request.match_info.get("tag_id")
        if not tag_id:
            return web.json_response({"error": "tag_id required"}, status=400)

        try:
            data = await request.json()
            validated_tag = TagModel(**data)
        except ValidationError as e:
            return web.json_response(self.__format_validation_error(e), status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)
        if not config:
            return web.json_response({"error": "failed to get guild config"}, status=500)

        if not config.tags_enabled:
            return web.json_response({"error": "tags are disabled in this server"}, status=403)

        member = await get_or_fetch_member(self.bot, guild, int(validated_tag.user))
        if not member:
            return web.json_response({"error": "user not found"}, status=404)

        async with get_session(autocommit=False) as session:
            to_edit = await session.get(Tag, tag_id)

            if not to_edit or to_edit.is_user or to_edit.guild_id != guild.id:
                return web.json_response({"error": "tag not found"}, status=404)

            to_edit.name = validated_tag.name
            to_edit.content = validated_tag.content
            to_edit.modified_by = member.id

            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()

                err_code = getattr(e.orig, "sqlstate", getattr(e.orig, "pgcode", None))
                if err_code == "23505":  # 23505 = unique_violation
                    return web.json_response({"error": "tag_in_use"}, status=404)
                raise

        await self.bot.refresh_guild_config_cache(guild.id)
        return web.Response(status=204)

    async def guild_delete_tag(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        tag_id = request.match_info.get("tag_id")
        if not tag_id:
            return web.json_response({"error": "tag_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)
        if not config:
            return web.json_response({"error": "failed to get guild config"}, status=500)

        if not config.tags_enabled:
            return web.json_response({"error": "tags are disabled in this server"}, status=403)

        async with get_session() as session:
            to_delete = await session.get(Tag, tag_id)

            if not to_delete or to_delete.is_user or to_delete.guild_id != guild.id:
                return web.json_response({"error": "tag not found"}, status=404)

            await session.execute(delete(Tag).where(Tag.id == to_delete.id))

        await self.bot.refresh_guild_config_cache(guild.id)
        return web.Response(status=204)

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
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        lb_config = config.leaderboard_settings

        if not lb_config or not config.leaderboard_enabled:
            return web.json_response({"error": "leaderboard module disabled"}, status=403)

        limit = max(min(int(request.query.get("limit", 25)), 100), 1)
        offset = max(int(request.query.get("offset", 0)), 0)

        async with get_session() as session:
            # Get total count
            total_result = await session.execute(
                select(func.count())
                .select_from(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == guild.id)
            )
            total_count = total_result.scalar() or 0

            # no need to get leaderboard entries if we know there will be none
            if offset >= total_count or total_count == 0:
                return web.json_response(
                    {
                        "total_count": total_count,
                        "leaderboard": [],
                    }
                )

            result = await session.execute(
                select(LeaderboardUserStats)
                .where(LeaderboardUserStats.guild_id == guild.id)
                .order_by(LeaderboardUserStats.xp.desc())
                .limit(limit)
                .offset(offset)
            )
            leaderboard = result.scalars().all()

        member_cache: dict[int, discord.Member | discord.User | None] = {}
        missing_ids: list[int] = []

        for entry in leaderboard:
            uid = entry.user_id
            user = guild.get_member(uid) or self.bot.get_user(uid)
            if user:
                member_cache[uid] = user
            else:
                missing_ids.append(uid)

        if missing_ids:
            queried = await guild.query_members(limit=100, user_ids=missing_ids)
            for member in queried:
                member_cache[member.id] = member

        return web.json_response(
            {
                "total_count": total_count,
                "leaderboard": [
                    {
                        "user_id": str(user_stat.user_id),
                        "user_name": mem.name
                        if (mem := member_cache.get(user_stat.user_id))
                        else None,
                        "user_display": mem.display_name
                        if (mem := member_cache.get(user_stat.user_id))
                        else None,
                        "user_pfp": mem.display_avatar.url
                        if (mem := member_cache.get(user_stat.user_id))
                        else None,
                        "xp": str(user_stat.xp),
                        "level": user_stat.level,
                        "historical": user_stat.daily_snapshots,
                    }
                    for user_stat in leaderboard
                    if user_stat.xp > 0
                ],
            }
        )

    async def guild_rep_leaderboard(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        # Get permissions
        config = await self.bot.fetch_guild_config(guild.id)
        if not config:
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        rep_config = config.rep_settings

        if not rep_config or not config.rep_enabled:
            return web.json_response({"error": "rep module disabled"}, status=403)

        limit = max(min(int(request.query.get("limit", 25)), 100), 1)
        offset = max(int(request.query.get("offset", 0)), 0)

        async with get_session() as session:
            # Get total count
            total_result = await session.execute(
                select(func.count()).select_from(UserRep).where(UserRep.guild_id == guild.id)
            )
            total_count = total_result.scalar() or 0

            # no need to get leaderboard entries if we know there will be none
            if offset >= total_count or total_count == 0:
                return web.json_response(
                    {
                        "total_count": total_count,
                        "leaderboard": [],
                    }
                )

            result = await session.execute(
                select(UserRep)
                .where(UserRep.guild_id == guild.id)
                .order_by(UserRep.rep.desc())
                .limit(limit)
                .offset(offset)
            )
            leaderboard = result.scalars().all()

        member_cache: dict[int, discord.Member | discord.User | None] = {}
        missing_ids: list[int] = []

        for entry in leaderboard:
            uid = entry.user_id
            user = guild.get_member(uid) or self.bot.get_user(uid)
            if user:
                member_cache[uid] = user
            else:
                missing_ids.append(uid)

        if missing_ids:
            queried = await guild.query_members(limit=100, user_ids=missing_ids)
            for member in queried:
                member_cache[member.id] = member

        return web.json_response(
            {
                "total_count": total_count,
                "leaderboard": [
                    {
                        "user_id": str(user_stat.user_id),
                        "user_name": mem.name
                        if (mem := member_cache.get(user_stat.user_id))
                        else None,
                        "user_display": mem.display_name
                        if (mem := member_cache.get(user_stat.user_id))
                        else None,
                        "user_pfp": mem.display_avatar.url
                        if (mem := member_cache.get(user_stat.user_id))
                        else None,
                        "rep": str(user_stat.rep),
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
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)
        if not config:
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        try:
            data = await request.json()
            validated_perms = GuildPermissionsModel(**data)
        except ValidationError as e:
            return web.json_response(self.__format_validation_error(e), status=400)
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

        cache_key = (guild.id, int(user_id))
        loop = asyncio.get_event_loop()
        current_time = loop.time()

        cached_data = self.perm_cache.get(cache_key)
        if cached_data is not None:
            expiry, cached_perms = cached_data
            if current_time < expiry:
                return web.json_response(cached_perms)

        if cache_key not in self.perm_locks:
            self.perm_locks[cache_key] = asyncio.Lock()

        async with self.perm_locks[cache_key]:
            cached_data = self.perm_cache.get(cache_key)
            if cached_data is not None and loop.time() < cached_data[0]:
                return web.json_response(cached_data[1])

            member: discord.Member | None = await get_or_fetch_member(self.bot, guild, int(user_id))
            if not member:
                resp = {
                    "dashboard_manager": False,
                    "case_manager": False,
                    "member": False,
                }
                self.perm_cache[cache_key] = (loop.time() + self.PERM_CACHE_TTL, resp)
                self.perm_locks.pop(cache_key, None)
                return web.json_response(resp)

            # Get permissions
            config = await self.bot.fetch_guild_config(guild.id)
            if not config:
                self.perm_locks.pop(cache_key, None)
                return web.json_response(
                    {"error": "Failed to retrieve server configuration"},
                    status=500,
                )

            dashboard_manager = member.guild_permissions.administrator
            case_manager = (
                member.guild_permissions.kick_members
                or member.guild_permissions.ban_members
                or member.guild_permissions.moderate_members
            )

            for role in member.roles:
                if role.id == guild.id:
                    continue

                if role.id in config.dashboard_managers:
                    dashboard_manager = True

                if role.id in config.case_managers:
                    case_manager = True

            resp = {
                "dashboard_manager": dashboard_manager,
                "case_manager": case_manager,
                "member": True,
            }
            self.perm_cache[cache_key] = (loop.time() + self.PERM_CACHE_TTL, resp)
            self.perm_locks.pop(cache_key, None)
            return web.json_response(resp)

    async def guild_settings(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)
        if not config:
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
                    "tags": config.tags_enabled,
                    "rep": config.rep_enabled,
                },
                "settings": {
                    "allow_prefix": config.allow_prefix,
                    "send_not_allowed": config.send_not_allowed,
                    "loading_reaction": config.loading_reaction,
                    "blocked_channels": [str(channel) for channel in config.blocked_channels],
                    "blocked_roles": [str(role) for role in config.blocked_roles],
                    "delete_after_3_days": config.delete_after_3_days,
                },
                "prefixes": config.prefixes,
                "permissions": {
                    "dashboard_managers": [str(role_id) for role_id in config.dashboard_managers],
                    "case_managers": [str(role_id) for role_id in config.case_managers],
                },
            }
        )

    async def update_guild_settings(self, request: web.Request) -> web.Response:
        guild_id = request.match_info.get("guild_id")
        if not guild_id or not guild_id.isdigit():
            return web.json_response({"error": "guild_id required"}, status=400)

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)

        config = await self.bot.fetch_guild_config(guild.id)
        if not config:
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        try:
            data = await request.json()
            validated_settings = GuildSettingsModel(**data)
        except ValidationError as e:
            return web.json_response(self.__format_validation_error(e), status=400)
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
            db_config.tags_enabled = validated_settings.modules.tags
            db_config.rep_enabled = validated_settings.modules.rep

            db_config.prefixes = validated_settings.prefixes
            db_config.allow_prefix = validated_settings.settings.allow_prefix
            db_config.send_not_allowed = validated_settings.settings.send_not_allowed
            db_config.loading_reaction = validated_settings.settings.loading_reaction
            db_config.blocked_channels = [
                int(channel) for channel in validated_settings.settings.blocked_channels
            ]
            db_config.blocked_roles = [
                int(role) for role in validated_settings.settings.blocked_roles
            ]

            db_config.delete_after_3_days = validated_settings.settings.delete_after_3_days

            session.add(db_config)

        await self.bot.refresh_guild_config_cache(guild.id)
        return web.Response(status=204)

    async def module_get(self, request: web.Request) -> web.Response:
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
        elif module_name == "tags":
            return tags_info(self.bot, request, guild)
        elif module_name == "rep":
            return rep_info(self.bot, request, guild)
        else:
            return web.json_response({"error": "Module not found"}, status=404)

    async def module_update(self, request: web.Request) -> web.Response:
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
            return web.json_response(
                {"error": "Failed to retrieve server configuration"},
                status=500,
            )

        user_id = request.query.get("user", None)
        member = None

        if user_id:
            member = await get_or_fetch_member(self.bot, guild, int(user_id))

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
            elif module_name == "tags":
                validated_config = TagsConfigModel(**data)
            elif module_name == "rep":
                validated_config = RepConfigModel(**data)
        except ValidationError as e:
            return web.json_response(self.__format_validation_error(e), status=400)
        except ValueError as e:
            return web.json_response({"error": "Invalid data", "message": str(e)}, status=400)

        if module_name == "confessions" and isinstance(validated_config, ConfessionsConfigModel):
            async with get_session() as session:
                db_config = await session.get(GuildConfessionsSettings, guild.id)
                if not db_config:
                    db_config = GuildConfessionsSettings(guild_id=guild.id)

                if (
                    validated_config.confessions_channel_id
                    and db_config.confessions_channel_id
                    != int(validated_config.confessions_channel_id)
                ):
                    channel = guild.get_channel(int(validated_config.confessions_channel_id))

                    if not channel:
                        return web.json_response(
                            {
                                "error": "Channel does not exist",
                                "message": f"The selected channel ({int(validated_config.confessions_channel_id)}) does not exist.",
                            },
                            status=404,
                        )

                    if not member or not self.__can_see_channel(member, channel):
                        return web.json_response(
                            {
                                "error": "User can't see channel",
                                "message": f"You are not allowed to see the {int(validated_config.confessions_channel_id)} channel.",
                            },
                            status=403,
                        )

                db_config.confessions_in_channel = validated_config.confessions_in_channel
                db_config.confessions_channel_id = (
                    int(validated_config.confessions_channel_id)
                    if validated_config.confessions_channel_id
                    else None
                )
                db_config.polls_enabled = validated_config.polls_enabled
                db_config.attachments_allowed = validated_config.attachments_allowed

                session.add(db_config)
        elif module_name == "moderation" and isinstance(validated_config, ModerationConfigModel):
            async with get_session() as session:
                db_config = await session.get(GuildModerationSettings, guild.id)
                if not db_config:
                    db_config = GuildModerationSettings(guild_id=guild.id)

                db_config.delete_confirmation = validated_config.delete_confirmation
                db_config.dm_users = validated_config.dm_users
                db_config.ban_days = validated_config.ban_days

                session.add(db_config)
        elif module_name == "automod" and isinstance(validated_config, AutomodConfigModel):
            if len(validated_config.rules) > config.limits.automod_rules:
                return web.json_response(
                    {
                        "error": "Limit exceeded",
                        "message": "You have gone over your allocated automod rules limit.",
                    },
                    status=403,
                )

            async with get_session() as session:
                db_config = await session.get(GuildAutomodSettings, guild.id)
                if not db_config:
                    db_config = GuildAutomodSettings(guild_id=guild.id)

                db_config.show_outcome_message = validated_config.show_outcome_message
                db_config.global_ignored_channels = [
                    int(channel) for channel in validated_config.global_ignored_channels
                ]
                db_config.global_ignored_roles = [
                    int(role) for role in validated_config.global_ignored_roles
                ]

                await session.execute(delete(AutomodRule).where(AutomodRule.guild_id == guild_id))
                for rule in validated_config.rules:
                    for criterion in rule.criteria:
                        if (
                            criterion.words
                            and len(criterion.words) > config.limits.bad_word_list_size
                        ):
                            return web.json_response(
                                {
                                    "error": "Limit exceeded",
                                    "message": "One of your automod criterion has too many words.",
                                },
                                status=403,
                            )

                    automod_rule = rule.to_sqlalchemy(guild_id)
                    session.add(automod_rule)

                session.add(db_config)

            await self.bot.refresh_guild_config_cache(guild_id)
            config = self.bot.guild_configs.get(guild_id)

            if config is None:
                return web.json_response(
                    {"error": "Failed to retrieve server configuration from cache"},
                    status=500,
                )
        elif module_name == "bouncer" and isinstance(validated_config, BouncerConfigModel):
            if len(validated_config.rules) > config.limits.bouncer_rules:
                return web.json_response(
                    {
                        "error": "Limit exceeded",
                        "message": "You have gone over your allocated bouncer rules limit.",
                    },
                    status=403,
                )

            async with get_session() as session:
                db_config = await session.get(GuildBouncerSettings, guild.id)
                if not db_config:
                    db_config = GuildBouncerSettings(guild_id=guild.id)

                await session.execute(delete(BouncerRule).where(BouncerRule.guild_id == guild_id))
                for rule in validated_config.rules:
                    for criterion in rule.criteria:
                        if (
                            criterion.words
                            and len(criterion.words) > config.limits.bad_word_list_size
                        ):
                            return web.json_response(
                                {
                                    "error": "Limit exceeded",
                                    "message": "One of your bouncer criterion has too many words.",
                                },
                                status=403,
                            )

                    bouncer_rule = rule.to_sqlalchemy(guild_id)
                    session.add(bouncer_rule)

                session.add(db_config)
        elif module_name == "logging" and isinstance(validated_config, LoggingConfigModel):
            async with get_session() as session:
                db_config = await session.get(GuildLoggingSettings, guild.id)
                if not db_config:
                    db_config = GuildLoggingSettings(guild_id=guild.id)

                db_config.channels = {
                    key: int(value)
                    for key, value in validated_config.channels.items()
                    if value is not None and key in LOGGING_EVENT_MAP
                }

                db_config.ignored_creator_user_ids = [
                    int(id) for id in validated_config.ignored_creator_user_ids
                ]
                db_config.ignored_creator_role_ids = [
                    int(id) for id in validated_config.ignored_creator_role_ids
                ]
                db_config.ignored_target_user_ids = [
                    int(id) for id in validated_config.ignored_target_user_ids
                ]
                db_config.ignored_target_role_ids = [
                    int(id) for id in validated_config.ignored_target_role_ids
                ]

                session.add(db_config)
        elif module_name == "fireboard" and isinstance(validated_config, FireboardConfigModel):
            if len(validated_config.boards) > config.limits.fireboards:
                return web.json_response(
                    {
                        "error": "Limit exceeded",
                        "message": "You have gone over your allocated fireboard limit.",
                    },
                    status=403,
                )

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
                        existing_board.send_notifications = new_board.send_notifications
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
                        send_notifications=new_board.send_notifications,
                        ignored_roles=[int(role_id) for role_id in new_board.ignored_roles],
                        ignored_channels=[
                            int(channel_id) for channel_id in new_board.ignored_channels
                        ],
                    )
                    session.add(board)
        elif module_name == "server_counters" and isinstance(
            validated_config, ServerCountersConfigModel
        ):
            if member and not member.guild_permissions.manage_channels:
                return web.json_response(
                    {
                        "error": "User missing permissions",
                        "message": "You are missing the Manage Channels permission.",
                    },
                    status=403,
                )

            if len(validated_config.channels) > config.limits.server_counters:
                return web.json_response(
                    {
                        "error": "Limit exceeded",
                        "message": "You have gone over your allocated server counter channel limit.",
                    },
                    status=403,
                )

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
                guild_preview = None

                for new_channel in validated_config.channels:
                    if new_channel.id is not None:
                        channel_ids.append(int(new_channel.id))

                    if new_channel.id is None:
                        if (
                            new_channel.type == ServerCounterType.ONLINE_MEMBERS
                            or new_channel.type == ServerCounterType.OFFLINE_MEMBERS
                        ):
                            if not guild_preview:
                                guild_preview = await self.bot.fetch_guild_preview(guild.id)

                            new_name = await resolve_counter(
                                guild_preview, new_channel.type, new_channel.name, []
                            )
                        else:
                            members = list(guild.members)
                            if (
                                new_channel.type == ServerCounterType.USERS
                                or new_channel.type == ServerCounterType.BOTS
                            ) and not guild.chunked:
                                members = await guild.chunk()

                            new_name = await resolve_counter(
                                guild, new_channel.type, new_channel.name, members
                            )

                        if not guild.me.guild_permissions.manage_channels:
                            return web.json_response(
                                {
                                    "error": "Bot - No Permissions",
                                    "message": "Titanium does not have permission to create channels in your server.",
                                }
                            )

                        try:
                            discord_channel = await guild.create_voice_channel(
                                name=new_name,
                                reason="Creating server counter channel",
                                overwrites={
                                    guild.default_role: discord.PermissionOverwrite(
                                        view_channel=True, connect=False
                                    ),
                                    guild.me: discord.PermissionOverwrite(
                                        connect=True, manage_channels=True
                                    ),
                                },
                            )
                            channel_ids.append(discord_channel.id)

                            channel = ServerCounterChannel(
                                id=discord_channel.id,
                                guild_id=guild.id,
                                name=new_channel.name,
                                count_type=new_channel.type,
                            )
                            session.add(channel)
                        except discord.Forbidden as e:
                            await log_error(
                                bot=self.bot,
                                module="Server Counters",
                                guild_id=guild.id,
                                error="Missing permissions to create server counter channel",
                                exc=e,
                            )
                        except discord.HTTPException as e:
                            await log_error(
                                bot=self.bot,
                                module="Server Counters",
                                guild_id=guild.id,
                                error="Unexpected Discord error when creating server counter channel",
                                exc=e,
                            )
                        except Exception as e:
                            await log_error(
                                bot=self.bot,
                                module="Server Counters",
                                guild_id=guild.id,
                                error="Unexpected error when creating server counter channel",
                                exc=e,
                            )
                    else:
                        existing_channel = await session.get(
                            ServerCounterChannel, int(new_channel.id)
                        )

                        if existing_channel and existing_channel.guild_id == guild.id:
                            existing_channel.name = new_channel.name
                            existing_channel.count_type = new_channel.type

                            session.add(existing_channel)
                        else:
                            members = list(guild.members)
                            if (
                                new_channel.type == ServerCounterType.USERS
                                or new_channel.type == ServerCounterType.BOTS
                            ) and not guild.chunked:
                                members = await guild.chunk()

                            new_name = await resolve_counter(
                                guild, new_channel.type, new_channel.name, members
                            )

                            if not guild.me.guild_permissions.manage_channels:
                                return web.json_response(
                                    {
                                        "error": "Bot - No Permissions",
                                        "message": "Titanium does not have permission to create channels in your server.",
                                    }
                                )

                            try:
                                discord_channel = await guild.create_voice_channel(
                                    name=new_name,
                                    reason="Creating server counter channel",
                                )
                                channel_ids.append(discord_channel.id)
                            except discord.Forbidden as e:
                                await log_error(
                                    bot=self.bot,
                                    module="Server Counters",
                                    guild_id=guild.id,
                                    error="Missing permissions to create server counter channel",
                                    exc=e,
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
                            )
                            session.add(channel)

                await session.commit()
                await session.refresh(existing_config, ["channels"])

                # Delete removed channels
                for existing_channel in existing_config.channels:
                    if existing_channel.id not in channel_ids:
                        discord_channel = guild.get_channel(existing_channel.id)

                        if discord_channel:
                            if not guild.me.guild_permissions.manage_channels:
                                return web.json_response(
                                    {
                                        "error": "Bot - No Permissions",
                                        "message": "Titanium does not have permission to delete channels in your server.",
                                    }
                                )

                            try:
                                await discord_channel.delete(
                                    reason="Removing server counter channel"
                                )
                            except discord.Forbidden as e:
                                await log_error(
                                    bot=self.bot,
                                    module="Server Counters",
                                    guild_id=guild.id,
                                    error=f"Missing permissions to delete channel #{discord_channel.name} ({discord_channel.id})",
                                    exc=e,
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
            if len(validated_config.levels) > config.limits.leaderboard_levels:
                return web.json_response(
                    {
                        "error": "Limit exceeded",
                        "message": "You have gone over your allocated leaderboard level limit.",
                    },
                    status=403,
                )

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

                if (
                    validated_config.notification_channel
                    and existing_config.notification_channel
                    != int(validated_config.notification_channel)
                ):
                    channel = guild.get_channel(int(validated_config.notification_channel))

                    if not channel:
                        return web.json_response(
                            {
                                "error": "Channel does not exist",
                                "message": f"The selected channel ({int(validated_config.notification_channel)}) does not exist.",
                            },
                            status=404,
                        )

                    if not member or not self.__can_see_channel(member, channel):
                        return web.json_response(
                            {
                                "error": "User can't see channel",
                                "message": f"You are not allowed to see the {int(validated_config.notification_channel)} channel.",
                            },
                            status=403,
                        )

                existing_config.mode = validated_config.mode
                existing_config.base_xp = validated_config.base_xp
                existing_config.min_xp = validated_config.min_xp
                existing_config.max_xp = validated_config.max_xp
                existing_config.xp_mult = validated_config.xp_mult
                existing_config.vc_enabled = validated_config.vc_enabled
                existing_config.vc_mode = validated_config.vc_mode
                existing_config.vc_delay = validated_config.vc_delay
                existing_config.vc_base_xp = validated_config.vc_base_xp
                existing_config.vc_min_xp = validated_config.vc_min_xp
                existing_config.vc_max_xp = validated_config.vc_max_xp
                existing_config.ignored_channels = [
                    int(channel) for channel in validated_config.ignored_channels
                ]
                existing_config.ignored_roles = [
                    int(role) for role in validated_config.ignored_roles
                ]
                existing_config.bot_message_tracking = validated_config.bot_message_tracking
                existing_config.bot_message_xp = validated_config.bot_message_xp
                existing_config.bot_vc_tracking = validated_config.bot_vc_tracking
                existing_config.bot_vc_xp = validated_config.bot_vc_xp
                existing_config.cooldown = validated_config.cooldown
                existing_config.levelup_notifications = validated_config.levelup_notifications
                existing_config.notification_ping = validated_config.notification_ping
                existing_config.notification_channel = (
                    int(validated_config.notification_channel)
                    if validated_config.notification_channel
                    else None
                )
                existing_config.web_leaderboard_enabled = validated_config.web_leaderboard_enabled
                existing_config.web_login_required = validated_config.web_login_required
                existing_config.delete_leavers = validated_config.delete_leavers
                existing_config.stack_roles = validated_config.stack_roles
                existing_config.levels = [
                    LeaderboardLevels(
                        xp=level.xp_required,
                        reward_roles=[int(role) for role in level.reward_roles if role.isdigit()],
                    )
                    for level in validated_config.levels
                ]

                session.add(existing_config)
        elif module_name == "tags" and isinstance(validated_config, TagsConfigModel):
            async with get_session() as session:
                db_config = await session.get(GuildTagSettings, guild.id)
                if not db_config:
                    db_config = GuildTagSettings(guild_id=guild.id)

                db_config.allow_user_tags = validated_config.allow_user_tags
                db_config.prefix_fallback = validated_config.prefix_fallback

                session.add(db_config)
        elif module_name == "rep" and isinstance(validated_config, RepConfigModel):
            async with get_session() as session:
                db_config = await session.get(GuildRepSettings, guild.id)
                if not db_config:
                    db_config = GuildRepSettings(guild_id=guild.id)

                db_config.rep_hint = validated_config.rep_hint
                db_config.allow_rep_remove = validated_config.allow_rep_remove
                db_config.delete_leavers = validated_config.delete_leavers

                db_config.web_leaderboard_enabled = validated_config.web_leaderboard_enabled
                db_config.web_login_required = validated_config.web_login_required

                db_config.ignored_channels = [
                    int(channel) for channel in validated_config.ignored_channels
                ]
                db_config.ignored_roles = [int(role) for role in validated_config.ignored_roles]

                session.add(db_config)
        else:
            return web.json_response({"error": "Module not found"}, status=404)

        await self.bot.refresh_guild_config_cache(guild.id)
        return web.Response(status=204)

    async def cog_unload(self) -> None:
        if self.server_task:
            self.server_task.cancel()

        if self.site:
            await self.site.stop()

        if self.runner:
            await self.runner.cleanup()


async def setup(bot: TitaniumBot):
    await bot.add_cog(APICog(bot))
