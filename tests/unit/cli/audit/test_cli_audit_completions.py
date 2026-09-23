from __future__ import annotations

from unittest import mock

import pytest

from soliplex.cli.audit import completions as audit_completions
from tests.unit.cli.audit import audit_helpers


@pytest.mark.parametrize(
    "w_compl_id_and_error, exp_invalid_ids",
    [
        ([], []),
        ([("c1", False)], []),
        ([("c1", True)], ["c1"]),
        ([("c1", False), ("c2", True)], ["c2"]),
        ([("c1", True), ("c2", True)], ["c1", "c2"]),
    ],
)
@mock.patch("soliplex.models.Completion.from_config")
def test__invalid_completions(
    mcfc,
    the_installation,
    w_compl_id_and_error,
    exp_invalid_ids,
):
    completion_configs = {}
    side_effects = []
    for compl_id, has_error in w_compl_id_and_error:
        cfg = mock.Mock()
        cfg.id = compl_id
        completion_configs[compl_id] = cfg
        side_effects.append(
            audit_helpers.ModelException() if has_error else None
        )

    the_installation._config.completion_configs = completion_configs
    mcfc.side_effect = side_effects

    found = audit_completions._invalid_completions(the_installation)

    if exp_invalid_ids:
        assert found == {
            "completions": {
                cid: audit_helpers.TESTING_MODEL_ERROR
                for cid in exp_invalid_ids
            },
        }
    else:
        assert found == {}

    assert mcfc.call_args_list == [
        mock.call(cfg) for cfg in completion_configs.values()
    ]


# _audit_completions_section: ui only
# audit_completions: command
