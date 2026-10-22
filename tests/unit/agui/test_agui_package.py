from unittest import mock

import fastapi
import pytest

from soliplex import agui


@pytest.mark.anyio
@mock.patch("soliplex.agui.persistence.ThreadStorage")
async def test_get_the_threads(ts_klass, fake_async_session):
    engine = object()
    request = fastapi.Request(scope={"type": "http"})
    request.state.threads_engine = engine

    counter = 0

    with mock.patch(
        "sqlalchemy.ext.asyncio.AsyncSession",
        new=fake_async_session.cls,
    ):
        async for the_threads in agui.get_the_threads(request):
            assert the_threads is ts_klass.return_value
            counter += 1

    assert counter == 1

    ts_klass.assert_called_once_with(fake_async_session.session)

    fake_async_session.cls.assert_called_once_with(bind=engine)
