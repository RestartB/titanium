import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

import shortuuid
from discord import Guild, Member, PartialInviteGuild
from dotenv import load_dotenv
from sqlalchemy import (
    URL,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    desc,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import (
    Mapped,
    MappedColumn,
    configure_mappers,
    declarative_base,
    relationship,
    selectinload,
)

from lib.enums.automod import AutomodActionType, AutomodCriteriaType
from lib.enums.bouncer import BouncerActionType, BouncerCriteriaType
from lib.enums.games import GameTypes
from lib.enums.leaderboard import LeaderboardCalcType, LeaderboardVcCalcType
from lib.enums.moderation import CaseType
from lib.enums.scheduled_events import EventType
from lib.enums.server_counters import ServerCounterType

if TYPE_CHECKING:
    from main import TitaniumBot


Base = declarative_base()
logger = logging.getLogger("sql")


def generate_short_uuid() -> str:
    return shortuuid.ShortUUID().random(length=8)


# -- Tables --
class GuildSettings(Base):
    __tablename__ = "guild_settings"
    guild_id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)

    allow_prefix: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    send_not_allowed: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    loading_reaction: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    blocked_channels: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    blocked_roles: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )

    delete_after_3_days: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    leave_date: Mapped[datetime | None] = MappedColumn(DateTime(timezone=True), nullable=True)

    dashboard_managers: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    case_managers: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )

    limits: Mapped["GuildLimits"] = relationship(
        "GuildLimits",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="guild_settings",
        uselist=False,
    )
    prefixes: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=5)),
        default=["t!"],
        server_default=text("ARRAY['t!']::varchar[]"),
        nullable=False,
    )

    moderation_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    moderation_settings: Mapped["GuildModerationSettings | None"] = relationship(
        "GuildModerationSettings",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="guild_settings",
        uselist=False,
    )

    automod_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    automod_settings: Mapped["GuildAutomodSettings | None"] = relationship(
        "GuildAutomodSettings",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="guild_settings",
        uselist=False,
    )

    bouncer_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    bouncer_settings: Mapped["GuildBouncerSettings | None"] = relationship(
        "GuildBouncerSettings",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="guild_settings",
        uselist=False,
    )

    logging_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    logging_settings: Mapped["GuildLoggingSettings | None"] = relationship(
        "GuildLoggingSettings",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="guild_settings",
        uselist=False,
    )

    fireboard_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    fireboard_settings: Mapped["GuildFireboardSettings | None"] = relationship(
        "GuildFireboardSettings",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="guild_settings",
        uselist=False,
    )

    server_counters_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    server_counters_settings: Mapped["GuildServerCounterSettings | None"] = relationship(
        "GuildServerCounterSettings",
        back_populates="guild",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    leaderboard_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    leaderboard_settings: Mapped["GuildLeaderboardSettings | None"] = relationship(
        "GuildLeaderboardSettings",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="guild_settings",
        uselist=False,
    )

    confessions_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    confessions_settings: Mapped["GuildConfessionsSettings | None"] = relationship(
        "GuildConfessionsSettings",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="guild_settings",
        uselist=False,
    )

    tags_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    tag_settings: Mapped["GuildTagSettings | None"] = relationship(
        "GuildTagSettings",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="guild_settings",
        uselist=False,
    )

    rep_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    rep_settings: Mapped["GuildRepSettings | None"] = relationship(
        "GuildRepSettings",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="guild_settings",
        uselist=False,
    )


class GuildLimits(Base):
    __tablename__ = "guild_limits"
    id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="limits", uselist=False
    )

    enforcing: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    automod_rules: Mapped[int] = MappedColumn(Integer, server_default=text("10"))
    bad_word_list_size: Mapped[int] = MappedColumn(Integer, server_default=text("1000"))
    bouncer_rules: Mapped[int] = MappedColumn(Integer, server_default=text("10"))
    fireboards: Mapped[int] = MappedColumn(Integer, server_default=text("10"))
    leaderboard_levels: Mapped[int] = MappedColumn(Integer, server_default=text("100"))
    server_counters: Mapped[int] = MappedColumn(Integer, server_default=text("20"))
    tags: Mapped[int] = MappedColumn(Integer, server_default=text("250"))


