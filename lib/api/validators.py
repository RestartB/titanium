import uuid
from typing import Annotated, Optional

from emoji import is_emoji
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from lib.enums.automod import AutomodActionType, AutomodCriteriaType
from lib.enums.bouncer import BouncerActionType, BouncerCriteriaType
from lib.enums.leaderboard import LeaderboardCalcType, LeaderboardVcCalcType
from lib.enums.server_counters import ServerCounterType
from lib.sql.sql import (
    AutomodAction,
    AutomodCriteria,
    AutomodRule,
    BouncerAction,
    BouncerCriteria,
    BouncerRule,
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
    tags: bool
    rep: bool


class SettingsModel(BaseModel):
    allow_prefix: bool
    send_not_allowed: bool
    loading_reaction: bool
    blocked_channels: list[str] = Field(default_factory=list, max_length=100)
    blocked_roles: list[str] = Field(default_factory=list, max_length=100)
    delete_after_3_days: bool


class GuildSettingsModel(BaseModel):
    modules: ModuleModel
    settings: SettingsModel
    prefixes: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("prefixes")
    def validate_prefixes(cls, v):
        for prefix in v:
            if not (1 <= len(prefix) <= 5):
                raise ValueError("Each prefix must be between 1 and 5 characters long")

        if len(v) != len(set(v)):
            raise ValueError("Prefixes must be unique")

        return v


class GuildPermissionsModel(BaseModel):
    dashboard_managers: list[str] = Field(default_factory=list, max_length=100)
    case_managers: list[str] = Field(default_factory=list, max_length=100)


class ConfessionsConfigModel(BaseModel):
    confessions_in_channel: bool
    confessions_channel_id: Optional[str] = None
    polls_enabled: bool
    attachments_allowed: bool


class ModerationConfigModel(BaseModel):
    delete_confirmation: bool
    dm_users: bool
    external_cases: bool
    ban_days: int = Field(0, ge=0, le=7)


class CaseComment(BaseModel):
    user: str
    content: Annotated[
        str,
        StringConstraints(min_length=1, max_length=500, strip_whitespace=True),
    ]


class AutomodCriteriaModel(BaseModel):
    type: AutomodCriteriaType

    threshold: Optional[int] = Field(None, ge=1, le=1_892_160_000)
    duration: Optional[int] = Field(None, ge=1, le=1_892_160_000)

    words: list[
        Annotated[
            str,
            StringConstraints(min_length=1, max_length=100),
        ]
    ] = Field(default_factory=list)
    match_whole_word: bool
    match_all_words: bool
    case_sensitive: bool

    @model_validator(mode="after")
    def validate_spam(self):
        if self.type.value.endswith("_spam") and (self.threshold is None or self.duration is None):
            raise ValueError("Threshold and duration must be provided for spam filters")
        return self

    def to_sqlalchemy(self) -> AutomodCriteria:
        return AutomodCriteria(
            type=self.type,
            threshold=self.threshold,
            duration=self.duration,
            words=self.words,
            match_whole_word=self.match_whole_word,
            match_all_words=self.match_all_words,
            case_sensitive=self.case_sensitive,
        )


class AutomodActionModel(BaseModel):
    type: AutomodActionType

    duration: Optional[int] = Field(None, ge=1, le=1_892_160_000)
    reason: Optional[
        Annotated[
            str,
            StringConstraints(max_length=512, strip_whitespace=True),
        ]
    ] = None

    role_ids: list[str] = Field(default_factory=list, max_length=10)

    message_content: Optional[
        Annotated[
            str,
            StringConstraints(max_length=1024, strip_whitespace=True),
        ]
    ] = None
    message_reply: bool
    message_mention: bool
    message_embed: bool
    # TODO: validate hex code
    embed_colour: Optional[
        Annotated[
            str,
            StringConstraints(max_length=7, strip_whitespace=True),
        ]
    ] = None

    @model_validator(mode="after")
    def validate_role_present(self):
        if (
            self.type
            in {
                AutomodActionType.ADD_ROLE,
                AutomodActionType.REMOVE_ROLE,
                AutomodActionType.TOGGLE_ROLE,
            }
            and not self.role_ids
        ):
            raise ValueError("Role IDs must be provided for role actions")
        return self

    @model_validator(mode="after")
    def validate_message_content(self):
        if self.type == AutomodActionType.SEND_MESSAGE:
            if not self.message_content or self.message_content.strip() == "":
                raise ValueError("Message content must be provided for send message action")
        return self

    @model_validator(mode="after")
    def validate_role_ids(self):
        if not self.role_ids:
            return self

        valid_role_ids: list[str] = []
        for role_id in self.role_ids:
            if not role_id:
                raise ValueError(f"Invalid role id: {role_id}")

            try:
                int(role_id)
                valid_role_ids.append(role_id)
            except Exception:
                raise ValueError(f"Invalid role id: {role_id}")

        self.role_ids = valid_role_ids
        return self

    def to_sqlalchemy(self) -> AutomodAction:
        return AutomodAction(
            type=self.type,
            duration=self.duration,
            reason=self.reason,
            message_content=self.message_content,
            message_reply=self.message_reply,
            message_mention=self.message_mention,
            message_embed=self.message_embed,
            embed_colour=self.embed_colour,
            role_ids=[int(role_id) for role_id in (self.role_ids or [])],
        )


class AutomodRuleModel(BaseModel):
    rule_name: Annotated[str, StringConstraints(max_length=100, strip_whitespace=True)] = ""

    enabled: bool
    evaluate_edits: bool
    match_all_criteria: bool

    order: int
    stop_if_triggered: bool

    criteria: list[AutomodCriteriaModel]
    actions: list[AutomodActionModel]

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

    def to_sqlalchemy(self, guild_id: int) -> AutomodRule:
        rule = AutomodRule(
            guild_id=guild_id,
            rule_name=self.rule_name,
            enabled=self.enabled,
            evaluate_edits=self.evaluate_edits,
            match_all_criteria=self.match_all_criteria,
            order=self.order,
            stop_if_triggered=self.stop_if_triggered,
            criteria=[criteria.to_sqlalchemy() for criteria in self.criteria],
            actions=[action.to_sqlalchemy() for action in self.actions],
        )

        return rule


class AutomodConfigModel(BaseModel):
    rules: list[AutomodRuleModel]
    show_outcome_message: bool


class BouncerCriterionModel(BaseModel):
    type: BouncerCriteriaType

    account_age: Optional[int] = Field(None, ge=1, le=1_892_160_000)

    words: Optional[list[str]] = None
    match_whole_word: bool = False
    case_sensitive: bool = False

    def to_sqlalchemy(self, rule_id: uuid.UUID) -> BouncerCriteria:
        return BouncerCriteria(
            rule_id=rule_id,
            type=self.type,
            account_age=self.account_age,
            words=self.words or [],
            match_whole_word=self.match_whole_word,
            case_sensitive=self.case_sensitive,
        )


class BouncerActionModel(BaseModel):
    type: BouncerActionType

    duration: Optional[int] = Field(None, ge=1, le=1_892_160_000)
    reason: Optional[str] = None

    role_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_role_present(self):
        if (
            self.type
            in {
                BouncerActionType.ADD_ROLE,
                BouncerActionType.REMOVE_ROLE,
                BouncerActionType.TOGGLE_ROLE,
            }
            and not self.role_id
        ):
            raise ValueError("Role ID must be provided for role action")
        return self

    @model_validator(mode="after")
    def validate_role_id(self):
        if not self.role_id:
            return self

        try:
            int(self.role_id)
        except Exception:
            raise ValueError("Invalid role ID")

        return self

    def to_sqlalchemy(self, rule_id: uuid.UUID) -> BouncerAction:
        return BouncerAction(
            rule_id=rule_id,
            type=self.type,
            duration=self.duration,
            role_id=int(self.role_id) if self.role_id else None,
            reason=self.reason,
        )


class BouncerRuleModel(BaseModel):
    enabled: bool
    evaluate_for_existing_members: bool

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
            guild_id=guild_id,
            enabled=True,
        )

        for criterion_model in self.criteria:
            rule.criteria.append(criterion_model.to_sqlalchemy(rule.id))

        for action_model in self.actions:
            rule.actions.append(action_model.to_sqlalchemy(rule.id))

        return rule


