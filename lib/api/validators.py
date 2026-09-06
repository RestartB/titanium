import re
import uuid
from typing import Annotated

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


def validate_id(id: str) -> bool:
    return re.fullmatch(r"\d{15,20}", id) is not None


DiscordId = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9]{15,20}$"),
]


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
    blocked_channels: list[DiscordId] = Field(default_factory=list, max_length=100)
    blocked_roles: list[DiscordId] = Field(default_factory=list, max_length=100)
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
    dashboard_managers: list[DiscordId] = Field(default_factory=list, max_length=100)
    case_managers: list[DiscordId] = Field(default_factory=list, max_length=100)


class ConfessionsConfigModel(BaseModel):
    confessions_in_channel: bool
    confessions_channel_id: DiscordId | None = None
    polls_enabled: bool
    attachments_allowed: bool


class ModerationConfigModel(BaseModel):
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

    threshold: int | None = Field(None, ge=1, le=1_892_160_000)
    duration: int | None = Field(None, ge=1, le=1_892_160_000)

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

    duration: int | None = Field(None, ge=1, le=1_892_160_000)
    reason: Annotated[str, StringConstraints(max_length=512, strip_whitespace=True)] | None = None

    role_ids: list[DiscordId] = Field(default_factory=list, max_length=10)

    reaction: str | None = None

    message_content: (
        Annotated[str, StringConstraints(max_length=1024, strip_whitespace=True)] | None
    ) = None
    message_reply: bool
    message_mention: bool
    message_embed: bool
    # FIXME: validate hex code
    embed_colour: Annotated[str, StringConstraints(max_length=7, strip_whitespace=True)] | None = (
        None
    )

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
        if self.type == AutomodActionType.SEND_MESSAGE and (
            not self.message_content or self.message_content.strip() == ""
        ):
            raise ValueError("Message content must be provided for send message action")
        return self

    @model_validator(mode="after")
    def validate_reaction(self):
        if self.type != AutomodActionType.REACTION:
            return self

        if not self.reaction or self.reaction.strip() == "":
            raise ValueError("Reaction cannot be empty")

        if self.reaction.isdigit():
            if not validate_id(self.reaction):
                raise ValueError(f"Invalid emoji ID - {self.reaction}")
        else:
            if not is_emoji(self.reaction):
                raise ValueError(f"Invalid emoji or emoji ID - {self.reaction}")

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
            reaction=self.reaction,
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

    global_ignored_roles: list[DiscordId] = Field(default_factory=list, max_length=100)
    global_ignored_channels: list[DiscordId] = Field(default_factory=list, max_length=100)


class BouncerCriterionModel(BaseModel):
    type: BouncerCriteriaType

    account_age: int | None = Field(None, ge=1, le=1_892_160_000)

    words: list[
        Annotated[
            str,
            StringConstraints(min_length=1, max_length=100),
        ]
    ] = Field(default_factory=list)
    match_whole_word: bool
    match_all_words: bool
    case_sensitive: bool

    def to_sqlalchemy(self) -> BouncerCriteria:
        return BouncerCriteria(
            type=self.type,
            account_age=self.account_age,
            words=self.words,
            match_whole_word=self.match_whole_word,
            match_all_words=self.match_all_words,
            case_sensitive=self.case_sensitive,
        )


class BouncerActionModel(BaseModel):
    type: BouncerActionType

    duration: int | None = Field(None, ge=1, le=1_892_160_000)
    reason: Annotated[str, StringConstraints(max_length=512, strip_whitespace=True)] | None = None

    role_ids: list[DiscordId] = Field(default_factory=list, max_length=10)

    def to_sqlalchemy(self) -> BouncerAction:
        return BouncerAction(
            type=self.type,
            duration=self.duration,
            reason=self.reason,
            role_ids=[int(role_id) for role_id in (self.role_ids or [])],
        )


