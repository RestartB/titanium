import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import shortuuid
from sqlalchemy import (
    URL,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, MappedColumn, declarative_base, relationship

Base = declarative_base()


def generate_short_uuid() -> str:
    return shortuuid.ShortUUID().random(length=8)


logger = logging.getLogger("sql")


# -- Tables --
class GuildSettings(Base):
    __tablename__ = "guild_settings"
    guild_id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    loading_reaction: Mapped[bool] = MappedColumn(Boolean, default=True)
    reply_ping: Mapped[bool] = MappedColumn(Boolean, default=True)
    moderation_enabled: Mapped[bool] = MappedColumn(Boolean, default=True)
    moderation_settings: Mapped["GuildModerationSettings"] = relationship(
        "GuildModerationSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )
    automod_enabled: Mapped[bool] = MappedColumn(Boolean, default=True)
    automod_settings: Mapped["GuildAutomodSettings"] = relationship(
        "GuildAutomodSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )
    bouncer_enabled: Mapped[bool] = MappedColumn(Boolean, default=False)
    bouncer_settings: Mapped["GuildBouncerSettings"] = relationship(
        "GuildBouncerSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )
    logging_enabled: Mapped[bool] = MappedColumn(Boolean, default=False)
    logging_settings: Mapped["GuildLoggingSettings"] = relationship(
        "GuildLoggingSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )
    fireboard_enabled: Mapped[bool] = MappedColumn(Boolean, default=False)
    fireboard_settings: Mapped["GuildFireboardSettings"] = relationship(
        "GuildFireboardSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )
    server_counters_enabled: Mapped[bool] = MappedColumn(Boolean, default=False)
    server_counters_settings: Mapped["GuildServerCounterSettings"] = relationship(
        "GuildServerCounterSettings",
        back_populates="guild",
        cascade="all, delete-orphan",
        uselist=False,
    )

    # confession settings
    confession_enabled: Mapped[bool] = MappedColumn(Boolean, default=False)
    confession_settings: Mapped["GuildConfessionSettings"] = relationship(
        "GuildConfessionSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )


class GuildConfessionSettings(Base):
    __tablename__ = "guild_confession_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="confession_settings", uselist=False
    )
    confession_channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    confession_log_channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)


class GuildLimits(Base):
    __tablename__ = "guild_limits"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    BadWordList: Mapped[int] = MappedColumn(Integer, default=10)
    BadWordListSize: Mapped[int] = MappedColumn(Integer, default=1500)
    MessageSpamRules: Mapped[int] = MappedColumn(Integer, default=5)
    MentionSpamRules: Mapped[int] = MappedColumn(Integer, default=5)
    WordSpamRules: Mapped[int] = MappedColumn(Integer, default=5)
    NewLineSpamRules: Mapped[int] = MappedColumn(Integer, default=5)
    LinkSpamRules: Mapped[int] = MappedColumn(Integer, default=5)
    AttachmentSpamRules: Mapped[int] = MappedColumn(Integer, default=5)
    EmojiSpamRules: Mapped[int] = MappedColumn(Integer, default=5)


class GuildPrefixes(Base):
    __tablename__ = "guild_prefixes"
    guild_id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    prefixes: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=5)),
        default=["t!"],
        server_default=text("ARRAY['t!']::varchar[]"),
        nullable=False,
    )


class AvailableWebhook(Base):
    __tablename__ = "available_webhooks"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    guild_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    webhook_url: Mapped[str] = MappedColumn(String, nullable=False)


class GuildModerationSettings(Base):
    __tablename__ = "guild_moderation_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="moderation_settings", uselist=False
    )
    delete_confirmation: Mapped[bool] = MappedColumn(Boolean, default=True)
    dm_users: Mapped[bool] = MappedColumn(Boolean, default=True)
    immune_roles: Mapped[list[int]] = MappedColumn(
        ARRAY(Integer), server_default=text("ARRAY[]::bigint[]")
    )


class GuildAutomodSettings(Base):
    __tablename__ = "guild_automod_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="automod_settings", uselist=False
    )
    badword_detection_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(GuildAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='badword_detection')",
        back_populates="guild",
        cascade="all, delete-orphan",
    )
    spam_detection_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(GuildAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='spam_detection')",
        back_populates="guild",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules",
    )
    malicious_link_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(GuildAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='malicious_link')",
        back_populates="guild",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules,spam_detection_rules",
    )
    phishing_link_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(GuildAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='phishing_link')",
        back_populates="guild",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules,malicious_link_rules,spam_detection_rules",
    )


