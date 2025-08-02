import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# -- Tables --
class ModCases(Base):
    __tablename__ = "mod_cases"
    id = Column(BigInteger, primary_key=True)
    guild_id = Column(BigInteger)
    user_id = Column(BigInteger)
    proof_msg_id = Column(BigInteger)
    proof_channel_id = Column(BigInteger)
    proof_text = Column(String)
    time_created = Column(DateTime)
    time_updated = Column(DateTime)
    time_expires = Column(DateTime, nullable=True)
    description = Column(String(length=512), nullable=True)
    comments = relationship("ModCaseComments", back_populates="case")


class ModCaseComments(Base):
    __tablename__ = "mod_case_comments"
    id = Column(BigInteger, primary_key=True)
    guild_id = Column(BigInteger)
    case_id = Column(BigInteger, ForeignKey("mod_cases.id"))
    user_id = Column(BigInteger)
    comment = Column(String(length=512))
    time_created = Column(DateTime)
    case = relationship("ModCases", back_populates="comments")


class ScheduledTasks(Base):
    __tablename__ = "scheduled_tasks"
    id = Column(Integer, primary_key=True)
    type = Column(String)
    guild_id = Column(BigInteger)
    user_id = Column(BigInteger)
    channel_id = Column(BigInteger)
    role_id = Column(BigInteger)
    message_id = Column(BigInteger)
    time_scheduled = Column(DateTime)


class ServerPrefixes(Base):
    __tablename__ = "server_prefixes"
    guild_id = Column(BigInteger, primary_key=True)
    prefixes = Column(ARRAY(String(length=4)))


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
