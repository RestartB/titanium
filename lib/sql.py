import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# -- Tables --
class ModCase(Base):
    __tablename__ = "mod_cases"
    id = Column(BigInteger, primary_key=True)
    type = Column(String(length=32))
    guild_id = Column(BigInteger)
    user_id = Column(BigInteger)
    creator_user_id = Column(BigInteger)
    proof_msg_id = Column(BigInteger)
    proof_channel_id = Column(BigInteger)
    proof_text = Column(String)
    time_created = Column(DateTime)
    time_updated = Column(DateTime, nullable=True)
    time_expires = Column(DateTime, nullable=True)
    description = Column(String(length=512), nullable=True)
    resolved = Column(Boolean, default=False)
    comments = relationship(
        "ModCaseComment", back_populates="case", cascade="all, delete-orphan"
    )
    scheduled_tasks = relationship(
        "ScheduledTask", back_populates="case", cascade="all, delete-orphan"
    )


class ModCaseComment(Base):
    __tablename__ = "mod_case_comments"
    id = Column(BigInteger, primary_key=True)
    guild_id = Column(BigInteger)
    case_id = Column(BigInteger, ForeignKey("mod_cases.id"))
    user_id = Column(BigInteger)
    comment = Column(String(length=512))
    time_created = Column(DateTime)
    case = relationship("ModCase", back_populates="comments")


class ServerSettings(Base):
    __tablename__ = "server_settings"
    guild_id = Column(BigInteger, primary_key=True)
    moderation_enabled = Column(Boolean, default=True)
    automod_enabled = Column(Boolean, default=True)
    automod_settings = relationship(
        "ServerAutomodSettings", cascade="all, delete-orphan"
    )


class ServerAutomodSettings(Base):
    __tablename__ = "server_automod_settings"
    guild_id = Column(
        BigInteger, ForeignKey("server_settings.guild_id"), primary_key=True
    )
    badword_detection = Column(Boolean, default=False)
    badword_detection_rules = relationship(
        "AutomodRule",
        primaryjoin="and_(ServerAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='badword_detection')",
        back_populates="server",
        cascade="all, delete-orphan",
    )
    spam_detection = Column(Boolean, default=False)
    spam_detection_rules = relationship(
        "AutomodRule",
        primaryjoin="and_(ServerAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='spam_detection')",
        back_populates="server",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules",
    )
    malicious_link_detection = Column(Boolean, default=False)
    malicious_link_rules = relationship(
        "AutomodRule",
        primaryjoin="and_(ServerAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='malicious_link')",
        back_populates="server",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules,spam_detection_rules",
    )
    phishing_link_detection = Column(Boolean, default=False)
    phishing_link_rules = relationship(
        "AutomodRule",
        primaryjoin="and_(ServerAutomodSettings.guild_id==foreign(AutomodRule.guild_id), AutomodRule.rule_type=='phishing_link')",
        back_populates="server",
        cascade="all, delete-orphan",
        overlaps="badword_detection_rules,malicious_link_rules,spam_detection_rules",
    )


class AutomodRule(Base):
    __tablename__ = "automod_rules"
    id = Column(BigInteger, primary_key=True)
    guild_id = Column(BigInteger, ForeignKey("server_automod_settings.guild_id"))
    user_id = Column(BigInteger)
    rule_type = Column(String(length=32))
    antispam_type = Column(String(length=32), nullable=True)
    words = Column(ARRAY(String(length=100)), server_default=text("ARRAY[]::varchar[]"))
    occurrences = Column(Integer)
    threshold = Column(Integer)
    duration = Column(Integer)
    actions = relationship(
        "AutomodAction",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="AutomodAction.order",
    )
    server = relationship(
        "ServerAutomodSettings",
        overlaps="badword_detection_rules,spam_detection_rules,malicious_link_rules,phishing_link_rules",
    )


class AutomodAction(Base):
    __tablename__ = "automod_actions"
    id = Column(BigInteger, primary_key=True)
    rule_id = Column(BigInteger, ForeignKey("automod_rules.id"))
    rule_type = Column(String(length=32))
    action_type = Column(String(length=32))
    duration = Column(BigInteger, nullable=True)
    reason = Column(String(length=512), nullable=True)
    order = Column(Integer, default=0)
    rule = relationship("AutomodRule", back_populates="actions")


class ServerLimits(Base):
    __tablename__ = "server_limits"
    id = Column(Integer, primary_key=True)
    BadWordList = Column(Integer, default=10)
    BadWordListSize = Column(Integer, default=1500)
    MessageSpamRules = Column(Integer, default=5)
    MentionSpamRules = Column(Integer, default=5)
    WordSpamRules = Column(Integer, default=5)
    NewLineSpamRules = Column(Integer, default=5)
    LinkSpamRules = Column(Integer, default=5)
    AttachmentSpamRules = Column(Integer, default=5)
    EmojiSpamRules = Column(Integer, default=5)


class ServerPrefixes(Base):
    __tablename__ = "server_prefixes"
    guild_id = Column(BigInteger, primary_key=True)
    prefixes = Column(
        ARRAY(String(length=5)),
        default=["t!"],
        server_default=text("ARRAY['t!']::varchar[]"),
        nullable=False,
    )


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    id = Column(BigInteger, primary_key=True)
    type = Column(String)
    guild_id = Column(BigInteger)
    user_id = Column(BigInteger)
    channel_id = Column(BigInteger)
    role_id = Column(BigInteger)
    message_id = Column(BigInteger)
    case_id = Column(BigInteger, ForeignKey("mod_cases.id"), nullable=True)
    case = relationship("ModCase", back_populates="scheduled_tasks", uselist=False)
    time_scheduled = Column(DateTime)


# -- Engine --
load_dotenv()
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
