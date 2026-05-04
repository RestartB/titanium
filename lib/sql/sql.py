import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Optional

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
    select,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, MappedColumn, declarative_base, relationship

from lib.enums.automod import AutomodActionType, AutomodAntispamType, AutomodRuleType
from lib.enums.bouncer import BouncerActionType, BouncerCriteriaType
from lib.enums.games import GameTypes
from lib.enums.leaderboard import LeaderboardCalcType
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

    loading_reaction: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    delete_after_3_days: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    leave_date: Mapped[datetime | None] = MappedColumn(DateTime(timezone=True), nullable=True)

    dashboard_managers: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    case_managers: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )

    moderation_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    moderation_settings: Mapped["GuildModerationSettings"] = relationship(
        "GuildModerationSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )

    automod_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    automod_settings: Mapped["GuildAutomodSettings"] = relationship(
        "GuildAutomodSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )

    bouncer_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    bouncer_settings: Mapped["GuildBouncerSettings"] = relationship(
        "GuildBouncerSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )

    logging_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    logging_settings: Mapped["GuildLoggingSettings"] = relationship(
        "GuildLoggingSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )

    fireboard_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    fireboard_settings: Mapped["GuildFireboardSettings"] = relationship(
        "GuildFireboardSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )

    server_counters_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    server_counters_settings: Mapped["GuildServerCounterSettings"] = relationship(
        "GuildServerCounterSettings",
        back_populates="guild",
        cascade="all, delete-orphan",
        uselist=False,
    )

    leaderboard_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    leaderboard_settings: Mapped["GuildLeaderboardSettings"] = relationship(
        "GuildLeaderboardSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )

    confessions_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    confessions_settings: Mapped["GuildConfessionsSettings"] = relationship(
        "GuildConfessionsSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )

    tags_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    tag_settings: Mapped["GuildTagSettings"] = relationship(
        "GuildTagSettings",
        cascade="all, delete-orphan",
        back_populates="guild_settings",
        uselist=False,
    )


class GuildLimits(Base):
    __tablename__ = "guild_limits"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    automod_rules: Mapped[int] = MappedColumn(Integer, server_default=text("50"))
    bad_word_list_size: Mapped[int] = MappedColumn(Integer, server_default=text("1500"))
    bouncer_rules: Mapped[int] = MappedColumn(Integer, server_default=text("10"))
    fireboards: Mapped[int] = MappedColumn(Integer, server_default=text("10"))
    server_counters: Mapped[int] = MappedColumn(Integer, server_default=text("20"))


class GuildPrefixes(Base):
    __tablename__ = "guild_prefixes"
    guild_id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    prefixes: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=5)),
        default=["t!"],
        server_default=text("ARRAY['t!']::varchar[]"),
        nullable=False,
    )


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
    id: Mapped[str] = MappedColumn(String(length=8), primary_key=True, default=generate_short_uuid)
    type: Mapped[CaseType] = MappedColumn(Enum(CaseType), nullable=False)
    guild_id: Mapped[int] = MappedColumn(BigInteger)
    user_id: Mapped[int] = MappedColumn(BigInteger)
    creator_user_id: Mapped[int] = MappedColumn(BigInteger)
    time_created: Mapped[datetime] = MappedColumn(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    time_updated: Mapped[datetime] = MappedColumn(DateTime(timezone=True), nullable=True)
    time_expires: Mapped[datetime] = MappedColumn(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = MappedColumn(String(length=512), nullable=True)
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
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(BigInteger)
    case_id: Mapped[str] = MappedColumn(
        String(length=8), ForeignKey("mod_cases.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = MappedColumn(BigInteger)
    comment: Mapped[str] = MappedColumn(String(length=512))
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
    badword_detection_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(GuildAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='BADWORD_DETECTION')",
        back_populates="guild",
        cascade="all, delete-orphan",
    )
    spam_detection_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(GuildAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='SPAM_DETECTION')",
        back_populates="guild",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules",
    )
    malicious_link_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(GuildAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='MALICIOUS_LINK')",
        back_populates="guild",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules,spam_detection_rules",
    )
    phishing_link_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(GuildAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='PHISHING_LINK')",
        back_populates="guild",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules,malicious_link_rules,spam_detection_rules",
    )


class AutomodRule(Base):
    __tablename__ = "automod_rules"
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_automod_settings.guild_id", ondelete="CASCADE")
    )
    rule_type: Mapped[AutomodRuleType] = MappedColumn(Enum(AutomodRuleType))
    antispam_type: Mapped[AutomodAntispamType] = MappedColumn(
        Enum(AutomodAntispamType), nullable=True
    )
    rule_name: Mapped[str] = MappedColumn(String(length=100), nullable=True)
    words: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=100)), server_default=text("ARRAY[]::varchar[]")
    )
    match_whole_word: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    case_sensitive: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
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
        ForeignKey("guild_automod_settings.guild_id", ondelete="CASCADE"),
    )
    rule_id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), ForeignKey("automod_rules.id", ondelete="CASCADE")
    )

    rule_type: Mapped[AutomodRuleType] = MappedColumn(Enum(AutomodRuleType))
    action_type: Mapped[AutomodActionType] = MappedColumn(Enum(AutomodActionType))

    duration: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    reason: Mapped[str] = MappedColumn(String(length=512), nullable=True)

    message_content: Mapped[str] = MappedColumn(String(length=2000), nullable=True)
    message_reply: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    message_mention: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    message_embed: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))
    embed_colour: Mapped[str] = MappedColumn(String(length=7), nullable=True)

    role_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
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
    )