class GuildModerationSettings(Base):
    __tablename__ = "guild_moderation_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="moderation_settings", uselist=False
    )
    delete_confirmation: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    dm_users: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    external_cases: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    ban_days: Mapped[int] = MappedColumn(Integer, server_default=text("0"))


class ModCase(Base):
    __tablename__ = "mod_cases"
    __table_args__ = (
        Index("ix_mod_cases_guild_id", "guild_id", desc("time_created")),
        Index("ix_mod_cases_guild_id_user_id", "guild_id", "user_id", desc("time_created")),
    )

    id: Mapped[str] = MappedColumn(String(length=8), primary_key=True, default=generate_short_uuid)
    type: Mapped[CaseType] = MappedColumn(Enum(CaseType), nullable=False)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = MappedColumn(BigInteger)
    creator_user_id: Mapped[int] = MappedColumn(BigInteger)
    time_created: Mapped[datetime] = MappedColumn(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    time_updated: Mapped[datetime | None] = MappedColumn(DateTime(timezone=True), nullable=True)
    time_expires: Mapped[datetime | None] = MappedColumn(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = MappedColumn(String(length=512), nullable=True)
    external: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    resolved: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    comments: Mapped[list["ModCaseComment"]] = relationship(
        "ModCaseComment", back_populates="case", cascade="all, delete-orphan"
    )
    scheduled_tasks: Mapped[list["ScheduledTask"]] = relationship(
        "ScheduledTask", back_populates="case", cascade="all, delete-orphan"
    )

    async def add_comment(
        self, member: Member, content: str, bot: TitaniumBot, guild: Guild | PartialInviteGuild
    ) -> ModCaseComment:
        from lib.classes.guild_logger import GuildLogger
        from lib.helpers.log_error import log_error

        comment = ModCaseComment(
            guild_id=self.guild_id, case_id=self.id, user_id=member.id, comment=content
        )

        async with get_session() as session:
            session.add(comment)

        try:
            log = GuildLogger(bot=bot, guild=guild)
            await log.titanium_case_comment(case=self, creator=member, comment=content)
        except Exception as e:
            await log_error(
                bot=bot,
                module="Logging",
                guild_id=guild.id,
                error=f"Unknown error while logging new case comment - {comment.id}",
                user=member,
                exc=e,
            )

        return comment

    async def get_user_comment(self, comment: uuid.UUID, user: int) -> ModCaseComment | None:
        async with get_session() as session:
            query = await session.execute(
                select(ModCaseComment)
                .where(ModCaseComment.id == comment)
                .where(ModCaseComment.case_id == self.id)
                .where(ModCaseComment.user_id == user)
            )

            return query.scalar_one_or_none()


class ModCaseComment(Base):
    __tablename__ = "mod_case_comments"
    __table_args__ = (Index("ix_mod_case_comments_case_id_guild_id", "case_id", "guild_id"),)

    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE")
    )
    case_id: Mapped[str] = MappedColumn(
        String(length=8), ForeignKey("mod_cases.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = MappedColumn(BigInteger)
    comment: Mapped[str] = MappedColumn(String(length=500))
    time_created: Mapped[datetime] = MappedColumn(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    case: Mapped["ModCase"] = relationship("ModCase", back_populates="comments", uselist=False)

    async def edit_comment(self, content: str) -> ModCaseComment | None:
        async with get_session() as session:
            self.comment = content
            session.add(self)

        return self

    async def delete_comment(self) -> None:
        async with get_session() as session:
            await session.delete(self)


class GuildAutomodSettings(Base):
    __tablename__ = "guild_automod_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="automod_settings", uselist=False
    )

    rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        back_populates="guild",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    show_outcome_message: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))

    global_ignored_channels: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    global_ignored_roles: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )


