import json
from unittest import mock

import fastapi
import pytest

from soliplex import config
from soliplex.views import installation as installation_views


@pytest.mark.anyio
@mock.patch("soliplex.models.Installation.from_config")
@mock.patch("soliplex.authn.authenticate")
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


@pytest.mark.anyio
@mock.patch("soliplex.views.installation.traceback")
@mock.patch("soliplex.views.installation.subprocess")
@mock.patch("soliplex.authn.authenticate")
async def test_get_installation_versions_w_error(auth_fn, sp, tb):
    sp.check_output.side_effect = ValueError("testing")

    request = mock.create_autospec(fastapi.Request)
    the_installation = object()
    token = object()

    def _check(exc):
        return exc.status_code == 500

    with pytest.raises(fastapi.HTTPException, check=_check) as exc:
        await installation_views.get_installation_versions(
            request,
            the_installation=the_installation,
            token=token,
        )

    assert exc.value.detail is tb.format_exc.return_value

    tb.format_exc.assert_called_once_with()
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@mock.patch("soliplex.views.installation.subprocess")
@mock.patch("soliplex.authn.authenticate")
async def test_get_installation_versions_wo_error(auth_fn, sp):
    pip_manifest = [
        {"name": "one-package", "version": "0.1.2"},
        {"name": "another-package", "version": "3.4.5", "extra": "blather"},
    ]
    expected = {
        "one-package": {
            "version": "0.1.2",
        },
        "another-package": {
            "version": "3.4.5",
            "extra": "blather",
        },
    }
    sp.check_output.return_value = json.dumps(pip_manifest).encode("utf8")

    request = mock.create_autospec(fastapi.Request)
    the_installation = object()
    token = object()

    found = await installation_views.get_installation_versions(
        request,
        the_installation=the_installation,
        token=token,
    )

    assert found == expected

    auth_fn.assert_called_once_with(the_installation, token)
