from __future__ import annotations

from unittest import mock

import pytest

from soliplex.cli.audit import oidc as audit_oidc
from tests.unit.cli.audit import audit_helpers


@pytest.mark.parametrize(
    "w_cfg_id_and_error, exp_invalid_ids",
    [
        ([], []),
        ([("alpha", False)], []),
        ([("alpha", True)], ["alpha"]),
        ([("alpha", False), ("beta", True)], ["beta"]),
        ([("alpha", True), ("beta", True)], ["alpha", "beta"]),
    ],
)
@mock.patch("soliplex.models.OIDCAuthSystem.from_config")
def test__invalid_oidc_auth_providers(
    moafc,
    the_installation,
    w_cfg_id_and_error,
    exp_invalid_ids,
):
    oidc_configs = []
    side_effects = []
    for cfg_id, has_error in w_cfg_id_and_error:
        cfg = mock.Mock()
        cfg.id = cfg_id
        oidc_configs.append(cfg)
        side_effects.append(
            audit_helpers.ModelException() if has_error else None
        )

    the_installation._config.oidc_auth_system_configs = oidc_configs
    moafc.side_effect = side_effects

    found = audit_oidc._invalid_oidc_auth_providers(the_installation)

    if exp_invalid_ids:
        assert found == {
            "oidc": {
                cid: audit_helpers.TESTING_MODEL_ERROR
                for cid in exp_invalid_ids
            },
        }
    else:
        assert found == {}

    assert moafc.call_args_list == [mock.call(cfg) for cfg in oidc_configs]


# _audit_oidc_section: ui only
# audit_oidc_auth_providers: command
