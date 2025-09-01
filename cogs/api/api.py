import asyncio
import logging
import os
from typing import TYPE_CHECKING, Optional

from aiohttp import web
from discord.ext import commands
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from sqlalchemy import delete

from lib.sql import (
    AutomodAction,
    AutomodRule,
    ServerAutomodSettings,
    get_session,
)

if TYPE_CHECKING:
    from main import TitaniumBot


class AutomodActionModel(BaseModel):
    id: Optional[int] = None
    type: str
    duration: Optional[int] = None
    reason: Optional[str] = None
    order: int

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
            order=self.order,
        )


class AutomodRuleModel(BaseModel):
    id: Optional[int] = None
    rule_type: str
    words: Optional[list[str]] = []
    antispam_type: Optional[str] = None
    occurrences: int
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

    def to_sqlalchemy(self, guild_id: int) -> AutomodRule:
        rule = AutomodRule(
            guild_id=guild_id,
            rule_type=self.rule_type,
            words=self.words or [],
            antispam_type=self.antispam_type,
            occurrences=self.occurrences,
            threshold=self.threshold,
            duration=self.duration,
        )

        # Convert actions
        for action_model in self.actions:
            rule.actions.append(action_model.to_sqlalchemy(self.rule_type, guild_id))

        return rule


class DetectionRulesModel(BaseModel):
    enabled: bool
    rules: list[AutomodRuleModel]


class AutomodConfigModel(BaseModel):
    badword_detection: DetectionRulesModel
    spam_detection: DetectionRulesModel
    malicious_link_detection: DetectionRulesModel
    phishing_link_detection: DetectionRulesModel


