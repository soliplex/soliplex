from unittest import mock

import fastapi
import pytest

from soliplex import authz as authz_package


@pytest.mark.anyio
@mock.patch("soliplex.authz.persistence.AuthorizationPolicy")
@mock.patch("sqlalchemy.ext.asyncio.AsyncSession")
async def test_get_the_authz_policy(as_klass, ap_klass):
    engine = object()
    request = fastapi.Request(scope={"type": "http"})
    request.state.authorization_engine = engine

    counter = 0

    async for the_authz_policy in authz_package.get_the_authz_policy(request):
        assert the_authz_policy is ap_klass.return_value
        counter += 1

    assert counter == 1

    ap_klass.assert_called_once_with(
        as_klass.return_value.__aenter__.return_value,
    )

    as_klass.assert_called_once_with(bind=engine)
