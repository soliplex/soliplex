from __future__ import annotations

from unittest import mock

import pytest

from soliplex.cli.audit import environment as audit_environment
from soliplex.config import installation as config_installation


@pytest.mark.parametrize(
    "w_missing",
    [
        None,
        ["ALPHA"],
        ["ALPHA", "BETA"],
    ],
)
@mock.patch("soliplex.installation.Installation.resolve_environment")
def test__missing_env_vars(
    resolve_environment,
    the_installation,
    w_missing,
):
    if w_missing is not None:
        resolve_environment.side_effect = (
            config_installation.MissingEnvVars.from_failed(
                w_missing,
                [ValueError()],
            )
        )

    found = audit_environment._missing_env_vars(the_installation)

    if w_missing is not None:
        assert found == {"missing_env_vars": w_missing}
    else:
        assert found == {}

    resolve_environment.assert_called_once_with()


# _audit_environment_section: ui only
# audit_environment: command