class AutomodRule(Base):
    __tablename__ = "automod_rules"
    id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_automod_settings.guild_id")
    )
    rule_type: Mapped[str] = MappedColumn(String(length=32))
    antispam_type: Mapped[str] = MappedColumn(String(length=32), nullable=True)
    rule_name: Mapped[str] = MappedColumn(String(length=100), nullable=True)
    words: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=100)), server_default=text("ARRAY[]::varchar[]")
    )
    match_whole_word: Mapped[bool] = MappedColumn(Boolean, default=False)
    case_sensitive: Mapped[bool] = MappedColumn(Boolean, default=False)
    threshold: Mapped[int] = MappedColumn(Integer)  # number of occurrences to trigger
    duration: Mapped[int] = MappedColumn(Integer)  # duration to look for occurrences
    actions: Mapped[list["AutomodAction"]] = relationship(
        "AutomodAction",
        back_populates="rule",
        cascade="all, delete-orphan",
    )
    guild: Mapped["GuildAutomodSettings"] = relationship(
        "GuildAutomodSettings",
        overlaps="badword_detection_rules,spam_detection_rules,malicious_link_rules,phishing_link_rules",
        uselist=False,
    )


class AutomodAction(Base):
    __tablename__ = "automod_actions"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger,
        ForeignKey("guild_automod_settings.guild_id"),
    )
    rule_id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), ForeignKey("automod_rules.id")
    )
    rule_type: Mapped[str] = MappedColumn(String(length=32))
    action_type: Mapped[str] = MappedColumn(String(length=32))
    duration: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    reason: Mapped[str] = MappedColumn(String(length=512), nullable=True)
    rule: Mapped["AutomodRule"] = relationship(
        "AutomodRule", back_populates="actions", uselist=False
    )


class GuildBouncerSettings(Base):
    __tablename__ = "guild_bouncer_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="bouncer_settings", uselist=False
    )
    rules: Mapped[list["BouncerRule"]] = relationship(
        "BouncerRule",
        back_populates="guild",
        cascade="all, delete-orphan",
    )


class BouncerRule(Base):
    __tablename__ = "bouncer_rules"
    id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_bouncer_settings.guild_id")
    )
    rule_name: Mapped[str] = MappedColumn(String(length=100), nullable=True)
    enabled: Mapped[bool] = MappedColumn(Boolean, default=True)
    criteria: Mapped[list["BouncerCriteria"]] = relationship(
        "BouncerCriteria",
        back_populates="rule",
        cascade="all, delete-orphan",
    )
    actions: Mapped[list["BouncerAction"]] = relationship(
        "BouncerAction",
        back_populates="rule",
        cascade="all, delete-orphan",
    )
    guild: Mapped["GuildBouncerSettings"] = relationship(
        "GuildBouncerSettings",
        back_populates="rules",
        uselist=False,
    )


class BouncerCriteria(Base):
    __tablename__ = "bouncer_criteria"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True, autoincrement=True)
    rule_id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), ForeignKey("bouncer_rules.id")
    )
    criteria_type: Mapped[str] = MappedColumn(String(length=32))
    account_age: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    words: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=100)), server_default=text("ARRAY[]::varchar[]")
    )
    match_whole_word: Mapped[bool] = MappedColumn(Boolean, default=False)
    case_sensitive: Mapped[bool] = MappedColumn(Boolean, default=False)
    rule: Mapped["BouncerRule"] = relationship(
        "BouncerRule", back_populates="criteria", uselist=False
    )


class BouncerAction(Base):
    __tablename__ = "bouncer_actions"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True, autoincrement=True)
    rule_id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), ForeignKey("bouncer_rules.id")
    )
    action_type: Mapped[str] = MappedColumn(String(length=32))

    # Actions with duration
    duration: Mapped[int] = MappedColumn(BigInteger, nullable=True)

    # Role actions
    role_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)

    # All actions
    reason: Mapped[str] = MappedColumn(String(length=512), nullable=True)

    # Send message action
    message_content: Mapped[str] = MappedColumn(String(length=2000), nullable=True)
    dm_user: Mapped[bool] = MappedColumn(Boolean, default=False)

    rule: Mapped["BouncerRule"] = relationship(
        "BouncerRule", back_populates="actions", uselist=False
    )


