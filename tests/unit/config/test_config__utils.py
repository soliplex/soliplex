import contextlib
import pathlib
from unittest import mock

import pytest

from soliplex.config import _utils as config__utils
from soliplex.config import exceptions as config_exc
from soliplex.config import installation as config_installation


@mock.patch("importlib.import_module")
def test__from_dotted_name(im):
    dotted_name = "somemodule.SomeClass"

    faux_module = im.return_value = mock.Mock()

    klass = config__utils._from_dotted_name(dotted_name)

    assert klass is faux_module.SomeClass


def test__load_config_yaml_w_missing(temp_dir):
    config_path = temp_dir / "oidc"
    config_path.mkdir()
    missing_cfg = config_path / "config.yaml"

    with pytest.raises(config_exc.NoSuchConfig) as exc:
        config_installation._load_config_yaml(missing_cfg)

    assert exc.value._config_path == missing_cfg


@pytest.mark.parametrize(
    "invalid",
    [
        b"\xde\xad\xbe\xef",  # raises UnicodeDecodeError
        "",  # parses as None
        "123",  # parses as int
        "4.56",  # parses as float
        '"foo"',  # parses as str
        '- "abc"\n- "def"',  # parses as list of str
    ],
)
def test__load_config_yaml_w_invalid(temp_dir, invalid):
    config_path = temp_dir / "oidc"
    config_path.mkdir()
    invalid_cfg = config_path / "config.yaml"

    if isinstance(invalid, bytes):
        invalid_cfg.write_bytes(invalid)
    else:
        invalid_cfg.write_text(invalid)

    with pytest.raises(config_exc.FromYamlException) as exc:
        config_installation._load_config_yaml(invalid_cfg)

    assert exc.value._config_path == invalid_cfg


def test__find_configs_yaml_w_single(temp_dir):
    THING_ID = "testing"
    CONFIG_FILENAME = "config.yaml"
    to_search = temp_dir / "to_search"
    to_search.mkdir()
    config_file = to_search / CONFIG_FILENAME
    config_file.write_text(f"id: {THING_ID}")
    expected = {"id": THING_ID}

    found = list(
        config_installation._find_configs_yaml(to_search, CONFIG_FILENAME)
    )

    assert found == [(config_file, expected)]


def test__find_configs_w_multiple(temp_dir):
    THING_IDS = ["foo", "bar", "baz", "qux"]
    CONFIG_FILENAME = "config.yaml"

    expected_things = []

    for thing_id in sorted(THING_IDS):
        thing_path = temp_dir / thing_id
        if thing_id == "baz":  # file, not dir
            thing_path.write_text("DEADBEEF")
        elif thing_id == "qux":  # empty dir
            thing_path.mkdir()
        else:
            thing_path.mkdir()
            config_file = thing_path / CONFIG_FILENAME
            config_file.write_text(f"id: {thing_id}")
            expected_thing = {"id": thing_id}
            expected_things.append((config_file, expected_thing))

    found_things = list(
        config_installation._find_configs_yaml(temp_dir, CONFIG_FILENAME)
    )

    for (f_key, f_thing), (e_key, e_thing) in zip(
        sorted(found_things),
        sorted(expected_things),
        strict=True,
    ):
        assert f_key == e_key
        assert f_thing == e_thing


@pytest.mark.parametrize(
    "config_value, expected",
    [
        ("no_prefix", "no_prefix"),
        ("file:test.foo", "{temp_dir}/test.foo"),
        (1234, 1234),
    ],
)
def test_resolve_file_prefix(temp_dir, config_value, expected):
    config_path = temp_dir / "config.yaml"

    if isinstance(expected, str):
        expected = str(
            pathlib.Path(expected.format(temp_dir=temp_dir.resolve()))
        )

    found = config_installation.resolve_file_prefix(config_value, config_path)

    assert found == expected


@pytest.mark.parametrize(
    "env_name, env_value, dotenv_env, osenv_patch, expectation",
    [
        (
            "ENVVAR",
            None,
            {},
            {},
            pytest.raises(config_installation.MissingEnvVar),
        ),
        (
            "ENVVAR",
            None,
            {"ENVVAR": "dotenv"},
            {},
            contextlib.nullcontext("dotenv"),
        ),
        (
            "ENVVAR",
            None,
            {},
            {"ENVVAR": "osenv"},
            contextlib.nullcontext("osenv"),
        ),
        (
            "ENVVAR",
            None,
            {"ENVVAR": "dotenv"},
            {"ENVVAR": "osenv"},
            contextlib.nullcontext("dotenv"),  # dotenv_env wins
        ),
        (
            "ENVVAR",
            "baz",
            {},
            {},
            contextlib.nullcontext("baz"),
        ),
        (
            "ENVVAR",
            "baz",
            {"ENVVAR": "dotenv"},
            {},
            contextlib.nullcontext("baz"),
        ),
        (
            "ENVVAR",
            "baz",
            {},
            {"ENVVAR": "osenv"},
            contextlib.nullcontext("baz"),
        ),
        (
            "ENVVAR",
            "baz",
            {"ENVVAR": "dotenv"},
            {"ENVVAR": "osenv"},
            contextlib.nullcontext("baz"),
        ),
    ],
)
def test_resolve_environment_entry(
    env_name,
    env_value,
    dotenv_env,
    osenv_patch,
    expectation,
):
    with (
        mock.patch.dict("os.environ", **osenv_patch),
        expectation as expected,
    ):
        found = config_installation.resolve_environment_entry(
            env_name,
            env_value,
            dotenv_env,
        )

    if isinstance(expected, str):
        assert found == expected

    else:
        assert expected.value.env_var == "ENVVAR"
