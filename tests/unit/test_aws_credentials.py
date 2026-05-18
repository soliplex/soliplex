import sys
from unittest import mock

import pytest

from soliplex import aws_credentials


@pytest.fixture(autouse=True)
def _reset_session_cache():
    """Clear the cached botocore session between tests."""
    aws_credentials._SESSION = None
    yield
    aws_credentials._SESSION = None


def _fake_frozen(access_key, secret_key, token=None):
    return mock.Mock(
        access_key=access_key,
        secret_key=secret_key,
        token=token,
    )


def _fake_session(creds=None, region=None):
    session = mock.Mock()
    session.get_credentials.return_value = creds
    session.get_config_variable.return_value = region
    return session


def test_resolve_aws_storage_options_botocore_missing(monkeypatch):
    """If botocore can't be imported the resolver returns an empty dict."""
    monkeypatch.setitem(sys.modules, "botocore", None)
    monkeypatch.setitem(sys.modules, "botocore.session", None)

    assert aws_credentials.resolve_aws_storage_options() == {}


def test_resolve_aws_storage_options_no_credentials(monkeypatch):
    """When the provider chain yields no credentials, return {}."""
    fake_session = _fake_session(creds=None)
    monkeypatch.setattr(
        "botocore.session.get_session",
        lambda: fake_session,
    )

    assert aws_credentials.resolve_aws_storage_options() == {}


def test_resolve_aws_storage_options_static_creds_no_region(monkeypatch):
    """Static credentials with no region: key/secret only, no session
    token, no region key.
    """
    frozen = _fake_frozen("AK", "SK", token=None)
    creds = mock.Mock()
    creds.get_frozen_credentials.return_value = frozen
    fake_session = _fake_session(creds=creds, region=None)
    monkeypatch.setattr(
        "botocore.session.get_session",
        lambda: fake_session,
    )

    assert aws_credentials.resolve_aws_storage_options() == {
        "aws_access_key_id": "AK",
        "aws_secret_access_key": "SK",
    }


def test_resolve_aws_storage_options_session_token_and_region(monkeypatch):
    """Refreshable / STS / SSO credentials include the session token,
    region is forwarded when set.
    """
    frozen = _fake_frozen("AK", "SK", token="TOKEN")
    creds = mock.Mock()
    creds.get_frozen_credentials.return_value = frozen
    fake_session = _fake_session(creds=creds, region="us-west-2")
    monkeypatch.setattr(
        "botocore.session.get_session",
        lambda: fake_session,
    )

    assert aws_credentials.resolve_aws_storage_options() == {
        "aws_access_key_id": "AK",
        "aws_secret_access_key": "SK",
        "aws_session_token": "TOKEN",
        "region": "us-west-2",
    }


def test_resolve_aws_storage_options_caches_session(monkeypatch):
    """The botocore session is built lazily and reused across calls so
    its internal credential-provider cache (and RefreshableCredentials
    state) survives between accesses.
    """
    frozen = _fake_frozen("AK", "SK")
    creds = mock.Mock()
    creds.get_frozen_credentials.return_value = frozen
    fake_session = _fake_session(creds=creds)

    factory = mock.Mock(return_value=fake_session)
    monkeypatch.setattr("botocore.session.get_session", factory)

    aws_credentials.resolve_aws_storage_options()
    aws_credentials.resolve_aws_storage_options()
    aws_credentials.resolve_aws_storage_options()

    factory.assert_called_once()
    assert fake_session.get_credentials.call_count == 3
