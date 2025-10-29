import uuid
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from lib.sql.sql import AutomodAction, AutomodRule


class ModuleModel(BaseModel):
    moderation: bool
    automod: bool
    bouncer: bool
    logging: bool
    fireboard: bool
    server_counters: bool
    confession: bool


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


class ConfessionConfigModel(BaseModel):
    confession_channel_id: Optional[str] = None
    confession_log_channel_id: Optional[str] = None


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
    words: Optional[list[str]] = Field(default_factory=list)
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


class BouncerCriterionModel(BaseModel):
    type: str
    account_age: Optional[int] = None
    words: Optional[list[str]] = None
    match_whole_word: Optional[bool] = None
    case_sensitive: Optional[bool] = None


class BouncerActionModel(BaseModel):
    type: str
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
    id: Optional[str] = None
    channel_id: str
    reaction: str
    threshold: int
    ignore_bots: bool
    ignore_self_reactions: bool
    ignored_roles: list[str] = Field(default_factory=list)
    ignored_channels: list[str] = Field(default_factory=list)

    @field_validator("id")
    def validate_id(cls, v: str):
        if v.strip() == "":
            return None
        return v


class FireboardConfigModel(BaseModel):
    global_ignored_roles: list[str] = Field(default_factory=list)
    global_ignored_channels: list[str] = Field(default_factory=list)
    boards: list[FireboardBoardModel] = Field(default_factory=list)


class ServerCounterChannelModel(BaseModel):
    id: Optional[str] = None
    name: str
    type: str
    activity_name: Optional[str] = None

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
            "activity",
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
    channels: list[ServerCounterChannelModel] = Field(default_factory=list)
