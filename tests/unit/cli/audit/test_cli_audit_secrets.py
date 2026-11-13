from __future__ import annotations

from unittest import mock

import pytest

from soliplex import secrets
from soliplex.cli.audit import secrets as audit_secrets
from soliplex.config import secrets as config_secrets

SECRET_NAME = "TEST_SECRET"
OTHER_SECRET_NAME = "OTHER_SECRET"


def _resolved_secret_config(secret_name, source_klass):
    secret_config = config_secrets.SecretConfig(secret_name=secret_name)
    secret_config._resolved = "DEADBEEF"
    secret_config._resolved_by = source_klass(secret_name=secret_name)
    return secret_config


@pytest.mark.parametrize(
    "w_missing_secrets, exp_missing",
    [
        (None, None),
        ("alpha", ["alpha"]),
        ("alpha,beta", ["alpha", "beta"]),
    ],
)
@mock.patch("soliplex.installation.Installation.resolve_secrets")
def test__missing_secrets(
    resolve_secrets,
    the_installation,
    w_missing_secrets,
    exp_missing,
):
    if w_missing_secrets is not None:
        resolve_secrets.side_effect = secrets.SecretsNotFound(
            w_missing_secrets,
            [ValueError()],
        )

    found = audit_secrets._missing_secrets(the_installation)

    if exp_missing is not None:
        assert found == {"missing_secrets": exp_missing}
    else:
        assert found == {}

    resolve_secrets.assert_called_once_with()


@pytest.mark.parametrize(
    "w_source_klass, w_missing_names, expected",
    [
        (None, {SECRET_NAME}, "MISSING"),
        (config_secrets.EnvVarSecretSource, set(), "OK (env_var)"),
        (
            config_secrets.EnvVarSecretSource,
            {OTHER_SECRET_NAME},
            "OK (env_var)",
        ),
        (config_secrets.RandomCharsSecretSource, set(), "OK (random_chars)"),
    ],
)
def test__secret_status(w_source_klass, w_missing_names, expected):
    if w_source_klass is None:
        secret_config = config_secrets.SecretConfig(secret_name=SECRET_NAME)
    else:
        secret_config = _resolved_secret_config(SECRET_NAME, w_source_klass)

    found = audit_secrets._secret_status(secret_config, w_missing_names)

    assert found == expected


@pytest.mark.parametrize(
    "w_source_klasses, expected",
    [
        ([], []),
        ([None, config_secrets.EnvVarSecretSource], []),
        (
            [
                config_secrets.RandomCharsSecretSource,
                config_secrets.EnvVarSecretSource,
            ],
            [SECRET_NAME],
        ),
        (
            [
                config_secrets.RandomCharsSecretSource,
                config_secrets.RandomCharsSecretSource,
            ],
            [SECRET_NAME, OTHER_SECRET_NAME],
        ),
    ],
)
def test__ephemeral_secrets(the_installation, w_source_klasses, expected):
    secret_configs = []
    for secret_name, source_klass in zip(
        [SECRET_NAME, OTHER_SECRET_NAME], w_source_klasses, strict=False
    ):
        if source_klass is None:
            secret_configs.append(
                config_secrets.SecretConfig(secret_name=secret_name)
            )
        else:
            secret_configs.append(
                _resolved_secret_config(secret_name, source_klass)
            )
    the_installation._config.secrets = secret_configs

    found = audit_secrets._ephemeral_secrets(the_installation)

    assert found == expected


# _audit_secrets_section: ui only
# audit_secrets: command
