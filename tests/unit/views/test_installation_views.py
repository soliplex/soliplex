import json
from unittest import mock

import fastapi
import pytest

from soliplex import authz
from soliplex import config
from soliplex import installation
from soliplex import models
from soliplex.views import installation as installation_views

OLLAMA_BASE_URL = "http://ollama.example.com:11434"
TEST_MODEL_ONE = "test-model-one:1.2.3"
TEST_MODEL_TWO = "test-model-two:4.5.6"

GIT_HASH = "test-git-hash"
GIT_BRANCH = "test-git-branch"
GIT_TAG = "test-git-tag"


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@mock.patch("soliplex.models.Installation.from_config")
@mock.patch("soliplex.authn.authenticate")
async def test_get_installation(auth_fn, fc, w_admin_access):
    from soliplex import installation

    request = mock.create_autospec(fastapi.Request)

    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)
    the_authz_policy = mock.create_autospec(authz.AuthorizationPolicy)
    the_authz_policy.check_admin_access.return_value = w_admin_access

    token = object()

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await installation_views.get_installation(
                request,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                token=token,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == "Admin access required"

    else:
        found = await installation_views.get_installation(
            request,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            token=token,
        )

        assert found is fc.return_value

        fc.assert_called_once_with(i_config)

    the_authz_policy.check_admin_access.assert_awaited_once_with(
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@mock.patch("soliplex.views.installation.traceback")
@mock.patch("soliplex.views.installation.subprocess")
@mock.patch("soliplex.authn.authenticate")
async def test_get_installation_versions_w_error(auth_fn, sp, tb):
    sp.check_output.side_effect = ValueError("testing")

    request = mock.create_autospec(fastapi.Request)
    the_installation = object()
    the_authz_policy = mock.create_autospec(authz.AuthorizationPolicy)
    the_authz_policy.check_admin_access.return_value = True
    token = object()

    def _check(exc):
        return exc.status_code == 500

    with pytest.raises(fastapi.HTTPException, check=_check) as exc:
        await installation_views.get_installation_versions(
            request,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            token=token,
        )

    assert exc.value.detail is tb.format_exc.return_value

    tb.format_exc.assert_called_once_with()
    the_authz_policy.check_admin_access.assert_awaited_once_with(
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@mock.patch("soliplex.views.installation.subprocess")
@mock.patch("soliplex.authn.authenticate")
async def test_get_installation_versions_wo_error(auth_fn, sp, w_admin_access):
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
    the_authz_policy = mock.create_autospec(authz.AuthorizationPolicy)
    the_authz_policy.check_admin_access.return_value = w_admin_access
    token = object()

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await installation_views.get_installation_versions(
                request,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                token=token,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == "Admin access required"

    else:
        found = await installation_views.get_installation_versions(
            request,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            token=token,
        )

        assert found == expected

    the_authz_policy.check_admin_access.assert_awaited_once_with(
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_admin_access", [False, True])
@mock.patch("soliplex.authn.authenticate")
async def test_get_installation_providers(auth_fn, w_admin_access):
    PROVIDER_INFO = {
        config.LLMProviderType.OLLAMA: {
            OLLAMA_BASE_URL: set([TEST_MODEL_ONE, TEST_MODEL_TWO]),
        }
    }

    request = mock.create_autospec(fastapi.Request)
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.all_provider_info = PROVIDER_INFO
    the_authz_policy = mock.create_autospec(authz.AuthorizationPolicy)
    the_authz_policy.check_admin_access.return_value = w_admin_access
    token = object()

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await installation_views.get_installation_providers(
                request,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                token=token,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == "Admin access required"

    else:
        found = await installation_views.get_installation_providers(
            request,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            token=token,
        )

        assert found == PROVIDER_INFO

    the_authz_policy.check_admin_access.assert_awaited_once_with(
        auth_fn.return_value,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@mock.patch("soliplex.util.GitMetadata")
@mock.patch("soliplex.authn.authenticate")
async def test_get_installation_git_metadata(auth_fn, gm_klass):
    gm = gm_klass.return_value
    gm.git_hash = GIT_HASH
    gm.git_branch = GIT_BRANCH
    gm.git_tag = GIT_TAG

    request = mock.create_autospec(fastapi.Request)
    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    found = await installation_views.get_installation_git_metadata(
        request,
        the_installation=the_installation,
        token=token,
    )

    assert found == models.GitMetadata(
        git_hash=GIT_HASH,
        git_branch=GIT_BRANCH,
        git_tag=GIT_TAG,
    )

    auth_fn.assert_called_once_with(the_installation, token)
