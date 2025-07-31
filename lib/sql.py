from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# -- Tables --
class ModCases(Base):
    __tablename__ = "mod_cases"
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer)
    user_id = Column(Integer)
    proof_msg_id = Column(Integer)
    proof_channel_id = Column(Integer)
    proof_text = Column(String)
    date_created = Column(DateTime)
    comments = relationship("ModCaseComments", back_populates="case")


class ModCaseComments(Base):
    __tablename__ = "mod_case_comments"
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer)
    case_id = Column(Integer, ForeignKey("mod_cases.id"))
    user_id = Column(Integer)
    comment = Column(String(length=512))
    date_created = Column(DateTime)
    case = relationship("ModCases", back_populates="comments")


class ScheduledTasks(Base):
    __tablename__ = "scheduled_tasks"
    id = Column(Integer, primary_key=True)
    type = Column(String)
    guild_id = Column(Integer)
    user_id = Column(Integer)
    channel_id = Column(Integer)
    role_id = Column(Integer)
    message_id = Column(Integer)
    date_scheduled = Column(DateTime)


# -- Engine --
engine = create_async_engine(
    "sqlite+aiosqlite:///titanium.db",
    echo=True,
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

        await conn.execute("PRAGMA foreign_keys = ON;")
        await conn.execute("PRAGMA journal_mode = WAL;")

        await conn.commit()


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
