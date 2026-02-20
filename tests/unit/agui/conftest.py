import pytest
import sqlalchemy
from sqlalchemy import orm as sqla_orm

from soliplex import config
from soliplex.agui import schema as agui_schema


@pytest.fixture
def the_engine():
    engine = sqlalchemy.create_engine(config.SYNC_MEMORY_ENGINE_URL)

    yield engine

    engine.dispose()


@pytest.fixture
def the_session(the_engine):
    with the_engine.connect() as connection:
        agui_schema.Base.metadata.create_all(connection)

    assert connection.closed

    with sqla_orm.Session(bind=the_engine) as session:
        yield session
