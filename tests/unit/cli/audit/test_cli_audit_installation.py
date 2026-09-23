from __future__ import annotations

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


# _audit_installation_section: ui only
# audit_installation: command
