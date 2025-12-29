from contextlib import asynccontextmanager

import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest_asyncio.fixture(scope="function")
async def mock_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # SQLModel.metadata.create_all(engine)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


@asynccontextmanager
async def mock_session(engine):
    async with AsyncSession(engine) as session:
        try:
            # Begin a transaction within the session
            async with session.begin():
                yield session
        except Exception:
            # Rollback the transaction if an error occurs
            await session.rollback()
            raise
        finally:
            # Close the session, returning the connection to the pool
            await session.close()


def do_monkeypatch(monkeypatch, mock_engine):
    import soliplex.ingester.lib.config as cfg

    settings = cfg.get_settings()
    settings.doc_db_url = "sqlite+aiosqlite:///:memory:"
    monkeypatch.setattr(
        "soliplex.ingester.lib.models.get_session",
        lambda: mock_session(mock_engine),
    )