class AutomodRule(Base):
    __tablename__ = "automod_rules"
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_automod_settings.guild_id", ondelete="CASCADE")
    )

    rule_name: Mapped[str] = MappedColumn(String(length=100))
    enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"), nullable=False)
    evaluate_edits: Mapped[bool] = MappedColumn(
        Boolean, server_default=text("true"), nullable=False
    )
    match_all_criteria: Mapped[bool] = MappedColumn(
        Boolean, server_default=text("true"), nullable=False
    )

    order: Mapped[int] = MappedColumn(Integer, nullable=False)
    stop_if_triggered: Mapped[bool] = MappedColumn(
        Boolean, server_default=text("false"), nullable=False
    )

    criteria: Mapped[list["AutomodCriteria"]] = relationship(
        "AutomodCriteria",
        back_populates="rule",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    actions: Mapped[list["AutomodAction"]] = relationship(
        "AutomodAction",
        back_populates="rule",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    guild: Mapped["GuildAutomodSettings"] = relationship(
        "GuildAutomodSettings",
        back_populates="rules",
        uselist=False,
    )


class AutomodCriteria(Base):
    __tablename__ = "automod_criteria"
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[AutomodCriteriaType] = MappedColumn(Enum(AutomodCriteriaType))

    threshold: Mapped[int | None] = MappedColumn(Integer, nullable=True)
    duration: Mapped[int | None] = MappedColumn(Integer, nullable=True)

    words: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=100)), server_default=text("ARRAY[]::varchar[]"), nullable=False
    )
    match_whole_word: Mapped[bool] = MappedColumn(
        Boolean, server_default=text("false"), nullable=False
    )
    match_all_words: Mapped[bool] = MappedColumn(
        Boolean, server_default=text("false"), nullable=False
    )
    case_sensitive: Mapped[bool] = MappedColumn(
        Boolean, server_default=text("false"), nullable=False
    )

    rule_id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), ForeignKey("automod_rules.id", ondelete="CASCADE")
    )
    rule: Mapped["AutomodRule"] = relationship(
        "AutomodRule", back_populates="criteria", uselist=False
    )


class AutomodAction(Base):
    __tablename__ = "automod_actions"
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[AutomodActionType] = MappedColumn(Enum(AutomodActionType))

    duration: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)
    reason: Mapped[str | None] = MappedColumn(String(length=512), nullable=True)

    message_content: Mapped[str | None] = MappedColumn(String(length=1024), nullable=True)
    message_reply: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    message_mention: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    message_embed: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    embed_colour: Mapped[str | None] = MappedColumn(String(length=7), nullable=True)

    role_ids: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]"), nullable=False
    )

    rule_id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), ForeignKey("automod_rules.id", ondelete="CASCADE")
    )
    rule: Mapped["AutomodRule"] = relationship(
        "AutomodRule", back_populates="actions", uselist=False
    )


class GuildBouncerSettings(Base):
    __tablename__ = "guild_bouncer_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="bouncer_settings", uselist=False
    )
    rules: Mapped[list["BouncerRule"]] = relationship(
        "BouncerRule",
        back_populates="guild",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class BouncerRule(Base):
    __tablename__ = "bouncer_rules"
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_bouncer_settings.guild_id", ondelete="CASCADE")
    )

    rule_name: Mapped[str | None] = MappedColumn(String(length=100), nullable=True)
    enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    evaluate_for_existing_members: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))

    criteria: Mapped[list["BouncerCriteria"]] = relationship(
        "BouncerCriteria",
        back_populates="rule",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    actions: Mapped[list["BouncerAction"]] = relationship(
        "BouncerAction",
        back_populates="rule",
        cascade="all, delete-orphan",
        passive_deletes=True,
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
        UUID(as_uuid=True), ForeignKey("bouncer_rules.id", ondelete="CASCADE")
    )
    type: Mapped[BouncerCriteriaType] = MappedColumn(Enum(BouncerCriteriaType))

    account_age: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)

    words: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=100)), server_default=text("ARRAY[]::varchar[]")
    )
    match_whole_word: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    case_sensitive: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))

    rule: Mapped["BouncerRule"] = relationship(
        "BouncerRule", back_populates="criteria", uselist=False
    )