class APICog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
        self.app = None
        self.runner = None
        self.site = None

        # Get host and port from env with defaults
        self.host = os.getenv("BOT_API_HOST", "127.0.0.1")
        self.port = int(os.getenv("BOT_API_PORT", 5000))

        logging.info(f"[API] Starting API server on {self.host}:{self.port}")
        self.server_task = asyncio.create_task(self.start_server())

    def _serialize_detection_rules(
        self, enabled: bool, rules: list[AutomodRule]
    ) -> dict:
        return {
            "enabled": enabled,
            "rules": [self._serialize_rule(rule) for rule in rules],
        }

    def _serialize_rule(self, rule: AutomodRule) -> dict:
        return {
            "id": rule.id,
            "rule_type": rule.rule_type,
            "words": rule.words,
            "occurrences": rule.occurrences,
            "threshold": rule.threshold,
            "duration": rule.duration,
            "actions": [self._serialize_action(action) for action in rule.actions],
        }

    def _serialize_action(self, action: AutomodAction) -> dict:
        return {
            "id": action.id,
            "type": action.action_type,
            "duration": action.duration,
            "reason": action.reason,
            "order": action.order,
        }

    async def _apply_automod_config(
        self, guild_id: int, config: AutomodConfigModel
    ) -> ServerAutomodSettings | None:
        async with get_session() as session:
            automod_settings = await session.get(ServerAutomodSettings, guild_id)

            if not automod_settings:
                await self.bot.init_guild(guild_id)
                automod_settings = await session.get(ServerAutomodSettings, guild_id)

                if not automod_settings:
                    raise ValueError("Automod settings not found")

            automod_settings.badword_detection = config.badword_detection.enabled
            automod_settings.spam_detection = config.spam_detection.enabled
            automod_settings.malicious_link_detection = (
                config.malicious_link_detection.enabled
            )
            automod_settings.phishing_link_detection = (
                config.phishing_link_detection.enabled
            )

            await session.execute(
                delete(AutomodRule).where(AutomodRule.guild_id == guild_id)
            )

            for detection_config in [
                config.badword_detection,
                config.spam_detection,
                config.malicious_link_detection,
                config.phishing_link_detection,
            ]:
                for rule_model in detection_config.rules:
                    automod_rule = rule_model.to_sqlalchemy(guild_id)
                    session.add(automod_rule)

        await self.bot.refresh_guild_config_cache(guild_id)
        config = self.bot.server_configs.get(guild_id)

        if config is None:
            return None

        return config.automod_settings

    async def start_server(self):
        try:
            self.app = web.Application()
            self.register_routes()

            self.runner = web.AppRunner(self.app, access_log=None)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()

            logging.info(
                f"[API] API server started successfully on {self.host}:{self.port}"
            )
        except Exception as e:
            logging.error(f"[API] Failed to start API server: {e}")
            exit(1)

    def register_routes(self):
        if self.app is None:
            return

        self.app.router.add_get("/", self.index)
        self.app.router.add_get("/info", self.info)
        self.app.router.add_get("/ping", self.ping)
        self.app.router.add_get("/status", self.status)
        self.app.router.add_get("/stats", self.stats)
        self.app.router.add_get("/{guild_id}/module/{module_name}", self.module_get)
        self.app.router.add_put("/{guild_id}/module/{module_name}", self.module_update)

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

    async def module_get(self, request: web.Request) -> web.Response:
        await self.bot.wait_until_ready()

        guild_id = request.match_info.get("guild_id")
        module_name = request.match_info.get("module_name")
        module_name = module_name.lower() if module_name else None

        if not guild_id or not module_name:
            return web.json_response(
                {"error": "guild_id and module_name required"}, status=400
            )

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "Guild not found"}, status=404)

        config = self.bot.server_configs.get(guild.id)
        if not config:
            await self.bot.refresh_guild_config_cache(guild.id)
            config = self.bot.server_configs.get(guild.id)

            if not config:
                await self.bot.init_guild(guild.id)

        if module_name == "automod":
            config = self.bot.server_configs[guild.id].automod_settings

            if not config:
                return web.json_response(
                    {
                        "badword_detection": {
                            "enabled": False,
                            "rules": [],
                        },
                        "spam_detection": {
                            "enabled": False,
                            "rules": [],
                        },
                        "malicious_link_detection": {
                            "enabled": False,
                            "rules": [],
                        },
                        "phishing_link_detection": {
                            "enabled": False,
                            "rules": [],
                        },
                    }
                )

            return web.json_response(
                {
                    detection_type: self._serialize_detection_rules(
                        getattr(config, f"{detection_type}", False),
                        getattr(config, f"{detection_type}_rules", []),
                    )
                    for detection_type in [
                        "badword_detection",
                        "spam_detection",
                        "malicious_link_detection",
                        "phishing_link_detection",
                    ]
                }
            )
        else:
            return web.json_response({"error": "Module not found"}, status=404)

    async def module_update(self, request: web.Request) -> web.Response:
        await self.bot.wait_until_ready()

        guild_id = request.match_info.get("guild_id")
        module_name = request.match_info.get("module_name")
        module_name = module_name.lower() if module_name else None

        if not guild_id or not module_name:
            return web.json_response(
                {"error": "guild_id and module_name required"}, status=400
            )

        guild = self.bot.get_guild(int(guild_id))
        if not guild:
            return web.json_response({"error": "Guild not found"}, status=404)

        config = self.bot.server_configs.get(guild.id)
        if not config:
            await self.bot.refresh_guild_config_cache(guild.id)
            config = self.bot.server_configs.get(guild.id)

            if not config:
                await self.bot.init_guild(guild.id)

        if module_name == "automod":
            try:
                data = await request.json()
                validated_config = AutomodConfigModel(**data)

                config = await self._apply_automod_config(guild.id, validated_config)

                if config is None:
                    return web.json_response(
                        {"error": "Failed to update configuration"}, status=500
                    )

                return web.json_response(
                    {
                        detection_type: self._serialize_detection_rules(
                            getattr(config, f"{detection_type}", False),
                            getattr(config, f"{detection_type}_rules", []),
                        )
                        for detection_type in [
                            "badword_detection",
                            "spam_detection",
                            "malicious_link_detection",
                            "phishing_link_detection",
                        ]
                    }
                )
            except ValidationError as e:
                return web.json_response(
                    {"error": "Validation failed", "details": e.errors()}, status=400
                )
            except ValueError as e:
                return web.json_response(
                    {"error": "Invalid data", "message": str(e)}, status=400
                )
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
