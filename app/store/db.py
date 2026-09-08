# app/store/db.py
import os
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://bidharness:localdev@db:5432/bidharness",
)


class Base(DeclarativeBase):
    """Base class all ORM models inherit from."""
    pass


# echo=True logs every SQL statement — useful while building, turn off later
engine = create_async_engine(DATABASE_URL, echo=True, future=True)

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,  # keeps objects usable after commit, avoids re-query surprises
)


async def get_db():
    """FastAPI dependency — yields a session per request, closes it after."""
    async with async_session() as session:
        yield session


async def init_db():
    """Create all tables. Fine for a 3-day project; a real app would use Alembic migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)