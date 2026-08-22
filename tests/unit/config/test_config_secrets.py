import contextlib
import copy
import dataclasses
import typing
from unittest import mock

import pytest

from soliplex import secrets
from soliplex.config import exceptions as config_exc
from soliplex.config import secrets as config_secrets

NoRaise = contextlib.nullcontext()
NotASecret = pytest.raises(config_secrets.NotASecret)
ExcGroup = pytest.raises(ExceptionGroup)


SECRET_NAME = "TEST_SECRET"
SECRET_VALUE = "DEADBEEF"
SECRET_FILE_PATH = "./very_seekrit"
ENV_VAR_NAME = "TEST_ENV_VAR"
COMMAND = "cat"
ERROR_MISS = object()

SECRET_NAME_1 = "TEST_SECRET"
SECRET_NAME_2 = "OTHER_SECRET"
SECRET_CONFIG_1 = config_secrets.SecretConfig(secret_name=SECRET_NAME_1)
SECRET_CONFIG_2 = config_secrets.SecretConfig(secret_name=SECRET_NAME_2)
ENV_VAR_MISS = config_secrets.EnvVarSecretSource(
    secret_name=SECRET_NAME,
    env_var_name="NONESUCH",
)
ENV_VAR_HIT = config_secrets.EnvVarSecretSource(
    secret_name=SECRET_NAME,
    env_var_name=ENV_VAR_NAME,
)


@dataclasses.dataclass(kw_only=True)
class _NoGetterSecretSource(config_secrets._BaseSecretSource):
    """A source kind registered without its getter.

    Reachable via 'meta.secret_sources' alone: registering a source class
    does not register anything in 'SECRET_GETTERS_BY_KIND'.
    """

    kind: typing.ClassVar[str] = "no_getter"
    secret_name: str

    @property
    def extra_arguments(self) -> dict:  # pragma: NO COVER (never dumped)
        return {}


NO_GETTER = _NoGetterSecretSource(secret_name=SECRET_NAME)


@pytest.mark.parametrize(
    "w_params, exp_env_var_name",
    [
        ({}, SECRET_NAME),
        ({"env_var_name": ENV_VAR_NAME}, ENV_VAR_NAME),
    ],
)
def test_envvarsecretsource_ctor(w_params, exp_env_var_name):
    source = config_secrets.EnvVarSecretSource(
        secret_name=SECRET_NAME, **w_params
    )

    assert source.env_var_name == exp_env_var_name
    assert source.extra_arguments == {"env_var_name": exp_env_var_name}