class BouncerAction(Base):
    __tablename__ = "bouncer_actions"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True, autoincrement=True)
    rule_id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), ForeignKey("bouncer_rules.id", ondelete="CASCADE")
    )
    type: Mapped[BouncerActionType] = MappedColumn(Enum(BouncerActionType))

    # Actions with duration
    duration: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)

    # Role actions
    role_id: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)

    # All actions
    reason: Mapped[str | None] = MappedColumn(String(length=512), nullable=True)

    rule: Mapped["BouncerRule"] = relationship(
        "BouncerRule", back_populates="actions", uselist=False
    )


class GuildLoggingSettings(Base):
    __tablename__ = "guild_logging_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="logging_settings", uselist=False
    )

    channels: Mapped[dict[str, int]] = MappedColumn(JSONB, server_default=text("'{}'::jsonb"))


class GuildFireboardSettings(Base):
    __tablename__ = "guild_fireboard_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
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

    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_fireboard_settings.guild_id", ondelete="CASCADE")
    )
    guild: Mapped["GuildFireboardSettings"] = relationship(
        "GuildFireboardSettings", back_populates="fireboard_boards", uselist=False
    )

    channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    reaction: Mapped[str] = MappedColumn(String(), server_default=text("'🔥'"))
    threshold: Mapped[int] = MappedColumn(Integer, server_default=text("5"))

    ignore_bots: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    ignore_self_reactions: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    send_notifications: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))

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
    guild_id: Mapped[int] = MappedColumn(
        BigInteger,
        ForeignKey("guild_fireboard_settings.guild_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    fireboard_message_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    fireboard_id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), ForeignKey("fireboard_boards.id", ondelete="CASCADE"), index=True
    )
    fireboard: Mapped["FireboardBoard"] = relationship(
        "FireboardBoard", back_populates="messages", uselist=False
    )


class GuildLeaderboardSettings(Base):
    __tablename__ = "guild_leaderboard_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="leaderboard_settings", uselist=False
    )

    mode: Mapped[LeaderboardCalcType] = MappedColumn(
        Enum(LeaderboardCalcType), nullable=False, server_default=text("'FIXED'")
    )
    delete_leavers: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    stack_roles: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))

    cooldown: Mapped[int] = MappedColumn(Integer, server_default=text("5"))
    base_xp: Mapped[int] = MappedColumn(Integer, server_default=text("10"))
    min_xp: Mapped[int] = MappedColumn(Integer, server_default=text("15"))
    max_xp: Mapped[int] = MappedColumn(Integer, server_default=text("25"))
    xp_mult: Mapped[float] = MappedColumn(Float, server_default=text("1.0"))

    vc_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    vc_mode: Mapped[LeaderboardVcCalcType] = MappedColumn(
        Enum(LeaderboardVcCalcType), nullable=False, server_default=text("'FIXED'")
    )
    vc_delay: Mapped[int] = MappedColumn(Integer, server_default=text("5"))
    vc_base_xp: Mapped[int] = MappedColumn(Integer, server_default=text("10"))
    vc_min_xp: Mapped[int] = MappedColumn(Integer, server_default=text("15"))
    vc_max_xp: Mapped[int] = MappedColumn(Integer, server_default=text("25"))

    ignored_roles: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    ignored_channels: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )

    levelup_notifications: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    notification_ping: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    notification_channel: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)

    web_leaderboard_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    web_login_required: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))

    levels: Mapped[list["LeaderboardLevels"]] = relationship(
        "LeaderboardLevels", back_populates="guild_settings", cascade="all, delete-orphan"
    )


