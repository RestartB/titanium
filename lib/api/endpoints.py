from typing import TYPE_CHECKING

from aiohttp import web
from discord import Guild

if TYPE_CHECKING:
    from main import TitaniumBot

from lib.enums.leaderboard import LeaderboardCalcType, LeaderboardVcCalcType


def confessions_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]
    if not config.confessions_settings:
        return web.json_response(
            {"confessions_in_channel": True, "confessions_channel_id": None, "polls_enabled": True}
        )
    return web.json_response(
        {
            "confessions_in_channel": config.confessions_settings.confessions_in_channel,
            "confessions_channel_id": str(config.confessions_settings.confessions_channel_id)
            if config.confessions_settings.confessions_channel_id
            else None,
            "polls_enabled": config.confessions_settings.polls_enabled,
            "attachments_allowed": config.confessions_settings.attachments_allowed,
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
                "ban_days": 0,
            }
        )

    moderation_settings = config.moderation_settings
    return web.json_response(
        {
            "delete_confirmation": moderation_settings.delete_confirmation,
            "dm_users": moderation_settings.dm_users,
            "external_cases": moderation_settings.external_cases,
            "ban_days": moderation_settings.ban_days,
        }
    )


def automod_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]

    if not config.automod_settings:
        return web.json_response(
            {
                "rules": [],
                "show_outcome_message": True,
                "global_ignored_roles": [],
                "global_ignored_channels": [],
            }
        )

    rules = config.automod_settings.rules.copy()
    rules.sort(key=lambda r: r.order)

    return web.json_response(
        {
            "rules": [
                {
                    "id": str(rule.id),
                    "rule_name": rule.rule_name,
                    "enabled": rule.enabled,
                    "evaluate_edits": rule.evaluate_edits,
                    "match_all_criteria": rule.match_all_criteria,
                    "order": rule.order,
                    "stop_if_triggered": rule.stop_if_triggered,
                    "criteria": [
                        {
                            "id": str(criteria.id),
                            "type": criteria.type,
                            "threshold": criteria.threshold,
                            "duration": criteria.duration,
                            "words": criteria.words,
                            "match_whole_word": criteria.match_whole_word,
                            "match_all_words": criteria.match_all_words,
                            "case_sensitive": criteria.case_sensitive,
                        }
                        for criteria in rule.criteria
                    ],
                    "actions": [
                        {
                            "id": str(action.id),
                            "type": action.type,
                            "duration": action.duration,
                            "reason": action.reason,
                            "role_ids": action.role_ids,
                            "message_content": action.message_content,
                            "message_reply": action.message_reply,
                            "message_mention": action.message_mention,
                            "message_embed": action.message_embed,
                            "embed_colour": action.embed_colour,
                        }
                        for action in rule.actions
                    ],
                }
                for rule in rules
            ],
            "show_outcome_message": config.automod_settings.show_outcome_message,
            "global_ignored_roles": config.automod_settings.global_ignored_roles,
            "global_ignored_channels": config.automod_settings.global_ignored_channels,
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
                    "evaluate_for_existing_members": rule.evaluate_for_existing_members,
                    "criteria": [
                        {
                            "type": criterion.type.value,
                            "account_age": criterion.account_age,
                            "words": criterion.words,
                            "match_whole_word": criterion.match_whole_word,
                            "case_sensitive": criterion.case_sensitive,
                        }
                        for criterion in rule.criteria
                    ],
                    "actions": [
                        {
                            "type": action.type.value,
                            "duration": action.duration,
                            "role_id": str(action.role_id) if action.role_id else None,
                            "reason": action.reason,
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
        return web.json_response({"channels": []})

    return web.json_response(
        {"channels": {key: str(value) for key, value in config.logging_settings.channels.items()}}
    )


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
                    "send_notifications": board.send_notifications,
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
                    "type": str(channel.count_type.value),
                }
                for channel in server_counters_settings.channels
            ]
        }
    )


