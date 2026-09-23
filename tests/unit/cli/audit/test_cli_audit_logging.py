from __future__ import annotations

import contextlib
from unittest import mock

import pytest
import yaml

from soliplex.cli.audit import logging as audit_logging

_MISSING_FILE = object()


@pytest.mark.parametrize(
    "w_yaml_content, expectation",
    [
        (None, contextlib.nullcontext(None)),
        ("version: 1", contextlib.nullcontext({"version": 1})),
        (
            "a: b\nc: d",
            contextlib.nullcontext({"a": "b", "c": "d"}),
        ),
        ("key: [unclosed", pytest.raises(yaml.YAMLError)),
        (_MISSING_FILE, pytest.raises(FileNotFoundError)),
    ],
)
def test__load_logging_config(
    tmp_path,
    the_installation,
    w_yaml_content,
    expectation,
):
    if w_yaml_content is None:
        the_installation._config.logging_config_file = None
    elif w_yaml_content is _MISSING_FILE:
        the_installation._config.logging_config_file = tmp_path / "nope.yaml"
    else:
        config_file = tmp_path / "logging.yaml"
        config_file.write_text(w_yaml_content)
        the_installation._config.logging_config_file = config_file

    with expectation as expected:
        found = audit_logging._load_logging_config(the_installation)

    if not isinstance(expected, pytest.ExceptionInfo):
        assert found == expected


@pytest.mark.parametrize(
    "w_exc, exp_errors",
    [
        (None, {}),
        (yaml.YAMLError("bad yaml"), {"logging": "bad yaml"}),
        (OSError("missing file"), {"logging": "missing file"}),
    ],
)
@mock.patch("soliplex.cli.audit.logging._load_logging_config")
def test__invalid_logging(
    load_logging_config,
    the_installation,
    w_exc,
    exp_errors,
):
    if w_exc is not None:
        load_logging_config.side_effect = w_exc

    found = audit_logging._invalid_logging(the_installation)

    assert found == exp_errors
    load_logging_config.assert_called_once_with(the_installation)


# _audit_logging_section: ui only
# audit_logging: command