class LeaderboardLevels(Base):
    __tablename__ = "leaderboard_levels"
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_leaderboard_settings.guild_id", ondelete="CASCADE")
    )
    guild_settings: Mapped["GuildLeaderboardSettings"] = relationship(
        "GuildLeaderboardSettings", back_populates="levels", uselist=False
    )
    xp: Mapped[int] = MappedColumn(Integer, server_default=text("0"))
    reward_roles: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )


class LeaderboardUserStats(Base):
    __tablename__ = "leaderboard_user_stats"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_leaderboard_guild_user"),
        Index("ix_leaderboard_user_stats_guild_xp", "guild_id", desc("xp")),
    )

    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger,
        ForeignKey("guild_leaderboard_settings.guild_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = MappedColumn(BigInteger, nullable=False, index=True)

    xp: Mapped[int] = MappedColumn(BigInteger, server_default=text("0"))
    level: Mapped[int] = MappedColumn(BigInteger, server_default=text("0"))
    daily_snapshots: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )

    message_count: Mapped[int] = MappedColumn(BigInteger, server_default=text("0"))
    word_count: Mapped[int] = MappedColumn(BigInteger, server_default=text("0"))
    attachment_count: Mapped[int] = MappedColumn(BigInteger, server_default=text("0"))
    explicit_count: Mapped[int] = MappedColumn(BigInteger, server_default=text("0"))
    vc_minutes: Mapped[int] = MappedColumn(BigInteger, server_default=text("0"))


class GuildServerCounterSettings(Base):
    __tablename__ = "guild_server_counter_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
    )
    guild: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="server_counters_settings", uselist=False
    )
    channels: Mapped[list["ServerCounterChannel"]] = relationship(
        "ServerCounterChannel", back_populates="settings", cascade="all, delete-orphan"
    )


class ServerCounterChannel(Base):
    __tablename__ = "server_counter_channels"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger,
        ForeignKey("guild_server_counter_settings.guild_id", ondelete="CASCADE"),
    )
    settings: Mapped["GuildServerCounterSettings"] = relationship(
        "GuildServerCounterSettings", back_populates="channels", uselist=False
    )
    count_type: Mapped[ServerCounterType] = MappedColumn(Enum(ServerCounterType))
    name: Mapped[str] = MappedColumn(String(length=50), server_default=text("'{value}'"))


class GuildConfessionsSettings(Base):
    __tablename__ = "guild_confession_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="confessions_settings", uselist=False
    )
    confessions_in_channel: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    confessions_channel_id: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)
    polls_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    attachments_allowed: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))


class AnonymousPoll(Base):
    __tablename__ = "anonymous_polls"
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE")
    )

    channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    creator_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    message_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)

    content: Mapped[str] = MappedColumn(String(length=1000), nullable=False)
    image_url: Mapped[str | None] = MappedColumn(String(), nullable=True)
    choices: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=100)),
        server_default=text("ARRAY[]::varchar[]"),
    )
    closing_time: Mapped[datetime] = MappedColumn(DateTime(timezone=True), nullable=False)
    show_live_results: Mapped[bool] = MappedColumn(
        Boolean, server_default=text("true"), nullable=False
    )

    responses: Mapped[list["AnonymousPollResponse"]] = relationship(
        "AnonymousPollResponse",
        back_populates="poll",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    scheduled_task: Mapped[ScheduledTask] = relationship(
        "ScheduledTask", back_populates="poll", cascade="all, delete-orphan", passive_deletes=True
    )

    async def delete(self) -> None:
        async with get_session() as session:
            await session.delete(self)


class AnonymousPollResponse(Base):
    __tablename__ = "anonymous_poll_responses"
    __table_args__ = (UniqueConstraint("poll_id", "user_id", name="uq_poll_user_id"),)

    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    poll_id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True),
        ForeignKey("anonymous_polls.id", ondelete="CASCADE"),
        nullable=False,
    )
    answer_index: Mapped[int] = MappedColumn(Integer, nullable=False)

    poll: Mapped["AnonymousPoll"] = relationship(
        "AnonymousPoll",
        back_populates="responses",
        uselist=False,
    )


