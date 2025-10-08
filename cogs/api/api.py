import asyncio
import logging
import os
import uuid
from typing import TYPE_CHECKING, Optional

from aiohttp import web
from discord.ext import commands
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from sqlalchemy import delete

from lib.helpers.resolve_counter import resolve_counter
from lib.sql.sql import (
    AutomodAction,
    AutomodRule,
    FireboardBoard,
    GuildAutomodSettings,
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


class ModuleModel(BaseModel):
    moderation: bool
    automod: bool
    logging: bool
    fireboard: bool
    server_counters: bool


class SettingsModel(BaseModel):
    loading_reaction: bool


class GuildSettingsModel(BaseModel):
    modules: ModuleModel
    settings: SettingsModel
    prefixes: list[str]

    @field_validator("prefixes")
    def validate_prefixes(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one prefix is required")
        if len(v) > 5:
            raise ValueError("A maximum of 5 prefixes are allowed")
        for prefix in v:
            if not (1 <= len(prefix) <= 5):
                raise ValueError("Each prefix must be between 1 and 5 characters long")
        return v


class ModerationConfigModel(BaseModel):
    delete_confirmation: bool
    dm_users: bool


class AutomodActionModel(BaseModel):
    type: str
    duration: Optional[int] = None
    reason: Optional[str] = None

    @field_validator("type")
    def validate_action_type(cls, v):
        valid_types = ["warn", "mute", "kick", "ban", "delete"]
        if v not in valid_types:
            raise ValueError(f"Action type must be one of: {valid_types}")
        return v

    @model_validator(mode="after")
    def validate_mute_duration(self):
        if self.type == "mute" and (self.duration is None or self.duration <= 0):
            raise ValueError("Mute actions must have a positive duration")
        return self

    def to_sqlalchemy(self, rule_type: str, guild_id: int) -> AutomodAction:
        return AutomodAction(
            guild_id=guild_id,
            rule_type=rule_type,
            action_type=self.type,
            duration=self.duration,
            reason=self.reason,
        )


class AutomodRuleModel(BaseModel):
    id: Optional[str] = None
    rule_type: str
    rule_name: str = ""
    words: Optional[list[str]] = []
    match_whole_word: bool = False
    case_sensitive: bool = False
    antispam_type: Optional[str] = None
    threshold: int
    duration: int
    actions: list[AutomodActionModel]

    @field_validator("rule_type")
    def validate_rule_type(cls, v):
        valid_types = [
            "badword_detection",
            "spam_detection",
            "malicious_link",
            "phishing_link",
        ]
        if v not in valid_types:
            raise ValueError(f"Rule type must be one of: {valid_types}")
        return v

    @field_validator("id")
    def validate_id(cls, v):
        if v == "":
            return None
        return v

    def to_sqlalchemy(self, guild_id: int) -> AutomodRule:
        rule = AutomodRule(
            id=uuid.UUID(self.id),
            guild_id=guild_id,
            rule_type=self.rule_type,
            rule_name=self.rule_name,
            words=self.words or [],
            match_whole_word=self.match_whole_word,
            case_sensitive=self.case_sensitive,
            antispam_type=self.antispam_type,
            threshold=self.threshold,
            duration=self.duration,
        )

        # Convert actions
        for action_model in self.actions:
            rule.actions.append(action_model.to_sqlalchemy(self.rule_type, guild_id))

        return rule


class AutomodConfigModel(BaseModel):
    badword_detection: list[AutomodRuleModel]
    spam_detection: list[AutomodRuleModel]
    malicious_link_detection: list[AutomodRuleModel]
    phishing_link_detection: list[AutomodRuleModel]


class LoggingConfigModel(BaseModel):
    app_command_perm_update_id: Optional[str]
    dc_automod_rule_create_id: Optional[str]
    dc_automod_rule_update_id: Optional[str]
    dc_automod_rule_delete_id: Optional[str]
    channel_create_id: Optional[str]
    channel_update_id: Optional[str]
    channel_delete_id: Optional[str]
    guild_name_update_id: Optional[str]
    guild_afk_channel_update_id: Optional[str]
    guild_afk_timeout_update_id: Optional[str]
    guild_icon_update_id: Optional[str]
    guild_emoji_create_id: Optional[str]
    guild_emoji_delete_id: Optional[str]
    guild_sticker_create_id: Optional[str]
    guild_sticker_delete_id: Optional[str]
    guild_invite_create_id: Optional[str]
    guild_invite_delete_id: Optional[str]
    member_join_id: Optional[str]
    member_leave_id: Optional[str]
    member_nickname_update_id: Optional[str]
    member_roles_update_id: Optional[str]
    member_ban_id: Optional[str]
    member_unban_id: Optional[str]
    member_kick_id: Optional[str]
    member_timeout_id: Optional[str]
    member_untimeout_id: Optional[str]
    message_edit_id: Optional[str]
    message_delete_id: Optional[str]
    message_bulk_delete_id: Optional[str]
    poll_create_id: Optional[str]
    poll_delete_id: Optional[str]
    reaction_clear_id: Optional[str]
    reaction_clear_emoji_id: Optional[str]
    role_create_id: Optional[str]
    role_update_id: Optional[str]
    role_delete_id: Optional[str]
    scheduled_event_create_id: Optional[str]
    scheduled_event_update_id: Optional[str]
    scheduled_event_delete_id: Optional[str]
    soundboard_sound_create_id: Optional[str]
    soundboard_sound_update_id: Optional[str]
    soundboard_sound_delete_id: Optional[str]
    stage_instance_create_id: Optional[str]
    stage_instance_update_id: Optional[str]
    stage_instance_delete_id: Optional[str]
    thread_create_id: Optional[str]
    thread_update_id: Optional[str]
    thread_remove_id: Optional[str]
    thread_delete_id: Optional[str]
    voice_join_id: Optional[str]
    voice_leave_id: Optional[str]
    voice_move_id: Optional[str]
    voice_mute_id: Optional[str]
    voice_unmute_id: Optional[str]
    voice_deafen_id: Optional[str]
    voice_undeafen_id: Optional[str]
    titanium_warn_id: Optional[str]
    titanium_mute_id: Optional[str]
    titanium_unmute_id: Optional[str]
    titanium_kick_id: Optional[str]
    titanium_ban_id: Optional[str]
    titanium_unban_id: Optional[str]
    titanium_case_delete_id: Optional[str]
    titanium_case_comment_id: Optional[str]
    titanium_automod_trigger_id: Optional[str]


class FireboardBoardModel(BaseModel):
    id: Optional[str] = None
    channel_id: str
    reaction: str
    threshold: int
    ignore_bots: bool
    ignore_self_reactions: bool
    ignored_roles: list[str] = []
    ignored_channels: list[str] = []

    @field_validator("id")
    def validate_id(cls, v: str):
        if v.strip() == "":
            return None
        return v


class FireboardConfigModel(BaseModel):
    global_ignored_roles: list[str] = []
    global_ignored_channels: list[str] = []
    boards: list[FireboardBoardModel] = []


class ServerCounterChannelModel(BaseModel):
    id: Optional[str] = None
    name: str
    type: str

    @field_validator("type")
    def validate_type(cls, v):
        valid_types = [
            "total_members",
            "users",
            "bots",
            "online_members",
            "members_status_online",
            "members_status_idle",
            "members_status_dnd",
            "members_activity",
            "members_custom_status",
            "offline_members",
            "channels",
        ]
        if v not in valid_types:
            raise ValueError(f"Channel type must be one of: {valid_types}")
        return v

    @field_validator("id")
    def validate_id(cls, v: str):
        if v.strip() == "":
            return None
        return v


class ServerCountersConfigModel(BaseModel):
    channels: list[ServerCounterChannelModel] = []


class APICog(commands.Cog):
    """API server for dashboard, website and status page"""

    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
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
                "initial_connect": self.bot.connect_time.timestamp()
                if self.bot.connect_time
                else None,
                "last_disconnect": self.bot.last_disconnect.timestamp()
                if self.bot.last_disconnect
                else None,
                "last_resume": self.bot.last_resume.timestamp()
                if self.bot.last_resume
                else None,
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
                        "color": role.colour.value,
                        "hoist": role.hoist,
                        "position": role.position,
                    }
                    for role in guild.roles
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
                                "category": str(channel.category_id)
                                if channel.category_id
                                else None,
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
        if module_name == "moderation":
            config = self.bot.guild_configs[guild.id]

            if not config.moderation_settings:
                return web.json_response(
                    {
                        "delete_confirmation": True,
                        "dm_users": True,
                    }
                )

            moderation_settings = config.moderation_settings
            return web.json_response(
                {
                    "delete_confirmation": moderation_settings.delete_confirmation,
                    "dm_users": moderation_settings.dm_users,
                }
            )
        elif module_name == "automod":
            config = self.bot.guild_configs[guild.id]

            if not config.automod_settings:
                return web.json_response(
                    {
                        "badword_detection": [],
                        "spam_detection": [],
                        "malicious_link_detection": [],
                        "phishing_link_detection": [],
                    }
                )

            return web.json_response(
                {
                    detection_type: [
                        {
                            "id": str(rule.id),
                            "rule_type": rule.rule_type,
                            "words": rule.words,
                            "match_whole_word": rule.match_whole_word,
                            "case_sensitive": rule.case_sensitive,
                            "threshold": rule.threshold,
                            "duration": rule.duration,
                            "actions": [
                                {
                                    "type": action.action_type,
                                    "duration": action.duration,
                                    "reason": action.reason,
                                }
                                for action in (rule.actions or [])
                            ],
                        }
                        for rule in getattr(
                            config.automod_settings, f"{detection_type}_rules", []
                        )
                    ]
                    for detection_type in [
                        "badword_detection",
                        "spam_detection",
                        "malicious_link_detection",
                        "phishing_link_detection",
                    ]
                }
            )
        elif module_name == "logging":
            config = self.bot.guild_configs[guild.id]

            if not config.logging_settings:
                default_values = {}
                for field_name, field_info in LoggingConfigModel.model_fields.items():
                    default_values[field_name] = None

                return web.json_response(default_values)

            logging_settings = config.logging_settings
            response_data = {}

            for field_name in LoggingConfigModel.model_fields.keys():
                attr = getattr(logging_settings, field_name, None)
                if attr is not None:
                    response_data[field_name] = str(attr)
                else:
                    response_data[field_name] = None

            return web.json_response(response_data)
        elif module_name == "fireboard":
            config = self.bot.guild_configs[guild.id]

            if not config.fireboard_settings:
                return web.json_response(
                    {
                        "global_ignored_roles": [],
                        "global_ignored_channels": [],
                        "boards": [],
                    }
                )

            fireboard_settings = config.fireboard_settings
            return web.json_response(
                {
                    "global_ignored_roles": [
                        str(role_id)
                        for role_id in fireboard_settings.global_ignored_roles
                    ],
                    "global_ignored_channels": [
                        str(channel_id)
                        for channel_id in fireboard_settings.global_ignored_channels
                    ],
                    "boards": [
                        {
                            "id": str(board.id),
                            "channel_id": str(board.channel_id),
                            "reaction": board.reaction,
                            "threshold": board.threshold,
                            "ignore_bots": board.ignore_bots,
                            "ignore_self_reactions": board.ignore_self_reactions,
                            "ignored_roles": [
                                str(role_id) for role_id in board.ignored_roles
                            ],
                            "ignored_channels": [
                                str(channel_id) for channel_id in board.ignored_channels
                            ],
                        }
                        for board in fireboard_settings.fireboard_boards
                    ],
                }
            )
        elif module_name == "server_counters":
            config = self.bot.guild_configs[guild.id]

            if not config.server_counters_settings:
                return web.json_response({"channels": []})

            server_counters_settings = config.server_counters_settings
            return web.json_response(
                {
                    "channels": [
                        {
                            "id": str(channel.id),
                            "name": channel.name,
                            "type": str(channel.count_type),
                        }
                        for channel in server_counters_settings.channels
                    ]
                }
            )
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

        if module_name == "moderation":
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