class BouncerConfigModel(BaseModel):
    rules: list[BouncerRuleModel]


class LoggingConfigModel(BaseModel):
    channels: dict[str, Optional[str]] = Field(default_factory=dict, max_length=120)

    @model_validator(mode="after")
    def validate_keys(self):
        seen_keys: list[str] = []
        for key in self.channels.keys():
            if key in seen_keys:
                raise ValueError(f"Duplicate event type: {key}")
            seen_keys.append(key)

        return self


class FireboardBoardModel(BaseModel):
    id: Optional[uuid.UUID] = None

    channel_id: str
    reaction: str
    threshold: int

    ignore_bots: bool
    ignore_self_reactions: bool
    send_notifications: bool

    ignored_roles: list[str] = Field(default_factory=list)
    ignored_channels: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_reaction(self):
        if self.reaction.strip() == "":
            raise ValueError("Reaction cannot be empty")

        if self.reaction.isdigit():
            reaction_id = int(self.reaction)
            if reaction_id <= 0:
                raise ValueError("Emoji ID must be a positive integer")
        else:
            if not is_emoji(self.reaction):
                raise ValueError("Emoji must be valid or a positive integer ID")

        return self


class FireboardConfigModel(BaseModel):
    global_ignored_roles: list[str] = Field(default_factory=list)
    global_ignored_channels: list[str] = Field(default_factory=list)
    boards: list[FireboardBoardModel] = Field(default_factory=list)