class GuildLoggingSettings(Base):
    __tablename__ = "guild_logging_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="logging_settings", uselist=False
    )
    app_command_perm_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    dc_automod_rule_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    dc_automod_rule_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    dc_automod_rule_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    channel_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    channel_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    channel_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    guild_name_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    guild_afk_channel_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    guild_afk_timeout_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    guild_icon_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    guild_emoji_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    guild_emoji_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    guild_sticker_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    guild_sticker_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    guild_invite_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    guild_invite_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    member_join_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    member_leave_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    member_nickname_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    member_roles_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    member_ban_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    member_unban_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    member_kick_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    member_timeout_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    member_untimeout_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    message_edit_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    message_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    message_bulk_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    poll_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    poll_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    reaction_clear_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    reaction_clear_emoji_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    role_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    role_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    role_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    scheduled_event_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    scheduled_event_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    scheduled_event_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    soundboard_sound_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    soundboard_sound_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    soundboard_sound_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    stage_instance_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    stage_instance_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    stage_instance_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    thread_create_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    thread_update_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    thread_remove_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    thread_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    voice_join_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    voice_leave_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    voice_move_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    voice_mute_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    voice_unmute_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    voice_deafen_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    voice_undeafen_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    titanium_warn_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    titanium_mute_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    titanium_unmute_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    titanium_kick_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    titanium_ban_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    titanium_unban_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    titanium_case_delete_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    titanium_case_comment_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    titanium_automod_trigger_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)


class GuildFireboardSettings(Base):
    __tablename__ = "guild_fireboard_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="fireboard_settings", uselist=False
    )
    global_ignored_channels: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    global_ignored_roles: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    fireboard_boards: Mapped[list["FireboardBoard"]] = relationship(
        "FireboardBoard", back_populates="guild", cascade="all, delete-orphan"
    )


class FireboardBoard(Base):
    __tablename__ = "fireboard_boards"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_fireboard_settings.guild_id")
    )
    guild: Mapped["GuildFireboardSettings"] = relationship(
        "GuildFireboardSettings", back_populates="fireboard_boards", uselist=False
    )
    channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    reaction: Mapped[str] = MappedColumn(String(), default="🔥")
    threshold: Mapped[int] = MappedColumn(Integer, default=5)
    ignore_bots: Mapped[bool] = MappedColumn(Boolean, default=True)
    ignore_self_reactions: Mapped[bool] = MappedColumn(Boolean, default=True)
    ignored_roles: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    ignored_channels: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    messages: Mapped[list["FireboardMessage"]] = relationship(
        "FireboardMessage", back_populates="fireboard", cascade="all, delete-orphan"
    )


class FireboardMessage(Base):
    __tablename__ = "fireboard_messages"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    guild_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    message_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    fireboard_message_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    fireboard_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("fireboard_boards.id")
    )
    fireboard: Mapped["FireboardBoard"] = relationship(
        "FireboardBoard", back_populates="messages", uselist=False
    )


class GuildServerCounterSettings(Base):
    __tablename__ = "guild_server_counter_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id"), primary_key=True
    )
    guild: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="server_counters_settings", uselist=False
    )
    channels: Mapped[list["ServerCounterChannel"]] = relationship(
        "ServerCounterChannel", back_populates="settings", cascade="all, delete-orphan"
    )


class ServerCounterChannel(Base):
    __tablename__ = "server_counter_channels"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger,
        ForeignKey("guild_server_counter_settings.guild_id"),
    )
    settings: Mapped["GuildServerCounterSettings"] = relationship(
        "GuildServerCounterSettings", back_populates="channels", uselist=False
    )
    count_type: Mapped[str] = MappedColumn(String(length=32))
    name: Mapped[str] = MappedColumn(String(length=50), default="{value}")


class ModCase(Base):
    __tablename__ = "mod_cases"
    id: Mapped[str] = MappedColumn(
        String(length=8), primary_key=True, default=generate_short_uuid
    )
    type: Mapped[str] = MappedColumn(String(length=32))
    guild_id: Mapped[int] = MappedColumn(BigInteger)
    user_id: Mapped[int] = MappedColumn(BigInteger)
    creator_user_id: Mapped[int] = MappedColumn(BigInteger)
    proof_msg_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    proof_channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    proof_text: Mapped[str] = MappedColumn(String, nullable=True)
    time_created: Mapped[datetime] = MappedColumn(DateTime)
    time_updated: Mapped[datetime] = MappedColumn(DateTime, nullable=True)
    time_expires: Mapped[datetime] = MappedColumn(DateTime, nullable=True)
    description: Mapped[str] = MappedColumn(String(length=512), nullable=True)
    external: Mapped[bool] = MappedColumn(Boolean, default=False)
    resolved: Mapped[bool] = MappedColumn(Boolean, default=False)
    comments: Mapped[list["ModCaseComment"]] = relationship(
        "ModCaseComment", back_populates="case", cascade="all, delete-orphan"
    )
    scheduled_tasks: Mapped[list["ScheduledTask"]] = relationship(
        "ScheduledTask", back_populates="case", cascade="all, delete-orphan"
    )


