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


@pytest.fixture(autouse=True)
def _clean_aws_environ(monkeypatch):
    """Strip any pre-existing AWS env vars so tests run hermetically.

    Real dev environments may have AWS_PROFILE / AWS_REGION set, which
    would otherwise contaminate the .env bridging assertions.
    """
    for key in aws_credentials._BRIDGED_AWS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


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


def test_resolve_aws_storage_options_bridges_extra_env(monkeypatch):
    """AWS_* values from extra_env (e.g. installation '.env') are
    promoted into os.environ so botocore's EnvProvider and lance's S3
    backend can both see them. Returns whatever botocore then resolves.
    """
    # Pretend botocore's chain finds nothing — we just want to verify
    # that the bridge happened so lance itself can read the env.
    fake_session = _fake_session(creds=None)
    monkeypatch.setattr(
        "botocore.session.get_session",
        lambda: fake_session,
    )

    aws_credentials.resolve_aws_storage_options(
        extra_env={
            "AWS_ACCESS_KEY_ID": "FROM_DOTENV_AK",
            "AWS_SECRET_ACCESS_KEY": "FROM_DOTENV_SK",
            "AWS_REGION": "eu-west-1",
            "UNRELATED": "ignored",
        }
    )

    import os

    assert os.environ["AWS_ACCESS_KEY_ID"] == "FROM_DOTENV_AK"
    assert os.environ["AWS_SECRET_ACCESS_KEY"] == "FROM_DOTENV_SK"
    assert os.environ["AWS_REGION"] == "eu-west-1"
    assert "UNRELATED" not in os.environ


def test_resolve_aws_storage_options_does_not_overwrite_existing_env(
    monkeypatch,
):
    """Pre-existing os.environ values (set by the shell that launched
    the server) always win over .env-supplied values.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "FROM_SHELL")

    fake_session = _fake_session(creds=None)
    monkeypatch.setattr(
        "botocore.session.get_session",
        lambda: fake_session,
    )

    aws_credentials.resolve_aws_storage_options(
        extra_env={"AWS_ACCESS_KEY_ID": "FROM_DOTENV"},
    )

    import os

    assert os.environ["AWS_ACCESS_KEY_ID"] == "FROM_SHELL"


def test_region_falls_back_to_AWS_REGION_env(monkeypatch):
    """botocore.session.get_config_variable('region') only reads
    AWS_DEFAULT_REGION; AWS_REGION (the var that boto3 + lance + most
    AWS SDKs use) must be picked up too, otherwise lance often fails
    with "Bucket not found" even with valid credentials.
    """
    monkeypatch.setenv("AWS_REGION", "us-east-2")

    frozen = _fake_frozen("AK", "SK")
    creds = mock.Mock()
    creds.get_frozen_credentials.return_value = frozen
    fake_session = _fake_session(creds=creds, region=None)
    monkeypatch.setattr(
        "botocore.session.get_session",
        lambda: fake_session,
    )

    result = aws_credentials.resolve_aws_storage_options()
    assert result["region"] == "us-east-2"


def test_region_falls_back_to_AWS_DEFAULT_REGION_env(monkeypatch):
    """If only AWS_DEFAULT_REGION is set and botocore's session lookup
    returns None for some reason, our explicit fallback still finds it.
    """
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-northeast-1")

    frozen = _fake_frozen("AK", "SK")
    creds = mock.Mock()
    creds.get_frozen_credentials.return_value = frozen
    fake_session = _fake_session(creds=creds, region=None)
    monkeypatch.setattr(
        "botocore.session.get_session",
        lambda: fake_session,
    )

    result = aws_credentials.resolve_aws_storage_options()
    assert result["region"] == "ap-northeast-1"


def test_region_from_session_takes_precedence(monkeypatch):
    """When botocore's session-level lookup finds a region (e.g. from
    AWS_DEFAULT_REGION or profile config), it wins over our os.environ
    fallback.
    """
    monkeypatch.setenv("AWS_REGION", "us-east-2")  # fallback value

    frozen = _fake_frozen("AK", "SK")
    creds = mock.Mock()
    creds.get_frozen_credentials.return_value = frozen
    fake_session = _fake_session(creds=creds, region="eu-west-1")
    monkeypatch.setattr(
        "botocore.session.get_session",
        lambda: fake_session,
    )

    result = aws_credentials.resolve_aws_storage_options()
    assert result["region"] == "eu-west-1"


def test_bridge_aws_env_to_environ_returns_set_keys(monkeypatch):
    """The bridging helper returns the keys it actually set, for
    logging visibility.
    """
    monkeypatch.setenv("AWS_REGION", "us-east-1")  # already set

    bridged = aws_credentials._bridge_aws_env_to_environ(
        {
            "AWS_ACCESS_KEY_ID": "AK",
            "AWS_REGION": "eu-west-1",  # skipped (already in environ)
            "AWS_PROFILE": "myprofile",
        }
    )

    assert sorted(bridged) == ["AWS_ACCESS_KEY_ID", "AWS_PROFILE"]
