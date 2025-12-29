from unittest import mock

import fastapi
import pytest

from soliplex import config
from soliplex.views import installation as installation_views


@pytest.mark.anyio
@mock.patch("soliplex.models.Installation.from_config")
@mock.patch("soliplex.auth.authenticate")
async def test_get_installation(auth_fn, fc):
    from soliplex import installation

    request = mock.create_autospec(fastapi.Request)

    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)
    token = object()

    found = await installation_views.get_installation(
        request,
        the_installation=the_installation,
        token=token,
    )

    assert found is fc.return_value

    fc.assert_called_once_with(i_config)
    auth_fn.assert_called_once_with(the_installation, token)