class ModCaseComment(Base):
    __tablename__ = "mod_case_comments"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    guild_id: Mapped[int] = MappedColumn(BigInteger)
    case_id: Mapped[str] = MappedColumn(String(length=8), ForeignKey("mod_cases.id"))
    user_id: Mapped[int] = MappedColumn(BigInteger)
    comment: Mapped[str] = MappedColumn(String(length=512))
    time_created: Mapped[datetime] = MappedColumn(DateTime)
    case: Mapped["ModCase"] = relationship(
        "ModCase", back_populates="comments", uselist=False
    )


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    type: Mapped[str] = MappedColumn(String)
    guild_id: Mapped[int] = MappedColumn(BigInteger)
    user_id: Mapped[int] = MappedColumn(BigInteger)
    channel_id: Mapped[int] = MappedColumn(BigInteger)
    role_id: Mapped[int] = MappedColumn(BigInteger)
    message_id: Mapped[int] = MappedColumn(BigInteger)
    case_id: Mapped[str] = MappedColumn(
        String(length=8), ForeignKey("mod_cases.id"), nullable=True
    )
    duration: Mapped[int] = MappedColumn(
        BigInteger, nullable=True
    )  # for refresh_mute - how long we need to extend mute by
    case: Mapped["ModCase"] = relationship(
        "ModCase", back_populates="scheduled_tasks", uselist=False
    )
    time_scheduled: Mapped[datetime] = MappedColumn(DateTime)


# Game stats
class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = MappedColumn(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = MappedColumn(String(50), unique=True, nullable=False)
    # games like -> dice, coin_flip, chess, rps (rock, paper, ..)


class GameStat(Base):
    __tablename__ = "game_stats"

    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    game_id: Mapped[int] = MappedColumn(ForeignKey("games.id"), nullable=False)
    played: Mapped[int] = MappedColumn(Integer, default=0)
    win: Mapped[int] = MappedColumn(Integer, default=0)

    game = relationship("Game")

    # __table_args__ = (UniqueConstraint("user_id", "game_id", name="uq_user_game"),)


SQLALCHEMY_DATABASE_URL = URL.create(
    "postgresql+asyncpg",
    username=os.getenv("DB_USERNAME", ""),
    password=os.getenv("DB_PASSWORD", ""),
    host=os.getenv("DB_HOST", ""),
    port=int(os.getenv("DB_PORT", 0)),
    database=os.getenv("DB_DATABASE_NAME", ""),
)

logger.info(f"Connecting to database at {SQLALCHEMY_DATABASE_URL}, password is hidden")

# -- Engine --
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
)

# Create session maker
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    try:
        logger.info("Applying database migrations...")
        result = await asyncio.create_subprocess_exec(
            "atlas",
            "migrate",
            "apply",
            "--env",
            "sqlalchemy",
            "--url",
            str(
                SQLALCHEMY_DATABASE_URL.render_as_string(hide_password=False).replace(
                    "postgresql+asyncpg", "postgresql"
                )
                + "?search_path=public&sslmode=disable"
            ),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if await result.wait() != 0:
            raise Exception("Database migration failed")

        logger.info("Database migrations applied successfully")

        if result.stdout:
            stdout_text = (await result.stdout.read()).decode().strip()
            if stdout_text:
                logger.info(f"stdout: {stdout_text}")

        if result.stderr:
            stderr_text = (await result.stderr.read()).decode().strip()
            if stderr_text:
                logger.info(f"stderr: {stderr_text}")
    except Exception:
        logger.error("Error applying database migrations:")

        if result.stdout:
            stdout_text = (await result.stdout.read()).decode().strip()
            if stdout_text:
                logger.error(f"stdout: {stdout_text}")

        if result.stderr:
            stderr_text = (await result.stderr.read()).decode().strip()
            if stderr_text:
                logger.error(f"stderr: {stderr_text}")

        raise


@asynccontextmanager
async def get_session():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
