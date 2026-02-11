from unittest import mock

import pytest

from soliplex import installation
from soliplex import views


@pytest.mark.anyio
@mock.patch("soliplex.authn.authenticate")
async def test_get_the_user_claims(auth_fn):
    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    found = await views.get_the_user_claims(
        the_installation=the_installation,
        token=token,
    )

    assert found is auth_fn.return_value

    auth_fn.assert_called_once_with(
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.anyio
async def test_health_check():
    response = await views.health_check()

    assert response == "OK"