class BouncerRuleModel(BaseModel):
    rule_name: Annotated[str, StringConstraints(max_length=100, strip_whitespace=True)] = ""
    enabled: bool
    match_all_criteria: bool

    order: int
    stop_if_triggered: bool

    member_join: bool
    member_update: bool
    suspicious_reaction: bool

    criteria: list[BouncerCriterionModel]
    actions: list[BouncerActionModel]

    @model_validator(mode="after")
    def validate_triggers(self):
        if not self.member_join and not self.member_update and not self.suspicious_reaction:
            raise ValueError("At least 1 trigger must be selected")

        if (self.member_join or self.member_update) and len(self.criteria) == 0:
            raise ValueError("Member join / update triggers require at least 1 criteria")

        return self

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
            rule_name=self.rule_name,
            enabled=self.enabled,
            match_all_criteria=self.match_all_criteria,
            order=self.order,
            stop_if_triggered=self.stop_if_triggered,
            member_join=self.member_join,
            member_update=self.member_update,
            suspicious_reaction=self.suspicious_reaction,
            criteria=[criteria.to_sqlalchemy() for criteria in self.criteria],
            actions=[action.to_sqlalchemy() for action in self.actions],
        )

        return rule


class BouncerConfigModel(BaseModel):
    rules: list[BouncerRuleModel]


class LoggingConfigModel(BaseModel):
    channels: dict[str, str | None] = Field(default_factory=dict, max_length=120)

    ignored_creator_role_ids: list[DiscordId] = Field(default_factory=list, max_length=100)
    ignored_creator_user_ids: list[DiscordId] = Field(default_factory=list, max_length=100)
    ignored_target_role_ids: list[DiscordId] = Field(default_factory=list, max_length=100)
    ignored_target_user_ids: list[DiscordId] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_keys(self):
        seen_keys: list[str] = []
        for key in self.channels:
            if key in seen_keys:
                raise ValueError(f"Duplicate event type: {key}")
            seen_keys.append(key)

        return self


class FireboardBoardModel(BaseModel):
    id: uuid.UUID | None = None

    channel_id: DiscordId
    reaction: str
    threshold: int

    ignore_bots: bool
    ignore_self_reactions: bool
    send_notifications: bool

    ignored_roles: list[DiscordId] = Field(default_factory=list, max_length=100)
    ignored_channels: list[DiscordId] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_reaction(self):
        if self.reaction.strip() == "":
            raise ValueError("Reaction cannot be empty")

        if self.reaction.isdigit():
            if not validate_id(self.reaction):
                raise ValueError(f"Invalid emoji ID - {self.reaction}")
        else:
            if not is_emoji(self.reaction):
                raise ValueError(f"Invalid emoji or emoji ID - {self.reaction}")

        return self


class FireboardConfigModel(BaseModel):
    global_ignored_roles: list[DiscordId] = Field(default_factory=list, max_length=100)
    global_ignored_channels: list[DiscordId] = Field(default_factory=list, max_length=100)
    boards: list[FireboardBoardModel] = Field(default_factory=list)


# FIXME: to be honest i have no idea how the ID works here
# i will need to pick this up when i redo the update module endpoints
class ServerCounterChannelModel(BaseModel):
    id: str | None = None
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
    reward_roles: list[DiscordId] = Field(default_factory=list, max_length=5)


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

    ignored_roles: list[DiscordId] = Field(default_factory=list, max_length=100)
    ignored_channels: list[DiscordId] = Field(default_factory=list, max_length=100)

    bot_message_tracking: bool
    bot_message_xp: bool
    bot_vc_tracking: bool
    bot_vc_xp: bool

    levelup_notifications: bool
    notification_ping: bool
    notification_channel: DiscordId | None = None

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
    user: DiscordId


class RepConfigModel(BaseModel):
    rep_hint: bool
    allow_rep_remove: bool
    delete_leavers: bool

    web_leaderboard_enabled: bool
    web_login_required: bool

    ignored_roles: list[DiscordId] = Field(default_factory=list, max_length=100)
    ignored_channels: list[DiscordId] = Field(default_factory=list, max_length=100)