@pytest.mark.parametrize(
    "w_kind_kw, expectation",
    [
        ({}, contextlib.nullcontext()),
        (
            {"kind": config_secrets.EnvVarSecretSource.kind},
            contextlib.nullcontext(),
        ),
        (
            {"kind": "BOGUS"},
            pytest.raises(config_exc.FromYamlException),
        ),
    ],
)
@pytest.mark.parametrize("yaml_config", [{}, {"env_var_name": ENV_VAR_NAME}])
def test_envvarsecretsource_from_yaml(
    temp_dir,
    yaml_config,
    w_kind_kw,
    expectation,
):
    config_path = temp_dir / "installation.yaml"
    yaml_config["secret_name"] = SECRET_NAME

    with expectation as expected:
        source = config_secrets.EnvVarSecretSource.from_yaml(
            config_path, yaml_config | w_kind_kw
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert source._config_path == config_path
        assert source.secret_name == SECRET_NAME

        exp_env_var_name = (
            ENV_VAR_NAME if "env_var_name" in yaml_config else SECRET_NAME
        )

        assert source.env_var_name == exp_env_var_name
        assert source.extra_arguments == {"env_var_name": exp_env_var_name}


@pytest.mark.parametrize("has_ev", [False, True])
def test_envvarsecretsource_as_yaml(has_ev):
    config_kw = {"secret_name": SECRET_NAME}

    if has_ev:
        config_kw["env_var_name"] = ENV_VAR_NAME

    source = config_secrets.EnvVarSecretSource(**config_kw)

    expected = {
        "kind": config_secrets.EnvVarSecretSource.kind,
        "secret_name": SECRET_NAME,
        "env_var_name": ENV_VAR_NAME if has_ev else SECRET_NAME,
    }

    found = source.as_yaml

    assert found == expected


def _round_trip_secret_source(source_class, config_path, config_dict):
    """Reload a secret source from its own dump.

    'from_yaml' pops 'kind' out of the mapping it is handed, hence the
    copies.
    """
    original = source_class.from_yaml(
        config_path,
        copy.deepcopy(config_dict),
    )
    reloaded = source_class.from_yaml(
        config_path,
        copy.deepcopy(original.as_yaml),
    )

    return original, reloaded


@pytest.mark.parametrize("w_params", [{}, {"env_var_name": ENV_VAR_NAME}])
def test_envvarsecretsource_as_yaml_round_trips(temp_dir, w_params):
    config_dict = {"secret_name": SECRET_NAME} | w_params

    original, reloaded = _round_trip_secret_source(
        config_secrets.EnvVarSecretSource,
        temp_dir / "installation.yaml",
        config_dict,
    )

    assert reloaded == original


@pytest.mark.parametrize(
    "w_kind_kw, expectation",
    [
        ({}, contextlib.nullcontext()),
        (
            {"kind": config_secrets.FilePathSecretSource.kind},
            contextlib.nullcontext(),
        ),
        (
            {"kind": "BOGUS"},
            pytest.raises(config_exc.FromYamlException),
        ),
    ],
)
@pytest.mark.parametrize("file_path", ["/path/to/file", "./file"])
def test_filepathsecretsource_from_yaml(
    temp_dir,
    file_path,
    w_kind_kw,
    expectation,
):
    config_path = temp_dir / "installation.yaml"
    yaml_config = {"secret_name": SECRET_NAME, "file_path": file_path}

    with expectation as expected:
        source = config_secrets.FilePathSecretSource.from_yaml(
            config_path, yaml_config | w_kind_kw
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert source._config_path == config_path
        assert source.secret_name == SECRET_NAME
        assert source.file_path == file_path
        assert source.extra_arguments == {"file_path": file_path}


def test_filepathsecretsource_as_yaml():
    config_kw = {
        "secret_name": SECRET_NAME,
        "file_path": SECRET_FILE_PATH,
    }

    source = config_secrets.FilePathSecretSource(**config_kw)

    expected = {
        "kind": config_secrets.FilePathSecretSource.kind,
        "secret_name": SECRET_NAME,
        "file_path": SECRET_FILE_PATH,
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize("file_path", ["/path/to/file", "./file"])
def test_filepathsecretsource_as_yaml_round_trips(temp_dir, file_path):
    config_dict = {"secret_name": SECRET_NAME, "file_path": file_path}

    original, reloaded = _round_trip_secret_source(
        config_secrets.FilePathSecretSource,
        temp_dir / "installation.yaml",
        config_dict,
    )

    assert reloaded == original


@pytest.mark.parametrize(
    "w_kind_kw, expectation",
    [
        ({}, contextlib.nullcontext()),
        (
            {"kind": config_secrets.SubprocessSecretSource.kind},
            contextlib.nullcontext(),
        ),
        (
            {"kind": "BOGUS"},
            pytest.raises(config_exc.FromYamlException),
        ),
    ],
)
@pytest.mark.parametrize(
    "command, args",
    [
        ("/bin/true", ()),
        ("/bin/ls", ("-laF",)),
    ],
)
def test_subprocesssecretsource_from_yaml(
    temp_dir,
    command,
    args,
    w_kind_kw,
    expectation,
):
    config_path = temp_dir / "installation.yaml"
    yaml_config = {"secret_name": SECRET_NAME, "command": command}

    if args:
        exp_args = yaml_config["args"] = args
        exp_command_line = f"{command} {' '.join(args)}"
    else:
        exp_args = ()
        exp_command_line = command

    with expectation as expected:
        source = config_secrets.SubprocessSecretSource.from_yaml(
            config_path,
            yaml_config | w_kind_kw,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert source._config_path == config_path
        assert source.secret_name == SECRET_NAME
        assert source.command == command
        assert source.args == exp_args
        assert source.extra_arguments == {"command_line": exp_command_line}


@pytest.mark.parametrize(
    "w_args",
    [
        (),
        ["-a", "foo"],
    ],
)
def test_subprocesssecretsource_as_yaml(w_args):
    config_kw = {
        "secret_name": SECRET_NAME,
        "command": COMMAND,
        "args": w_args,
    }

    source = config_secrets.SubprocessSecretSource(**config_kw)

    expected = {
        "kind": config_secrets.SubprocessSecretSource.kind,
        "secret_name": SECRET_NAME,
        "command": COMMAND,
        "args": list(w_args),
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize("w_args", [None, [], ["-a", "foo"]])
def test_subprocesssecretsource_as_yaml_round_trips(temp_dir, w_args):
    config_dict = {"secret_name": SECRET_NAME, "command": COMMAND}

    if w_args is not None:
        config_dict["args"] = w_args

    original, reloaded = _round_trip_secret_source(
        config_secrets.SubprocessSecretSource,
        temp_dir / "installation.yaml",
        config_dict,
    )

    # Not 'reloaded == original': 'as_yaml' emits 'list(self.args)', so a
    # defaulted '()' comes back as '[]'. 'get_subprocess_secret' only ever
    # splats it ('[source.command, *source.args]'), so 'command_line' is
    # the state that matters, and it is equal either way.
    assert reloaded.secret_name == original.secret_name
    assert reloaded.command == original.command
    assert reloaded.command_line == original.command_line
    assert reloaded.extra_arguments == original.extra_arguments


@pytest.mark.parametrize(
    "w_kind_kw, expectation",
    [
        ({}, contextlib.nullcontext()),
        (
            {"kind": config_secrets.RandomCharsSecretSource.kind},
            contextlib.nullcontext(),
        ),
        (
            {"kind": "BOGUS"},
            pytest.raises(config_exc.FromYamlException),
        ),
    ],
)
@pytest.mark.parametrize(
    "kwargs, exp_nc",
    [
        ({}, 32),
        ({"n_chars": 17}, 17),
    ],
)
def test_randomsharssecretsource_from_yaml(
    temp_dir,
    kwargs,
    exp_nc,
    w_kind_kw,
    expectation,
):
    config_path = temp_dir / "installation.yaml"
    yaml_config = {"secret_name": SECRET_NAME} | kwargs

    with expectation as expected:
        source = config_secrets.RandomCharsSecretSource.from_yaml(
            config_path,
            yaml_config | w_kind_kw,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert source._config_path == config_path
        assert source.secret_name == SECRET_NAME
        assert source.n_chars == exp_nc
        assert source.extra_arguments == {"n_chars": exp_nc}


@pytest.mark.parametrize(
    "kwargs, exp_nc",
    [
        ({}, 32),
        ({"n_chars": 17}, 17),
    ],
)
def test_randomcharssecretsource_as_yaml(kwargs, exp_nc):
    source = config_secrets.RandomCharsSecretSource(
        secret_name=SECRET_NAME, **kwargs
    )

    expected = {
        "kind": config_secrets.RandomCharsSecretSource.kind,
        "secret_name": SECRET_NAME,
        "n_chars": exp_nc,
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize("w_params", [{}, {"n_chars": 17}])
def test_randomcharssecretsource_as_yaml_round_trips(temp_dir, w_params):
    config_dict = {"secret_name": SECRET_NAME} | w_params

    original, reloaded = _round_trip_secret_source(
        config_secrets.RandomCharsSecretSource,
        temp_dir / "installation.yaml",
        config_dict,
    )

    assert reloaded == original


@pytest.mark.parametrize(
    "w_sources, exp_sources",
    [
        (None, [config_secrets.EnvVarSecretSource(secret_name=SECRET_NAME)]),
        (
            [
                config_secrets.EnvVarSecretSource(
                    secret_name=SECRET_NAME,
                    env_var_name=ENV_VAR_NAME,
                ),
            ],
            None,
        ),
    ],
)
def test_secretconfig_ctor(w_sources, exp_sources):
    if exp_sources is None:
        exp_sources = w_sources

    secret = config_secrets.SecretConfig(
        secret_name=SECRET_NAME, sources=w_sources
    )

    assert secret.secret_name == SECRET_NAME
    assert secret.sources == exp_sources


def test_secretconfig_as_yaml():
    source_1 = mock.Mock(spec_set=["as_yaml"])
    source_2 = mock.Mock(spec_set=["as_yaml"])
    secret = config_secrets.SecretConfig(
        secret_name=SECRET_NAME,
        sources=[source_1, source_2],
    )

    expected = {
        "secret_name": SECRET_NAME,
        "sources": [
            source_1.as_yaml,
            source_2.as_yaml,
        ],
    }
    found = secret.as_yaml

    assert found == expected


def _round_trip_secret_config(config_path, config):
    """Reload a 'SecretConfig' from its own dump.

    'from_yaml' drains 'sources' out of the mapping it is handed, hence
    the copies.
    """
    klass = config_secrets.SecretConfig
    original = klass.from_yaml(config_path, copy.deepcopy(config))
    reloaded = klass.from_yaml(config_path, copy.deepcopy(original.as_yaml))

    return original, reloaded


# 'args' is spelled explicitly so the whole-object comparison is fair: a
# defaulted '()' would dump as '[]' (see the subprocess round-trip above).
FULL_SECRET_CONFIG = {
    "secret_name": SECRET_NAME,
    "sources": [
        {"kind": "env_var", "env_var_name": ENV_VAR_NAME},
        {"kind": "file_path", "file_path": SECRET_FILE_PATH},
        {"kind": "subprocess", "command": COMMAND, "args": ["-a", "foo"]},
        {"kind": "random_chars", "n_chars": 17},
    ],
}


@pytest.mark.parametrize(
    "config",
    [
        # the bare-string shorthand
        SECRET_NAME,
        {"secret_name": SECRET_NAME, "sources": [{"kind": "env_var"}]},
        FULL_SECRET_CONFIG,
    ],
)
def test_secretconfig_as_yaml_round_trips(temp_dir, config):
    # The string shorthand does not dump back to a string, but it does
    # reach the same state: one 'env_var' source named for the secret.
    original, reloaded = _round_trip_secret_config(
        temp_dir / "installation.yaml",
        config,
    )

    assert reloaded == original


def test_secretconfig_resolved():
    secret = config_secrets.SecretConfig(secret_name=SECRET_NAME)

    assert secret.resolved is None
    secret._resolved = SECRET_VALUE
    assert secret.resolved == SECRET_VALUE


@pytest.mark.parametrize(
    "config_str, expectation, expected",
    [
        ("secret:test", NoRaise, "test"),
        ("invalid", NotASecret, None),
    ],
)
def test_strip_secret_prefix(config_str, expectation, expected):
    with expectation:
        found = config_secrets.strip_secret_prefix(config_str)

    if expected is not None:
        assert found == expected


@pytest.mark.parametrize(
    "sources, expectation, expected",
    [
        ([ENV_VAR_MISS], ExcGroup, ERROR_MISS),
        ([ENV_VAR_MISS, ENV_VAR_HIT], NoRaise, SECRET_VALUE),
        ([NO_GETTER], ExcGroup, ERROR_MISS),
        ([NO_GETTER, ENV_VAR_HIT], NoRaise, SECRET_VALUE),
    ],
)
@mock.patch("os.urandom")
def test_get_secret_secret_ctor_w_sources(
    o_ur,
    sources,
    expectation,
    expected,
):
    secret_config = config_secrets.SecretConfig(
        secret_name=SECRET_NAME,
        sources=sources,
    )

    env_patch = {ENV_VAR_NAME: SECRET_VALUE}

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        with expectation:
            found = config_secrets.get_secret(secret_config)

    if expected is not ERROR_MISS:
        assert found == expected


def test_get_secret_w_source_kind_wo_registered_getter():
    secret_config = config_secrets.SecretConfig(
        secret_name=SECRET_NAME,
        sources=[NO_GETTER],
    )

    with pytest.raises(ExceptionGroup) as exc_info:
        config_secrets.get_secret(secret_config)

    (inner,) = exc_info.value.exceptions
    assert isinstance(inner, secrets.NoGetterForSecretSourceKind)
    assert inner.kind == _NoGetterSecretSource.kind
    assert inner.secret_name == SECRET_NAME


@pytest.mark.parametrize(
    "secret_configs, expectation",
    [
        ((), NoRaise),
        ([SECRET_CONFIG_1], ExcGroup),
        ([SECRET_CONFIG_1, SECRET_CONFIG_2], ExcGroup),
    ],
)
@mock.patch("soliplex.config.secrets.get_secret")
def test_resolve_secrets(gs, secret_configs, expectation):
    gs.side_effect = secrets.SecretError("testing")

    with mock.patch("os.environ", clear=True):
        with expectation as expected:
            config_secrets.resolve_secrets(secret_configs)

    if expected is not None:
        assert len(expected.value.exceptions) == len(secret_configs)

        for secret_config, gs_call in zip(
            secret_configs,
            gs.call_args_list,
            strict=True,
        ):
            assert gs_call == mock.call(secret_config)
