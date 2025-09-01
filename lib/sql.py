import os
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, MappedColumn, declarative_base, relationship

Base = declarative_base()


# -- Tables --
class ModCase(Base):
    __tablename__ = "mod_cases"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
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
    case_id: Mapped[int] = MappedColumn(BigInteger, ForeignKey("mod_cases.id"))
    user_id: Mapped[int] = MappedColumn(BigInteger)
    comment: Mapped[str] = MappedColumn(String(length=512))
    time_created: Mapped[datetime] = MappedColumn(DateTime)
    case: Mapped["ModCase"] = relationship(
        "ModCase", back_populates="comments", uselist=False
    )


class ServerSettings(Base):
    __tablename__ = "server_settings"
    guild_id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    moderation_enabled: Mapped[bool] = MappedColumn(Boolean, default=True)
    automod_enabled: Mapped[bool] = MappedColumn(Boolean, default=True)
    automod_settings: Mapped["ServerAutomodSettings"] = relationship(
        "ServerAutomodSettings",
        cascade="all, delete-orphan",
        back_populates="server_settings",
        uselist=False,
    )


class ServerAutomodSettings(Base):
    __tablename__ = "server_automod_settings"
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("server_settings.guild_id"), primary_key=True
    )
    server_settings: Mapped["ServerSettings"] = relationship(
        "ServerSettings", back_populates="automod_settings", uselist=False
    )
    badword_detection: Mapped[bool] = MappedColumn(Boolean, default=False)
    badword_detection_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(ServerAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='badword_detection')",
        back_populates="server",
        cascade="all, delete-orphan",
    )
    spam_detection: Mapped[bool] = MappedColumn(Boolean, default=False)
    spam_detection_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(ServerAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='spam_detection')",
        back_populates="server",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules",
    )
    malicious_link_detection: Mapped[bool] = MappedColumn(Boolean, default=False)
    malicious_link_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(ServerAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='malicious_link')",
        back_populates="server",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules,spam_detection_rules",
    )
    phishing_link_detection: Mapped[bool] = MappedColumn(Boolean, default=False)
    phishing_link_rules: Mapped[list["AutomodRule"]] = relationship(
        "AutomodRule",
        primaryjoin="and_(ServerAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='phishing_link')",
        back_populates="server",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules,malicious_link_rules,spam_detection_rules",
    )


class AutomodRule(Base):
    __tablename__ = "automod_rules"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("server_automod_settings.guild_id")
    )
    rule_type: Mapped[str] = MappedColumn(String(length=32))
    antispam_type: Mapped[str] = MappedColumn(String(length=32), nullable=True)
    words: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=100)), server_default=text("ARRAY[]::varchar[]")
    )
    occurrences: Mapped[int] = MappedColumn(Integer)
    threshold: Mapped[int] = MappedColumn(Integer)
    duration: Mapped[int] = MappedColumn(Integer)
    actions: Mapped[list["AutomodAction"]] = relationship(
        "AutomodAction",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="AutomodAction.order",
    )
    server: Mapped["ServerAutomodSettings"] = relationship(
        "ServerAutomodSettings",
        overlaps="badword_detection_rules,spam_detection_rules,malicious_link_rules,phishing_link_rules",
        uselist=False,
    )


class AutomodAction(Base):
    __tablename__ = "automod_actions"
    id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    guild_id: Mapped[int] = MappedColumn(
        BigInteger,
        ForeignKey("server_automod_settings.guild_id"),
    )
    rule_id: Mapped[int] = MappedColumn(BigInteger, ForeignKey("automod_rules.id"))
    rule_type: Mapped[str] = MappedColumn(String(length=32))
    action_type: Mapped[str] = MappedColumn(String(length=32))
    duration: Mapped[int] = MappedColumn(BigInteger, nullable=True)
    reason: Mapped[str] = MappedColumn(String(length=512), nullable=True)
    order: Mapped[int] = MappedColumn(Integer, default=0)
    rule: Mapped["AutomodRule"] = relationship(
        "AutomodRule", back_populates="actions", uselist=False
    )


class ServerLimits(Base):
    __tablename__ = "server_limits"
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


class ServerPrefixes(Base):
    __tablename__ = "server_prefixes"
    guild_id: Mapped[int] = MappedColumn(BigInteger, primary_key=True)
    prefixes: Mapped[list[str]] = MappedColumn(
        ARRAY(String(length=5)),
        default=["t!"],
        server_default=text("ARRAY['t!']::varchar[]"),
        nullable=False,
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
    case_id: Mapped[int] = MappedColumn(
        BigInteger, ForeignKey("mod_cases.id"), nullable=True
    )
    case: Mapped["ModCase"] = relationship(
        "ModCase", back_populates="scheduled_tasks", uselist=False
    )
    time_scheduled: Mapped[datetime] = MappedColumn(DateTime)


# -- Engine --
engine = create_async_engine(
    os.getenv("DATABASE_URL", ""),
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()


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
