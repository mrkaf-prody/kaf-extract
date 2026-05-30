"""Async database session management for PostgreSQL."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

# Async engine bound to PostgreSQL (or SQLite in dev)
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """Create all SQLAlchemy tables that don't exist yet."""
    from src.models.sql_models import Base
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add 'deleted' to user_status enum if not present
        try:
            await conn.execute(text(
                "ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'deleted'"
            ))
        except Exception:
            pass  # Ignore if already exists or type doesn't exist yet
