from unittest import mock

import fastapi
import pytest

from soliplex import authz as authz_package


@pytest.mark.anyio
@mock.patch("soliplex.authz.schema.RoomAuthorization")
@mock.patch("sqlalchemy.ext.asyncio.AsyncSession")
async def test_get_the_room_authz(as_klass, ra_klass):
    engine = object()
    request = fastapi.Request(scope={"type": "http"})
    request.state.room_authz_engine = engine

    counter = 0

    async for the_room_authz in authz_package.get_the_room_authz(request):
        assert the_room_authz is ra_klass.return_value
        counter += 1

    assert counter == 1

    ra_klass.assert_called_once_with(
        as_klass.return_value.__aenter__.return_value,
    )

    as_klass.assert_called_once_with(bind=engine)
