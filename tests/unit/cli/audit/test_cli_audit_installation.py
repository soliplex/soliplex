from __future__ import annotations

import warnings
from unittest import mock

import pytest

from soliplex.cli.audit import installation as audit_installation
from tests.unit.cli.audit import audit_helpers


@pytest.mark.parametrize("w_error", [False, True])
@mock.patch("soliplex.models.Installation.from_config")
def test__invalid_installation(mifc, the_installation, w_error):
    if w_error:
        mifc.side_effect = audit_helpers.ModelException()

    found = audit_installation._invalid_installation(the_installation)

    if w_error:
        assert found == {
            "installation_model": audit_helpers.TESTING_MODEL_ERROR
        }
    else:
        assert found == {}

    mifc.assert_called_once_with(the_installation._config)


def _warning_message(message, category):
    return warnings.WarningMessage(
        message=category(message),
        category=category,
        filename="config.py",
        lineno=1,
    )


@pytest.mark.parametrize(
    "w_records, exp_errors",
    [
        ([], {}),
        (
            [
                _warning_message("old stanza", DeprecationWarning),
                _warning_message("odd value", UserWarning),
            ],
            {
                "config_warnings": [
                    {
                        "category": "DeprecationWarning",
                        "message": "old stanza",
                    },
                    {"category": "UserWarning", "message": "odd value"},
                ],
            },
        ),
    ],
)
def test__config_warnings(w_records, exp_errors):
    found = audit_installation._config_warnings(w_records)

    assert found == exp_errors


# _audit_installation_section: ui only
# audit_installation: command