class ServerCounterChannelModel(BaseModel):
    id: Optional[str] = None
    name: str
    type: ServerCounterType

    @field_validator("id")
    def validate_id(cls, v: str):
        if not v or v.strip() == "":
            return None
        return v


class ServerCountersConfigModel(BaseModel):
    channels: list[ServerCounterChannelModel] = Field(default_factory=list)


class LeaderboardLevelModel(BaseModel):
    xp_required: int
    reward_roles: list[str] = Field(default_factory=list, max_length=5)


class LeaderboardConfigModel(BaseModel):
    mode: LeaderboardCalcType
    delete_leavers: bool
    stack_roles: bool

    cooldown: int
    base_xp: int = 10
    min_xp: int = 15
    max_xp: int = 25
    xp_mult: float = 1.0

    vc_enabled: bool
    vc_mode: LeaderboardVcCalcType
    vc_delay: int = Field(5, ge=0, le=1440)
    vc_base_xp: int = 10
    vc_min_xp: int = 15
    vc_max_xp: int = 25

    ignored_roles: list[str] = Field(default_factory=list, max_length=100)
    ignored_channels: list[str] = Field(default_factory=list, max_length=100)

    levelup_notifications: bool
    notification_ping: bool
    notification_channel: Optional[str] = None

    web_leaderboard_enabled: bool
    web_login_required: bool

    levels: list[LeaderboardLevelModel] = Field(default_factory=list)


class TagsConfigModel(BaseModel):
    allow_user_tags: bool
    prefix_fallback: bool


class TagModel(BaseModel):
    name: Annotated[
        str,
        StringConstraints(
            min_length=1, max_length=35, to_lower=True, ascii_only=True, strip_whitespace=True
        ),
    ]
    content: Annotated[str, StringConstraints(min_length=1, max_length=2000, strip_whitespace=True)]
    user: str

    @field_validator("user")
    def validate_user(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("User must be a numeric string ID")

        return v


class RepConfigModel(BaseModel):
    rep_hint: bool
    allow_rep_remove: bool
    delete_leavers: bool

    web_leaderboard_enabled: bool
    web_login_required: bool

    ignored_roles: list[str] = Field(default_factory=list, max_length=100)
    ignored_channels: list[str] = Field(default_factory=list, max_length=100)
