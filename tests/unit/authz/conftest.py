import pytest
import pytest_asyncio
import sqlalchemy
from sqlalchemy import orm as sqla_orm
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex.authz import schema as authz_schema
from soliplex.config import installation as config_installation


@pytest.fixture
def the_engine():
    engine = sqlalchemy.create_engine(
        config_installation.SYNC_MEMORY_ENGINE_URL,
    )

    yield engine

    engine.dispose()


@pytest.fixture
def the_session(the_engine):
    with the_engine.connect() as connection:
        authz_schema.Base.metadata.create_all(connection)

    assert connection.closed

    with sqla_orm.Session(bind=the_engine) as session:
        yield session


@pytest_asyncio.fixture()
async def the_async_engine():  # pragma: NO COVER
    engine = sqla_asyncio.create_async_engine(
        config_installation.ASYNC_MEMORY_ENGINE_URL,
    )
    async with engine.begin() as connection:
        await connection.run_sync(authz_schema.Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture()
async def the_async_session(the_async_engine):  # pragma: NO COVER
    session = sqla_asyncio.AsyncSession(bind=the_async_engine)
    yield session
    await session.close()