class GuildTagSettings(Base):
    __tablename__ = "guild_tag_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="tag_settings", uselist=False
    )
    prefix_fallback: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    allow_user_tags: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", back_populates="settings", cascade="all, delete-orphan"
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("guild_id", "name", name="uq_tag_guild_name"),
        Index(
            "uq_tag_user_name",
            "owner_id",
            "name",
            unique=True,
            postgresql_where=text("is_user = true"),
        ),
    )

    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int | None] = MappedColumn(
        BigInteger, ForeignKey("guild_tag_settings.guild_id", ondelete="CASCADE"), nullable=True
    )
    settings: Mapped["GuildTagSettings"] = relationship(
        "GuildTagSettings", back_populates="tags", uselist=False
    )

    owner_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    modified_by: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)
    is_user: Mapped[bool] = MappedColumn(Boolean, nullable=False)
    name: Mapped[str] = MappedColumn(String(length=80), nullable=False)
    content: Mapped[str] = MappedColumn(String(length=2000), nullable=False)
    amount_used: Mapped[int] = MappedColumn(BigInteger, server_default=text("0"))


class GuildRepSettings(Base):
    __tablename__ = "guild_rep_settings"

    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_settings.guild_id", ondelete="CASCADE"), primary_key=True
    )
    guild_settings: Mapped["GuildSettings"] = relationship(
        "GuildSettings", back_populates="rep_settings", uselist=False
    )

    rep_hint: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    allow_rep_remove: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    delete_leavers: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))

    web_leaderboard_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    web_login_required: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))

    ignored_roles: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    ignored_channels: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )


class UserRep(Base):
    __tablename__ = "user_rep"
    __table_args__ = (
        UniqueConstraint("user_id", "guild_id", name="uq_user_guild_id"),
        Index("ix_user_rep_guild_rep", "guild_id", desc("rep")),
    )

    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    guild_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)

    rep: Mapped[int] = MappedColumn(BigInteger, server_default=text("0"), nullable=False)
    daily_snapshots: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )


class RepAddHistory(Base):
    __tablename__ = "rep_add_history"
    __table_args__ = (
        Index("ix_rep_add_history_guild_user_target", "guild_id", "user_id", "target_id"),
    )

    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    target_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    guild_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)

    time: Mapped[datetime] = MappedColumn(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )


class GameStat(Base):
    __tablename__ = "game_stats"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = MappedColumn(BigInteger, nullable=False, index=True)
    game: Mapped[GameTypes] = MappedColumn(Enum(GameTypes), nullable=False)
    won: Mapped[bool] = MappedColumn(Boolean, nullable=False)


