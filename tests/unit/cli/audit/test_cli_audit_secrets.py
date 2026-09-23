from __future__ import annotations

from unittest import mock

import pytest

from soliplex import secrets
from soliplex.cli.audit import secrets as audit_secrets


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


# _audit_secrets_section: ui only
# audit_secrets: command
