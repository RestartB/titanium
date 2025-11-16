from typing import TYPE_CHECKING

from aiohttp import web
from discord import Guild

if TYPE_CHECKING:
    from main import TitaniumBot

from lib.api.validators import LoggingConfigModel


def confession_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]
    if not config.confession_settings:
        return web.json_response(
            {
                "confession_channel_id": None,
                "confession_log_channel_id": None,
            }
        )
    return web.json_response(
        {
            "confession_channel_id": str(config.confession_settings.confession_channel_id),
            "confession_log_channel_id": str(config.confession_settings.confession_log_channel_id),
        }
    )


def moderation_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]

    if not config.moderation_settings:
        return web.json_response(
            {
                "delete_confirmation": False,
                "dm_users": True,
                "external_cases": True,
                "external_case_dms": False,
            }
        )

    moderation_settings = config.moderation_settings
    return web.json_response(
        {
            "delete_confirmation": moderation_settings.delete_confirmation,
            "dm_users": moderation_settings.dm_users,
            "external_cases": moderation_settings.external_cases,
            "external_case_dms": moderation_settings.external_case_dms,
        }
    )


def automod_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]

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
                    "antispam_type": rule.antispam_type,
                    "words": rule.words,
                    "match_whole_word": rule.match_whole_word,
                    "case_sensitive": rule.case_sensitive,
                    "threshold": rule.threshold,
                    "duration": rule.duration,
                    "actions": [
                        {
                            "type": action.action_type,
                            "duration": action.duration,
                            "role_id": str(action.role_id) if action.role_id else None,
                            "reason": action.reason,
                        }
                        for action in (rule.actions or [])
                    ],
                }
                for rule in getattr(config.automod_settings, f"{detection_type}_rules", [])
            ]
            for detection_type in [
                "badword_detection",
                "spam_detection",
                "malicious_link_detection",
                "phishing_link_detection",
            ]
        }
    )


def bouncer_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]

    if not config.bouncer_settings:
        return web.json_response({"rules": []})

    bouncer_settings = config.bouncer_settings
    return web.json_response(
        {
            "rules": [
                {
                    "id": str(rule.id),
                    "enabled": rule.enabled,
                    "criteria": [
                        {
                            "type": criterion.criteria_type,
                            "account_age": criterion.account_age,
                            "words": criterion.words,
                            "match_whole_word": criterion.match_whole_word,
                            "case_sensitive": criterion.case_sensitive,
                        }
                        for criterion in rule.criteria
                    ],
                    "actions": [
                        {
                            "type": action.action_type,
                            "duration": action.duration,
                            "role_id": str(action.role_id) if action.role_id else None,
                            "reason": action.reason,
                            "message_content": action.message_content,
                            "dm_user": action.dm_user,
                        }
                        for action in rule.actions
                    ],
                }
                for rule in bouncer_settings.rules
            ]
        }
    )


def logging_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]

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


def fireboard_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]

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
                str(role_id) for role_id in fireboard_settings.global_ignored_roles
            ],
            "global_ignored_channels": [
                str(channel_id) for channel_id in fireboard_settings.global_ignored_channels
            ],
            "boards": [
                {
                    "id": str(board.id),
                    "channel_id": str(board.channel_id),
                    "reaction": board.reaction,
                    "threshold": board.threshold,
                    "ignore_bots": board.ignore_bots,
                    "ignore_self_reactions": board.ignore_self_reactions,
                    "ignored_roles": [str(role_id) for role_id in board.ignored_roles],
                    "ignored_channels": [str(channel_id) for channel_id in board.ignored_channels],
                }
                for board in fireboard_settings.fireboard_boards
            ],
        }
    )


def server_counters_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]

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
                    "activity_name": channel.activity_name,
                }
                for channel in server_counters_settings.channels
            ]
        }
    )