class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[str] = MappedColumn(String(length=8), primary_key=True, default=generate_short_uuid)

    guild_id: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)
    channel_id: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)
    user_id: Mapped[int] = MappedColumn(BigInteger, nullable=False, index=True)
    dm: Mapped[bool] = MappedColumn(Boolean, nullable=False)
    time: Mapped[datetime] = MappedColumn(DateTime(timezone=True), nullable=False)
    time_created: Mapped[datetime] = MappedColumn(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    content: Mapped[str] = MappedColumn(String(), nullable=False)
    scheduled_task: Mapped[ScheduledTask] = relationship(
        "ScheduledTask",
        back_populates="reminder",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    async def edit(self, content: Optional[str] = None, time: Optional[datetime] = None) -> Tag:
        if not content and not time:
            raise ValueError("Content or time must be specified")

        async with get_session() as session:
            result = await session.execute(
                select(Reminder)
                .where(Reminder.id == self.id)
                .options(selectinload(Reminder.scheduled_task))
            )
            reminder = result.scalar_one_or_none()

            if not reminder:
                raise RuntimeError("Failed to get reminder")

            if time is not None:
                reminder.time = time
                reminder.scheduled_task.time_scheduled = time

            if content is not None:
                reminder.content = content

            session.add(reminder)

        return self

    async def delete(self) -> None:
        async with get_session() as session:
            await session.delete(self)


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    __table_args__ = (Index("ix_scheduled_tasks_guild_user_type", "guild_id", "user_id", "type"),)

    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    time_scheduled: Mapped[datetime] = MappedColumn(DateTime(timezone=True), index=True)
    type: Mapped[EventType] = MappedColumn(Enum(EventType), nullable=False)

    guild_id: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)
    user_id: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)
    channel_id: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)
    role_id: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)
    message_id: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)

    # moderation
    case_id: Mapped[str | None] = MappedColumn(
        String(length=8), ForeignKey("mod_cases.id", ondelete="CASCADE"), nullable=True
    )
    case: Mapped["ModCase | None"] = relationship(
        "ModCase", back_populates="scheduled_tasks", uselist=False
    )
    duration: Mapped[int | None] = MappedColumn(
        BigInteger, nullable=True
    )  # for refresh_mute - how long we need to extend mute by

    # reminders
    reminder_id: Mapped[str | None] = MappedColumn(
        String(length=8), ForeignKey("reminders.id", ondelete="CASCADE"), nullable=True
    )
    reminder: Mapped["Reminder | None"] = relationship(
        "Reminder", back_populates="scheduled_task", uselist=False
    )

    # anonymous poll
    poll_id: Mapped[uuid.UUID | None] = MappedColumn(
        UUID(as_uuid=True), ForeignKey("anonymous_polls.id", ondelete="CASCADE"), nullable=True
    )
    poll: Mapped["AnonymousPoll | None"] = relationship(
        "AnonymousPoll", back_populates="scheduled_task", uselist=False
    )


class AvailableWebhook(Base):
    __tablename__ = "available_webhooks"

    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger,
        ForeignKey("guild_settings.guild_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    webhook_url: Mapped[str] = MappedColumn(String, nullable=False)


class ErrorLog(Base):
    __tablename__ = "error_logs"
    __table_args__ = (Index("ix_error_logs_guild_id", "guild_id", desc("time_occurred")),)

    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int | None] = MappedColumn(BigInteger, nullable=True)
    module: Mapped[str] = MappedColumn(String(length=100))
    error: Mapped[str] = MappedColumn(String(length=512))
    details: Mapped[str | None] = MappedColumn(String(length=1024), nullable=True)
    time_occurred: Mapped[datetime] = MappedColumn(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class OptOutIDs(Base):
    __tablename__ = "opt_out_ids"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)


class SpotifyToken(Base):
    __tablename__ = "spotify_tokens"
    token: Mapped[str] = MappedColumn(String, primary_key=True)
    time_added: Mapped[datetime] = MappedColumn(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    expires_in: Mapped[int] = MappedColumn(Integer)


def get_guild_settings_child_tables() -> tuple[tuple[type[Any], str], ...]:
    configure_mappers()

    child_tables: list[tuple[type[Any], str]] = []
    guild_settings_table = GuildSettings.__table__

    for mapper in Base.registry.mappers:
        model = mapper.class_

        if model is GuildSettings or len(mapper.primary_key) != 1:
            continue

        primary_key = mapper.primary_key[0]
        if any(
            foreign_key.column.table is guild_settings_table
            for foreign_key in primary_key.foreign_keys
        ):
            child_tables.append((model, primary_key.key))

    return tuple(sorted(child_tables, key=lambda table: table[0].__tablename__))


load_dotenv()

SQLALCHEMY_DATABASE_URL = URL.create(
    "postgresql+asyncpg",
    username=os.getenv("DB_USERNAME", ""),
    password=os.getenv("DB_PASSWORD", ""),
    host=os.getenv("DB_HOST", ""),
    port=int(os.getenv("DB_PORT", 0)),
    database=os.getenv("DB_DATABASE_NAME", ""),
)

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
    logger.info(f"Connecting to database at {SQLALCHEMY_DATABASE_URL}, password is hidden")

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
            raise RuntimeError("Database migration failed")

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
async def get_session(autocommit: bool = True):
    async with async_session() as session:
        session: AsyncSession
        try:
            yield session

            if autocommit:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
