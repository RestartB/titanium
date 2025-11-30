import uuid
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from lib.enums.automod import AutomodActionType, AutomodAntispamType, AutomodRuleType
from lib.enums.bouncer import BouncerActionType, BouncerCriteriaType
from lib.enums.leaderboard import LeaderboardCalcType
from lib.enums.server_counters import ServerCounterType
from lib.sql.sql import (
    AutomodAction,
    AutomodRule,
    BouncerAction,
    BouncerCriteria,
    BouncerRule,
    GuildLeaderboardSettings,
    LeaderboardLevels,
)


class ModuleModel(BaseModel):
    moderation: bool
    automod: bool
    bouncer: bool
    logging: bool
    fireboard: bool
    server_counters: bool
    confessions: bool
    leaderboard: bool


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

        if len(v) != len(set(v)):
            raise ValueError("Prefixes must be unique")

        return v


class GuildPermissionsModel(BaseModel):
    dashboard_managers: list[str] = Field(default_factory=list)
    case_managers: list[str] = Field(default_factory=list)


class ConfessionsConfigModel(BaseModel):
    confessions_in_channel: bool
    confessions_channel_id: Optional[str] = None


class ModerationConfigModel(BaseModel):
    delete_confirmation: bool
    dm_users: bool
    external_cases: bool
    external_case_dms: bool


class AutomodActionModel(BaseModel):
    type: AutomodActionType
    duration: Optional[int] = None
    reason: Optional[str] = None
    role_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_mute_duration(self):
        if self.type == "mute" and (self.duration is None or self.duration <= 0):
            raise ValueError("Mute actions must have a positive duration")
        return self

    def to_sqlalchemy(self, rule_type: AutomodRuleType, guild_id: int) -> AutomodAction:
        return AutomodAction(
            guild_id=guild_id,
            rule_type=rule_type,
            action_type=self.type,
            duration=self.duration,
            reason=self.reason,
            role_id=self.role_id,
        )


class AutomodRuleModel(BaseModel):
    id: Optional[str] = None
    rule_type: AutomodRuleType
    rule_name: str = ""
    words: Optional[list[str]] = Field(default_factory=list)
    match_whole_word: bool = False
    case_sensitive: bool = False
    antispam_type: Optional[AutomodAntispamType] = None
    threshold: int
    duration: int
    actions: list[AutomodActionModel]

    @field_validator("id")
    def validate_id(cls, v):
        if v == "":
            return None
        return v

    @model_validator(mode="after")
    def validate_unique_action_types(self):
        action_types = [action.type for action in self.actions]

        if len(action_types) != len(set(action_types)):
            raise ValueError("Each action type in a rule must be unique")

        return self

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
    badword_detection: list["AutomodRuleModel"]
    spam_detection: list["AutomodRuleModel"]
    malicious_link_detection: list["AutomodRuleModel"]
    phishing_link_detection: list["AutomodRuleModel"]


class BouncerCriterionModel(BaseModel):
    type: BouncerCriteriaType
    account_age: Optional[int] = None
    words: Optional[list[str]] = None
    match_whole_word: bool = False
    case_sensitive: bool = False


class BouncerActionModel(BaseModel):
    type: BouncerActionType
    duration: Optional[int] = None
    role_id: Optional[str] = None
    reason: Optional[str] = None
    message_content: Optional[str] = None
    dm_user: Optional[bool] = None


class BouncerRuleModel(BaseModel):
    id: str
    enabled: bool
    criteria: list[BouncerCriterionModel]
    actions: list[BouncerActionModel]

    @model_validator(mode="after")
    def validate_unique_criteria_types(self):
        criteria_types = [criterion.type for criterion in self.criteria]

        if len(criteria_types) != len(set(criteria_types)):
            raise ValueError("Each criterion type in a rule must be unique")

        return self

    @model_validator(mode="after")
    def validate_unique_action_types(self):
        action_types = [action.type for action in self.actions]

        if len(action_types) != len(set(action_types)):
            raise ValueError("Each action type in a rule must be unique")

        return self

    def to_sqlalchemy(self, guild_id: int) -> BouncerRule:
        rule = BouncerRule(
            id=uuid.UUID(self.id),
            guild_id=guild_id,
            enabled=True,
        )

        for criterion_model in self.criteria:
            criterion = BouncerCriteria(
                guild_id=guild_id,
                rule_id=rule.id,
                criterion_type=criterion_model.type,
                account_age=criterion_model.account_age,
                words=criterion_model.words or [],
                match_whole_word=criterion_model.match_whole_word,
                case_sensitive=criterion_model.case_sensitive,
            )
            rule.criteria.append(criterion)

        for action_model in self.actions:
            action = BouncerAction(
                guild_id=guild_id,
                rule_id=rule.id,
                action_type=action_model.type,
                duration=action_model.duration,
                role_id=action_model.role_id,
                reason=action_model.reason,
                message_content=action_model.message_content,
                dm_user=action_model.dm_user,
            )
            rule.actions.append(action)

        return rule


class BouncerConfigModel(BaseModel):
    rules: list[BouncerRuleModel]


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
    id: Optional[uuid.UUID] = None
    channel_id: str
    reaction: str
    threshold: int
    ignore_bots: bool
    ignore_self_reactions: bool
    ignored_roles: list[str] = Field(default_factory=list)
    ignored_channels: list[str] = Field(default_factory=list)


class FireboardConfigModel(BaseModel):
    global_ignored_roles: list[str] = Field(default_factory=list)
    global_ignored_channels: list[str] = Field(default_factory=list)
    boards: list[FireboardBoardModel] = Field(default_factory=list)


class ServerCounterChannelModel(BaseModel):
    id: Optional[str] = None
    name: str
    type: ServerCounterType
    activity_name: Optional[str] = None

    @field_validator("id")
    def validate_id(cls, v: str):
        if v.strip() == "":
            return None
        return v


class ServerCountersConfigModel(BaseModel):
    channels: list[ServerCounterChannelModel] = Field(default_factory=list)


class LeaderboardLevelModel(BaseModel):
    xp_required: int
    reward_roles: list[str] = Field(default_factory=list)


class LeaderboardConfigModel(BaseModel):
    mode: LeaderboardCalcType
    cooldown: int
    base_xp: Optional[int] = None
    min_xp: Optional[int] = None
    max_xp: Optional[int] = None
    xp_mult: Optional[float] = None
    levelup_notifications: bool
    notification_channel: Optional[str] = None
    web_leaderboard_enabled: bool
    web_login_required: bool
    delete_leavers: bool
    levels: list[LeaderboardLevelModel] = Field(default_factory=list)

    def to_sqlalchemy(self, guild_id: int) -> GuildLeaderboardSettings:
        return GuildLeaderboardSettings(
            guild_id=guild_id,
            mode=self.mode,
            cooldown=self.cooldown,
            base_xp=self.base_xp,
            min_xp=self.min_xp,
            max_xp=self.max_xp,
            xp_mult=self.xp_mult,
            levelup_notifications=self.levelup_notifications,
            notification_channel=self.notification_channel,
            web_leaderboard_enabled=self.web_leaderboard_enabled,
            web_login_required=self.web_login_required,
            delete_leavers=self.delete_leavers,
            levels=[
                LeaderboardLevels(
                    xp=level.xp_required,
                    reward_roles=[int(role) for role in level.reward_roles],
                )
                for level in self.levels
            ],
        )