class BouncerRule(Base):
    __tablename__ = "bouncer_rules"
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("guild_bouncer_settings.guild_id", ondelete="CASCADE")
    )
    rule_name: Mapped[str] = MappedColumn(String(length=100), nullable=True)
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
    criteria_type: Mapped[BouncerCriteriaType] = MappedColumn(Enum(BouncerCriteriaType))
    account_age: Mapped[int] = MappedColumn(BigInteger, nullable=True)
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
    action_type: Mapped[BouncerActionType] = MappedColumn(Enum(BouncerActionType))

    # Actions with duration
    duration: Mapped[int] = MappedColumn(BigInteger, nullable=True)

    # Role actions
    role_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)

    # All actions
    reason: Mapped[str] = MappedColumn(String(length=512), nullable=True)

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
    guild_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    message_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    fireboard_message_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    fireboard_id: Mapped[uuid.UUID] = MappedColumn(
        UUID(as_uuid=True), ForeignKey("fireboard_boards.id", ondelete="CASCADE")
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

    cooldown: Mapped[int] = MappedColumn(Integer, server_default=text("5"))
    base_xp: Mapped[Optional[int]] = MappedColumn(Integer, server_default=text("10"))
    min_xp: Mapped[Optional[int]] = MappedColumn(Integer, server_default=text("15"))
    max_xp: Mapped[Optional[int]] = MappedColumn(Integer, server_default=text("25"))
    xp_mult: Mapped[Optional[float]] = MappedColumn(Float, server_default=text("1.0"))

    ignored_roles: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )
    ignored_channels: Mapped[list[int]] = MappedColumn(
        ARRAY(BigInteger), server_default=text("ARRAY[]::bigint[]")
    )

    levelup_notifications: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    notification_ping: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    notification_channel: Mapped[Optional[int]] = MappedColumn(BigInteger, nullable=True)

    web_leaderboard_enabled: Mapped[bool] = MappedColumn(Boolean, server_default=text("true"))
    web_login_required: Mapped[bool] = MappedColumn(Boolean, server_default=text("false"))

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
    __table_args__ = (UniqueConstraint("guild_id", "user_id", name="uq_leaderboard_guild_user"),)

    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = MappedColumn(BigInteger, nullable=False, index=True)

    xp: Mapped[int] = MappedColumn(Integer, server_default=text("0"))
    level: Mapped[int] = MappedColumn(Integer, server_default=text("0"))
    daily_snapshots: Mapped[list[int]] = MappedColumn(
        ARRAY(Integer), server_default=text("ARRAY[]::integer[]")
    )

    message_count: Mapped[int] = MappedColumn(Integer, server_default=text("0"))
    word_count: Mapped[int] = MappedColumn(Integer, server_default=text("0"))
    attachment_count: Mapped[int] = MappedColumn(Integer, server_default=text("0"))
    explicit_count: Mapped[int] = MappedColumn(Integer, server_default=text("0"))


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
    content: Mapped[str] = MappedColumn(String(length=1024), nullable=False)


class GameStat(Base):
    __tablename__ = "game_stats"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    game: Mapped[GameTypes] = MappedColumn(Enum(GameTypes), nullable=False)
    won: Mapped[bool] = MappedColumn(Boolean, nullable=False)


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[EventType] = MappedColumn(Enum(EventType), nullable=False)
    guild_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    user_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    role_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    message_id: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    case_id: Mapped[str] = MappedColumn(
        String(length=8), ForeignKey("mod_cases.id", ondelete="CASCADE"), nullable=True
    )
    duration: Mapped[int] = MappedColumn(
        BigInteger, nullable=True
    )  # for refresh_mute - how long we need to extend mute by
    case: Mapped["ModCase"] = relationship(
        "ModCase", back_populates="scheduled_tasks", uselist=False
    )
    time_scheduled: Mapped[datetime] = MappedColumn(DateTime(timezone=True), index=True)


class AvailableWebhook(Base):
    __tablename__ = "available_webhooks"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    guild_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    channel_id: Mapped[int] = MappedColumn(BigInteger, nullable=False)
    webhook_url: Mapped[str] = MappedColumn(String, nullable=False)


class ErrorLog(Base):
    __tablename__ = "error_logs"
    id: Mapped[uuid.UUID] = MappedColumn(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = MappedColumn(BigInteger)
    module: Mapped[str] = MappedColumn(String(length=100))
    error: Mapped[str] = MappedColumn(String(length=512))
    details: Mapped[str] = MappedColumn(String(length=1024), nullable=True)
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