def leaderboard_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]

    if not config.leaderboard_settings:
        return web.json_response(
            {
                "mode": LeaderboardCalcType.FIXED.value,
                "cooldown": 5,
                "xp": 10,
                "min_xp": 15,
                "max_xp": 25,
                "xp_mult": 1.0,
                "vc_enabled": False,
                "vc_mode": LeaderboardVcCalcType.FIXED.value,
                "vc_delay": 0,
                "vc_base_xp": 10,
                "vc_min_xp": 15,
                "vc_max_xp": 25,
                "ignored_roles": [],
                "ignored_channels": [],
                "levelup_notifications": True,
                "notification_ping": True,
                "notification_channel": None,
                "web_leaderboard_enabled": True,
                "web_login_required": False,
                "delete_leavers": False,
                "stack_roles": True,
                "levels": [],
            }
        )

    lb_settings = config.leaderboard_settings
    lb_settings.levels.sort(key=lambda level: level.xp)

    return web.json_response(
        {
            "mode": lb_settings.mode.value,
            "cooldown": lb_settings.cooldown,
            "base_xp": lb_settings.base_xp,
            "min_xp": lb_settings.min_xp,
            "max_xp": lb_settings.max_xp,
            "xp_mult": lb_settings.xp_mult,
            "vc_enabled": lb_settings.vc_enabled,
            "vc_mode": lb_settings.vc_mode,
            "vc_delay": lb_settings.vc_delay,
            "vc_base_xp": lb_settings.vc_base_xp,
            "vc_min_xp": lb_settings.vc_min_xp,
            "vc_max_xp": lb_settings.vc_max_xp,
            "ignored_roles": [str(role_id) for role_id in lb_settings.ignored_roles],
            "ignored_channels": [str(channel_id) for channel_id in lb_settings.ignored_channels],
            "levelup_notifications": lb_settings.levelup_notifications,
            "notification_ping": lb_settings.notification_ping,
            "notification_channel": str(lb_settings.notification_channel)
            if lb_settings.notification_channel
            else None,
            "web_leaderboard_enabled": lb_settings.web_leaderboard_enabled,
            "web_login_required": lb_settings.web_login_required,
            "delete_leavers": lb_settings.delete_leavers,
            "stack_roles": lb_settings.stack_roles,
            "levels": [
                {
                    "id": str(level.id),
                    "xp_required": level.xp,
                    "reward_roles": [str(role_id) for role_id in level.reward_roles],
                }
                for level in lb_settings.levels
            ],
        }
    )


def tags_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]
    if not config.tag_settings:
        return web.json_response(
            {
                "allow_user_tags": True,
                "prefix_fallback": True,
            }
        )
    return web.json_response(
        {
            "allow_user_tags": config.tag_settings.allow_user_tags,
            "prefix_fallback": config.tag_settings.prefix_fallback,
        }
    )


def rep_info(bot: TitaniumBot, request: web.Request, guild: Guild) -> web.Response:
    config = bot.guild_configs[guild.id]

    if not config.rep_settings:
        return web.json_response(
            {
                "rep_hint": True,
                "allow_rep_remove": True,
                "delete_leavers": False,
                "web_leaderboard_enabled": True,
                "web_login_required": True,
                "ignored_roles": [],
                "ignored_channels": [],
            }
        )

    rep_settings = config.rep_settings

    return web.json_response(
        {
            "rep_hint": rep_settings.rep_hint,
            "allow_rep_remove": rep_settings.allow_rep_remove,
            "delete_leavers": rep_settings.delete_leavers,
            "web_leaderboard_enabled": rep_settings.web_leaderboard_enabled,
            "web_login_required": rep_settings.web_login_required,
            "ignored_roles": [str(role_id) for role_id in rep_settings.ignored_roles],
            "ignored_channels": [str(channel_id) for channel_id in rep_settings.ignored_channels],
        }
    )
