from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.base import Base
from app.core.config import settings


# ---------------------------------------------------------------------------
# Model imports
# ---------------------------------------------------------------------------
# These imports ensure SQLAlchemy knows about every model before
# Base.metadata.create_all() is executed.
# ---------------------------------------------------------------------------

# from app.models.address import Address  # noqa: F401,E402
# from app.models.auth_event import AuthEvent  # noqa: F401,E402
# from app.models.farm import Farm  # noqa: F401,E402
# from app.models.otp_verifications import OTPVerification  # noqa: F401,E402
# from app.models.role import Role  # noqa: F401,E402
# from app.models.user import User  # noqa: F401,E402
# from app.models.user_session import UserSession  # noqa: F401,E402


# ---------------------------------------------------------------------------
# Database engine
# ---------------------------------------------------------------------------

# Supabase's transaction pooler (port 6543) does not support asyncpg's prepared
# statement cache ("prepared statement ... already exists" errors). These settings
# switch the cache off and give every statement a unique name, so the engine works
# on both the transaction pooler (6543) and the session pooler / direct port (5432).
engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_pre_ping=settings.db_pool_pre_ping,
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    },
)


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Request-scoped database session
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide one SQLAlchemy session per request.

    Transaction ownership belongs to this dependency.

    Successful request:
        commit

    Failed request:
        rollback

    Session is always closed by the async context manager.
    """

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()

        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Database health check
# ---------------------------------------------------------------------------

async def check_database_connection() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


# ---------------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------------

async def create_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Database shutdown
# ---------------------------------------------------------------------------

async def close_database() -> None:
    await engine.dispose()