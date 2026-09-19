from __future__ import annotations

import contextlib
import dataclasses
import pathlib
from unittest import mock

import pytest
import requests
import sqlalchemy as sa
import typer
import yaml

from soliplex import authz
from soliplex import installation
from soliplex import models
from soliplex import secrets
from soliplex.cli import audit as cli_audit
from soliplex.cli import cli_util
from soliplex.config import installation as config_installation
from soliplex.config import interpolation as config_interp
from soliplex.config import quizzes as config_quizzes
from soliplex.config import rag as config_rag

TESTING_MODEL_ERROR = "testing model error"
TESTING_RAG_ERROR = "testing rag error"
TESTING_QUIZ_ERROR = "testing quiz error"
TESTING_SKILL_ERROR = "testing skill error"
TESTING_AUTHZ_DB_ERROR = "testing authz db error"

A_CONFIG_PATH = pathlib.Path("/tmp/installation.yaml")

CHAT_ROLE = installation.ProviderRole.CHAT
EMBEDDING_ROLE = installation.ProviderRole.EMBEDDING
RERANKING_ROLE = installation.ProviderRole.RERANKING

no_error_none = contextlib.nullcontext()


class ModelException(ValueError):
    def __init__(self):
        super().__init__(TESTING_MODEL_ERROR)


class RAGError(ValueError):
    def __init__(self):
        super().__init__(TESTING_RAG_ERROR)


class QuizError(ValueError):
    def __init__(self):
        super().__init__(TESTING_QUIZ_ERROR)


class SkillError(ValueError):
    def __init__(self):
        super().__init__(TESTING_SKILL_ERROR)


class AuthzDBError(OSError):
    """Stand-in for whatever the DB driver raises when it can't connect."""

    def __init__(self):
        super().__init__(TESTING_AUTHZ_DB_ERROR)


# The authz-DB readers prefix the exception type: a bare 'str(exc)' on e.g.
# the 'FileNotFoundError' asyncpg raises for a missing unix socket reads as
# a stray "[Errno 2] No such file or directory".
EXP_AUTHZ_DB_ERROR = f"AuthzDBError: {TESTING_AUTHZ_DB_ERROR}"

_RAM_DBURI = config_installation.ASYNC_MEMORY_ENGINE_URL
_FILE_DBURI = "sqlite+aiosqlite:///x.db"


class _OkRagCfg:
    haiku_rag_config = None
    rag_databases = ()
    rag_lancedb_path = None


class _ErrRagCfg:
    haiku_rag_config = None
    rag_databases = ()

    @property
    def rag_lancedb_path(self):
        raise RAGError()


class _NoDbRagCfg:
    """Exposes a haiku-rag config but names no database at all"""

    haiku_rag_config = None


class _DeferringRagCfg(_ErrRagCfg):
    """Leaves placement to its haiku.rag config, so has no path to probe"""

    names_own_databases = False


TESTING_RAG_UNBUILDABLE = (
    "lancedb.uri is not a thing; write lancedb.databases: {NAME: <location>}"
)


class _UnbuildableRagCfg(_ErrRagCfg):
    """A config whose haiku.rag configuration will not load

    Its database also fails to resolve, and only one of the two is the
    diagnosis an operator can act on.
    """

    @property
    def haiku_rag_config(self):
        raise ValueError(TESTING_RAG_UNBUILDABLE)


class _MultiRagCfg:
    """Names two databases, the second of which cannot be resolved"""

    class _Papers(_OkRagCfg):
        name = "papers"

    class _Wiki(_ErrRagCfg):
        name = "wiki"

    haiku_rag_config = None
    rag_databases = (_Papers(), _Wiki())


@pytest.fixture
def ctx():
    return mock.create_autospec(typer.Context, obj={})


@pytest.fixture
def installation_path(tmp_path):
    installation_path = tmp_path / "installation.yaml"
    installation_path.write_text("id: test")
    return installation_path


@pytest.fixture
def the_installation() -> installation.Installation:
    i_config = mock.create_autospec(config_installation.InstallationConfig)
    return installation.Installation(_config=i_config)


@pytest.mark.parametrize("w_quiet", [False, True])
@mock.patch("soliplex.cli.audit.the_console")
def test__quiet_console_funcs(the_console, w_quiet):
    found = cli_audit._quiet_console_funcs(w_quiet)

    (f_line, f_rule, f_print, f_print_exception) = found

    if w_quiet:
        assert f_line is cli_audit._noop
        assert f_rule is cli_audit._noop
        assert f_print is cli_audit._noop
        assert f_print_exception is cli_audit._noop
    else:
        assert f_line is the_console.line
        assert f_rule is the_console.rule
        assert f_print is the_console.print
        assert f_print_exception is the_console.print_exception


@pytest.mark.parametrize("w_quiet", [False, True])
@pytest.mark.parametrize("w_errors", [{}, {"foo": "bar"}])
@mock.patch("soliplex.cli.audit.the_console")
@mock.patch("sys.exit")
def test__emit_errors(
    sys_exit,
    the_console,
    w_errors,
    w_quiet,
):
    cli_audit._emit_errors(w_errors, w_quiet)

    if w_errors and w_quiet:
        the_console.print_json.assert_called_once_with(data=w_errors)
    else:
        the_console.print_json.assert_not_called()

    if w_errors:
        sys_exit.assert_called_once_with(1)
    else:
        sys_exit.assert_not_called()


@pytest.mark.parametrize("w_already", [False, True])
@mock.patch("soliplex.cli.cli_util.get_installation")
def test__get_installation(
    get_installation,
    ctx,
    installation_path,
    w_already,
):
    already = object()

    if w_already:
        ctx.obj["the_installation"] = already

    found = cli_audit._get_installation(ctx, installation_path)

    if w_already:
        assert found is already
        get_installation.assert_not_called()
    else:
        assert found is get_installation.return_value
        get_installation.assert_called_once_with(
            installation_path,
            auditing=True,
        )


# ---------------------------------------------------------------------------
# Interpolation findings
# ---------------------------------------------------------------------------

_SECRET = config_interp.MarkerKind.SECRET
_ENVIRONMENT = config_interp.MarkerKind.ENVIRONMENT
_BOTH = config_interp.MarkerKind.BOTH
_EMBEDDED = config_interp.MarkerArity.EMBEDDED
_SEQUENCE = config_interp.ValueShape.SEQUENCE
_MAPPING = config_interp.ValueShape.MAPPING

_UNDECLARED = cli_audit._InterpolationFindingCode.UNDECLARED_NAME
_IGNORED = cli_audit._InterpolationFindingCode.IGNORED_MARKER
_WRONG_KIND = cli_audit._InterpolationFindingCode.WRONG_KIND

_INTERP_CFG_NAME = f"{__name__}._InterpCfg"
_DERIVED_CFG_NAME = f"{__name__}._DerivedInterpCfg"

_DECLARED = cli_audit._InterpolationDeclarations(
    secrets=frozenset({"KNOWN_SECRET"}),
    environment=frozenset({"KNOWN_ENV"}),
)


@dataclasses.dataclass(kw_only=True)
class _InterpCfg:
    """Opt in to the checks by declaring interpolations of its own."""

    id: str | None = None
    _config_path: pathlib.Path | None = None

    secret_whole: str = config_interp.secret_whole_field(default="")
    secret_or_literal: str = config_interp.secret_whole_or_literal_field(
        default=""
    )
    env_embedded: str = config_interp.env_embedded_field(default="")
    dburi: str = config_interp.both_embedded_field(
        default="",
        public_name="public_dburi",
    )
    prose: str = config_interp.no_interpolation_field(default="")
    unannotated: str = ""
    args: list = config_interp.interpolated_field(
        kinds=_BOTH,
        arity=_EMBEDDED,
        shape=_SEQUENCE,
        default_factory=list,
    )
    env: dict = config_interp.interpolated_field(
        kinds=_BOTH,
        arity=_EMBEDDED,
        shape=_MAPPING,
        default_factory=dict,
    )


@dataclasses.dataclass(kw_only=True)
class _DerivedInterpCfg(_InterpCfg):
    """Declare no interpolation of its own: stay opted out."""

    extra: str = ""


@dataclasses.dataclass(kw_only=True)
class _DefaultMarkerCfg:
    """Hold markers as declared defaults, as 'LogfireConfig' does."""

    required: str = config_interp.secret_whole_field()
    env_default: str = config_interp.env_whole_or_literal_field(
        default="env:MISSING_ENV",
    )
    wrong_kind_default: str = config_interp.env_whole_or_literal_field(
        default="secret:MISSING",
    )


@dataclasses.dataclass(kw_only=True)
class _InterpQuizCfg:
    """Stand-in for 'QuizConfig': holds a judge agent."""

    id: str = "the-quiz"
    judge_agent: object = None


@dataclasses.dataclass(kw_only=True)
class _InterpRoomCfg:
    """Stand-in for 'RoomConfig': holds the configs a room owns."""

    id: str = "the-room"
    agent_config: object = None
    tool_configs: dict = dataclasses.field(default_factory=dict)
    mcp_client_toolset_configs: dict = dataclasses.field(default_factory=dict)
    quizzes: list = dataclasses.field(default_factory=list)


@dataclasses.dataclass(kw_only=True)
class _InterpCompletionCfg:
    """Stand-in for 'CompletionConfig': holds the configs it owns."""

    id: str = "the-completion"
    agent_config: object = None
    tool_configs: dict = dataclasses.field(default_factory=dict)
    mcp_client_toolset_configs: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(kw_only=True)
class _InterpInstallationCfg(_InterpCfg):
    """Stand-in for 'InstallationConfig': declares names, holds roots.

    Redeclare no interpolation, so the unannotated sweep stays off and
    the stanza mappings below are not read as configuration values.
    """

    secrets_map: dict = dataclasses.field(default_factory=dict)
    environment: dict = dataclasses.field(default_factory=dict)
    agent_configs: list = dataclasses.field(default_factory=list)
    logfire_config: object = None
    oidc_auth_system_configs: list = dataclasses.field(default_factory=list)
    room_configs: dict = dataclasses.field(default_factory=dict)
    completion_configs: dict = dataclasses.field(default_factory=dict)


def _the_installation(**overrides) -> installation.Installation:
    """Return an installation over a stand-in config declaring the names."""
    i_config = _InterpInstallationCfg(
        id="the-installation",
        secrets_map={"KNOWN_SECRET": object()},
        environment={"KNOWN_ENV": "a value"},
        **overrides,
    )

    return installation.Installation(_config=i_config)


def _finding(**overrides):
    """Return a finding, overriding any of its default fields."""
    kw = {
        "code": _UNDECLARED,
        "config_type": _INTERP_CFG_NAME,
        "config_id": None,
        "config_path": None,
        "field_name": "secret_whole",
        "config_key": "secret_whole",
        "marker_kind": _SECRET,
        "marker_name": "MISSING",
    }
    kw.update(overrides)

    return cli_audit._InterpolationFinding(**kw)


def test__interpolation_declarations_from_installation_config():
    installation_config = mock.Mock(
        secrets_map={"A_SECRET": object()},
        environment={"AN_ENV": "a value"},
    )
    klass = cli_audit._InterpolationDeclarations

    found = klass.from_installation_config(installation_config)

    assert found.secrets == frozenset({"A_SECRET"})
    assert found.environment == frozenset({"AN_ENV"})
    assert found.names_by_kind == {
        config_interp.MarkerKind.ENVIRONMENT: frozenset({"AN_ENV"}),
        config_interp.MarkerKind.SECRET: frozenset({"A_SECRET"}),
    }


@pytest.mark.parametrize(
    "w_kind, w_name, exp_declared",
    [
        (_SECRET, "KNOWN_SECRET", True),
        (_SECRET, "KNOWN_ENV", False),
        (_ENVIRONMENT, "KNOWN_ENV", True),
        (_ENVIRONMENT, "KNOWN_SECRET", False),
    ],
)
def test__interpolation_declarations_declares(w_kind, w_name, exp_declared):
    found = _DECLARED.declares(w_kind, w_name)

    assert found is exp_declared


@pytest.mark.parametrize(
    "w_overrides, exp_str",
    [
        (
            {},
            f"{_INTERP_CFG_NAME}: secret_whole: "
            "undeclared_name (secret:MISSING)",
        ),
        (
            {"config_id": "the-room", "location": "args[0]"},
            "the-room: args[0]: undeclared_name (secret:MISSING)",
        ),
    ],
)
def test__interpolation_finding___str__(w_overrides, exp_str):
    finding = _finding(**w_overrides)

    found = str(finding)

    assert found == exp_str


@pytest.mark.parametrize(
    "w_config_path, exp_config_path",
    [
        (None, None),
        (A_CONFIG_PATH, str(A_CONFIG_PATH)),
    ],
)
def test__interpolation_finding_as_json(w_config_path, exp_config_path):
    finding = _finding(
        config_id="the-room",
        config_path=w_config_path,
        location="args[0]",
    )

    found = finding.as_json

    assert found == {
        "code": "undeclared_name",
        "config_type": _INTERP_CFG_NAME,
        "config_id": "the-room",
        "config_path": exp_config_path,
        "field_name": "secret_whole",
        "config_key": "secret_whole",
        "marker_kind": "secret",
        "marker_name": "MISSING",
        "location": "args[0]",
    }


@pytest.mark.parametrize(
    "w_text, exp_markers",
    [
        ("no markers here", []),
        ("secret:ONE", [(_SECRET, "ONE")]),
        ("env:ONE", [(_ENVIRONMENT, "ONE")]),
        (
            "postgresql://u:secret:PW@h/env:DB",
            [(_SECRET, "PW"), (_ENVIRONMENT, "DB")],
        ),
        ("secret:ONE and secret:TWO", [(_SECRET, "ONE"), (_SECRET, "TWO")]),
    ],
)
def test__iter_markers(w_text, exp_markers):
    found = list(cli_audit._iter_markers(w_text))

    assert found == exp_markers


@pytest.mark.parametrize(
    "w_text, exp_marker",
    [
        ("secret:ONE", (_SECRET, "ONE")),
        ("env:ONE", (_ENVIRONMENT, "ONE")),
        ("prefix secret:ONE", None),
        ("prefix env:ONE", None),
        ("no markers here", None),
    ],
)
def test__whole_marker(w_text, exp_marker):
    found = cli_audit._whole_marker(w_text)

    assert found == exp_marker


@pytest.mark.parametrize(
    "w_value, exp_strings",
    [
        ("a scalar", [(None, "a scalar")]),
        ({"key": "a value", "n": 42}, [("field['key']", "a value")]),
        (
            ["first", 42, "third"],
            [("field[0]", "first"), ("field[2]", "third")],
        ),
        (("first",), [("field[0]", "first")]),
        (pathlib.Path("/tmp/x"), []),
    ],
)
def test__iter_field_strings(w_value, exp_strings):
    found = list(cli_audit._iter_field_strings("field", w_value))

    assert found == exp_strings


@pytest.mark.parametrize(
    "w_field_name, w_value, exp_findings",
    [
        # A declared-literal field is never reported.
        ("prose", "secret:MISSING", []),
        # A field declaring nothing reports only a whole-value marker: an
        # installation holds prose in which marker-like text is ordinary.
        ("unannotated", "plain text", []),
        ("unannotated", "see secret:MISSING inside", []),
        (
            "unannotated",
            "secret:MISSING",
            [
                {
                    "code": _IGNORED,
                    "field_name": "unannotated",
                    "config_key": "unannotated",
                }
            ],
        ),
        # A non-string value holds no markers.
        ("_config_path", pathlib.Path("/tmp/x"), []),
        # Whole-required: resolved when declared, reported when not.
        ("secret_whole", "secret:KNOWN_SECRET", []),
        ("secret_whole", "secret:MISSING", [{}]),
        (
            "secret_whole",
            "env:KNOWN_ENV",
            [
                {
                    "code": _WRONG_KIND,
                    "marker_kind": _ENVIRONMENT,
                    "marker_name": "KNOWN_ENV",
                },
            ],
        ),
        # Whole-required embedding a marker raises at runtime, so the
        # check stays silent here.
        ("secret_whole", "prefix secret:MISSING", []),
        # Whole-optional embedding a marker passes it through verbatim.
        ("secret_or_literal", "a plain literal", []),
        (
            "secret_or_literal",
            "prefix secret:MISSING suffix",
            [
                {
                    "code": _IGNORED,
                    "field_name": "secret_or_literal",
                    "config_key": "secret_or_literal",
                }
            ],
        ),
        # Embedded: each marker in the value is checked.
        ("env_embedded", "http://env:KNOWN_ENV/v1", []),
        (
            "env_embedded",
            "http://env:MISSING_ENV/v1",
            [
                {
                    "field_name": "env_embedded",
                    "config_key": "env_embedded",
                    "marker_kind": _ENVIRONMENT,
                    "marker_name": "MISSING_ENV",
                }
            ],
        ),
        (
            "env_embedded",
            "secret:KNOWN_SECRET",
            [
                {
                    "code": _WRONG_KIND,
                    "field_name": "env_embedded",
                    "config_key": "env_embedded",
                    "marker_name": "KNOWN_SECRET",
                }
            ],
        ),
        # 'BOTH' admits either kind; the finding names the public key.
        (
            "dburi",
            "postgresql://u:secret:MISSING@h/env:MISSING_ENV",
            [
                {"field_name": "dburi", "config_key": "public_dburi"},
                {
                    "field_name": "dburi",
                    "config_key": "public_dburi",
                    "marker_kind": _ENVIRONMENT,
                    "marker_name": "MISSING_ENV",
                },
            ],
        ),
        # A sequence and a mapping name the element holding the marker.
        (
            "args",
            ["secret:MISSING", 42, "--flag"],
            [
                {
                    "field_name": "args",
                    "config_key": "args",
                    "location": "args[0]",
                }
            ],
        ),
        (
            "env",
            {"TOKEN": "secret:MISSING", "RETRIES": 3},
            [
                {
                    "field_name": "env",
                    "config_key": "env",
                    "location": "env['TOKEN']",
                }
            ],
        ),
    ],
)
def test__field_interpolation_findings(w_field_name, w_value, exp_findings):
    config = _InterpCfg(**{w_field_name: w_value})

    found = cli_audit._field_interpolation_findings(
        config, w_field_name, _DECLARED
    )

    assert found == [
        _finding(
            **{
                "field_name": w_field_name,
                "config_key": w_field_name,
                **exp,
            }
        )
        for exp in exp_findings
    ]


@pytest.mark.parametrize(
    "w_class, exp_findings",
    [
        (
            _InterpCfg,
            [
                _finding(),
                _finding(
                    code=_IGNORED,
                    field_name="unannotated",
                    config_key="unannotated",
                ),
            ],
        ),
        (
            _DerivedInterpCfg,
            [
                _finding(
                    config_type=_DERIVED_CFG_NAME,
                ),
            ],
        ),
    ],
)
def test__config_interpolation_findings(w_class, exp_findings):
    config = w_class(
        secret_whole="secret:MISSING",
        unannotated="secret:MISSING",
    )

    found = cli_audit._config_interpolation_findings(config, _DECLARED)

    assert found == exp_findings


@pytest.mark.parametrize(
    "w_field_name, w_value, exp_holds",
    [
        # No default at all.
        ("required", "secret:KNOWN_SECRET", False),
        ("env_default", "env:MISSING_ENV", True),
        ("env_default", "env:OTHER_MISSING", False),
    ],
)
def test__holds_declared_default(w_field_name, w_value, exp_holds):
    config = _DefaultMarkerCfg(
        **{"required": "secret:KNOWN_SECRET", w_field_name: w_value}
    )

    found = cli_audit._holds_declared_default(config, w_field_name)

    assert found is exp_holds


@pytest.mark.parametrize(
    "w_field_name, w_value, exp_findings",
    [
        # A stock placeholder default is the framework's, not a typo.
        ("env_default", "env:MISSING_ENV", []),
        # An operator's own marker is reported as usual.
        (
            "env_default",
            "env:OTHER_MISSING",
            [{"marker_kind": _ENVIRONMENT, "marker_name": "OTHER_MISSING"}],
        ),
        # A default naming the wrong kind stays a finding.
        (
            "wrong_kind_default",
            "secret:MISSING",
            [{"code": _WRONG_KIND}],
        ),
    ],
)
def test__field_interpolation_findings_w_declared_default(
    w_field_name,
    w_value,
    exp_findings,
):
    config = _DefaultMarkerCfg(
        **{"required": "secret:KNOWN_SECRET", w_field_name: w_value}
    )

    found = cli_audit._field_interpolation_findings(
        config, w_field_name, _DECLARED
    )

    assert found == [
        _finding(
            **{
                "config_type": f"{__name__}._DefaultMarkerCfg",
                "field_name": w_field_name,
                "config_key": w_field_name,
                **exp,
            }
        )
        for exp in exp_findings
    ]


def test__iter_installation_interpolation_configs():
    agent_config = _InterpCfg(id="the-agent")
    installation_config = _InterpInstallationCfg(
        id="the-installation",
        agent_configs=[agent_config],
    )

    found = list(
        cli_audit._iter_installation_interpolation_configs(installation_config)
    )

    assert found == [installation_config, agent_config]


@pytest.mark.parametrize(
    "w_agent, w_judge, exp_ids",
    [
        (False, False, ["the-room", "the-tool", "the-toolset", "the-quiz"]),
        (
            True,
            True,
            [
                "the-room",
                "the-agent",
                "the-tool",
                "the-toolset",
                "the-quiz",
                "the-judge",
            ],
        ),
    ],
)
def test__iter_room_interpolation_configs(w_agent, w_judge, exp_ids):
    judge_agent = _InterpCfg(id="the-judge")
    room_config = _InterpRoomCfg(
        agent_config=_InterpCfg(id="the-agent") if w_agent else None,
        tool_configs={"tool": _InterpCfg(id="the-tool")},
        mcp_client_toolset_configs={"ts": _InterpCfg(id="the-toolset")},
        quizzes=[_InterpQuizCfg(judge_agent=judge_agent if w_judge else None)],
    )

    found = list(cli_audit._iter_room_interpolation_configs(room_config))

    assert [config.id for config in found] == exp_ids


@pytest.mark.parametrize(
    "w_agent, exp_ids",
    [
        (False, ["the-completion", "the-tool", "the-toolset"]),
        (True, ["the-completion", "the-agent", "the-tool", "the-toolset"]),
    ],
)
def test__iter_completion_interpolation_configs(w_agent, exp_ids):
    completion_config = _InterpCompletionCfg(
        agent_config=_InterpCfg(id="the-agent") if w_agent else None,
        tool_configs={"tool": _InterpCfg(id="the-tool")},
        mcp_client_toolset_configs={"ts": _InterpCfg(id="the-toolset")},
    )

    found = list(
        cli_audit._iter_completion_interpolation_configs(completion_config)
    )

    assert [config.id for config in found] == exp_ids


def test__interpolation_findings():
    configs = [
        _InterpCfg(id="first", secret_whole="secret:MISSING"),
        _InterpCfg(id="second", secret_whole="secret:KNOWN_SECRET"),
        _InterpCfg(id="third", env_embedded="env:MISSING_ENV"),
    ]

    found = cli_audit._interpolation_findings(configs, _DECLARED)

    assert found == [
        _finding(config_id="first").as_json,
        _finding(
            config_id="third",
            field_name="env_embedded",
            config_key="env_embedded",
            marker_kind=_ENVIRONMENT,
            marker_name="MISSING_ENV",
        ).as_json,
    ]


def test__installation_declarations(the_installation):
    the_installation._config.secrets_map = {"A_SECRET": object()}
    the_installation._config.environment = {"AN_ENV": "a value"}

    found = cli_audit._installation_declarations(the_installation)

    assert found.secrets == frozenset({"A_SECRET"})
    assert found.environment == frozenset({"AN_ENV"})


@pytest.mark.parametrize("w_finding", [False, True])
def test__invalid_installation_interpolations(w_finding):
    marker = "secret:MISSING" if w_finding else "secret:KNOWN_SECRET"
    agent_config = _InterpCfg(id="the-agent", secret_whole=marker)
    the_installation = _the_installation(agent_configs=[agent_config])

    found = cli_audit._invalid_installation_interpolations(the_installation)

    if w_finding:
        assert found == {
            "installation_interpolation": [
                _finding(config_id="the-agent").as_json,
            ],
        }
    else:
        assert found == {}


@pytest.mark.parametrize(
    "w_config, w_finding", [(False, False), (True, False), (True, True)]
)
def test__invalid_logfire_interpolations(w_config, w_finding):
    marker = "secret:MISSING" if w_finding else "secret:KNOWN_SECRET"
    logfire_config = _InterpCfg(id="the-logfire", secret_whole=marker)
    the_installation = _the_installation(
        logfire_config=logfire_config if w_config else None,
    )

    found = cli_audit._invalid_logfire_interpolations(the_installation)

    if w_finding:
        assert found == {
            "logfire_interpolation": [
                _finding(config_id="the-logfire").as_json,
            ],
        }
    else:
        assert found == {}


@pytest.mark.parametrize("w_finding", [False, True])
def test__invalid_oidc_interpolations(w_finding):
    marker = "secret:MISSING" if w_finding else "secret:KNOWN_SECRET"
    oidc_config = _InterpCfg(id="the-oidc", secret_whole=marker)
    the_installation = _the_installation(
        oidc_auth_system_configs=[oidc_config],
    )

    found = cli_audit._invalid_oidc_interpolations(the_installation)

    if w_finding:
        assert found == {
            "oidc_interpolation": [_finding(config_id="the-oidc").as_json],
        }
    else:
        assert found == {}


@pytest.mark.parametrize("w_finding", [False, True])
def test__invalid_room_interpolations(w_finding):
    marker = "secret:MISSING" if w_finding else "secret:KNOWN_SECRET"
    room_config = _InterpRoomCfg(
        agent_config=_InterpCfg(id="the-agent", secret_whole=marker),
    )
    the_installation = _the_installation(
        room_configs={"the-room": room_config},
    )

    found = cli_audit._invalid_room_interpolations(the_installation)

    if w_finding:
        assert found == {
            "rooms_interpolation": [_finding(config_id="the-agent").as_json],
        }
    else:
        assert found == {}


@pytest.mark.parametrize("w_finding", [False, True])
def test__invalid_completion_interpolations(w_finding):
    marker = "secret:MISSING" if w_finding else "secret:KNOWN_SECRET"
    completion_config = _InterpCompletionCfg(
        agent_config=_InterpCfg(id="the-agent", secret_whole=marker),
    )
    the_installation = _the_installation(
        completion_configs={"the-completion": completion_config},
    )

    found = cli_audit._invalid_completion_interpolations(the_installation)

    if w_finding:
        assert found == {
            "completions_interpolation": [
                _finding(config_id="the-agent").as_json,
            ],
        }
    else:
        assert found == {}


# _print_interpolation_findings: ui only


@pytest.mark.parametrize(
    "w_args, exp_args",
    [
        ((), ["all"]),
        (["-q"], ["-q", "all"]),
        (["all"], ["all"]),
        (["-q", "all"], ["-q", "all"]),
        (["other", "w_arg"], ["other", "w_arg"]),
        (["-q", "other", "w_arg"], ["-q", "other", "w_arg"]),
        (["-q", "path"], ["-q", "all", "path"]),
        (["path"], ["all", "path"]),
    ],
)
@mock.patch("soliplex.cli.audit.typer_core.TyperGroup.parse_args")
def test__auditgroup_parse_args(parse_args, ctx, w_args, exp_args):
    all_command = mock.Mock(spec_set=())
    other_command = mock.Mock(spec_set=())
    ag = cli_audit._AuditGroup(
        commands={"all": all_command, "other": other_command},
    )

    found = ag.parse_args(ctx, w_args)

    assert found is parse_args.return_value
    parse_args.assert_called_once_with(ctx, exp_args)


@pytest.mark.parametrize("w_quiet", [False, True])
@mock.patch("soliplex.cli.cli_util._configure_cli_logging")
def test__audit_callback(configure_logging, ctx, w_quiet):
    w_quiet_kw = {"quiet": w_quiet}

    cli_audit._audit_callback(ctx, cli_log_config=None, **w_quiet_kw)

    assert ctx.obj["quiet"] == w_quiet
    configure_logging.assert_called_once_with(None)


@mock.patch("soliplex.cli.cli_util._configure_cli_logging")
def test_cli_log_config_from_env(
    configure_logging, scratch_installation, cli_runner, tmp_path
):
    # 'audit room-authz' (like 'audit admin-users') reads security objects
    # through the authz policy, so it emits security-object-read audit
    # records -- hence the group's '--cli-log-config' option, backed by
    # 'SOLIPLEX_CLI_LOG_CONFIG' via Typer's 'envvar='. Verify the env value
    # reaches the callback as a Path. Regression guard.
    cfg = tmp_path / "audit-logging.yaml"
    cfg.write_text("version: 1\n")

    result = cli_runner.invoke(
        cli_audit.app,
        ["room-authz", str(scratch_installation.path)],
        env={"SOLIPLEX_CLI_LOG_CONFIG": str(cfg)},
    )

    assert result.exit_code == 0
    # The group callback (which runs first) forwards the env-derived Path;
    # the '_authz_session' safety net then calls it again with no argument.
    assert configure_logging.call_args_list[0] == mock.call(cfg)


@pytest.mark.parametrize("w_errors", [False, True])
@pytest.mark.parametrize("w_quiet", [False, True])
@mock.patch("soliplex.cli.audit._emit_errors")
@mock.patch("soliplex.cli.audit._audit_ollama_section")
@mock.patch("soliplex.cli.audit._audit_logfire_section")
@mock.patch("soliplex.cli.audit._audit_logging_section")
@mock.patch("soliplex.cli.audit._audit_skills_section")
@mock.patch("soliplex.cli.audit._audit_quizzes_section")
@mock.patch("soliplex.cli.audit._audit_completions_section")
@mock.patch("soliplex.cli.audit._audit_room_authz_section")
@mock.patch("soliplex.cli.audit._audit_admin_users_section")
@mock.patch("soliplex.cli.audit._audit_databases_section")
@mock.patch("soliplex.cli.audit._audit_rooms_section")
@mock.patch("soliplex.cli.audit._audit_oidc_section")
@mock.patch("soliplex.cli.audit._audit_environment_section")
@mock.patch("soliplex.cli.audit._audit_secrets_section")
@mock.patch("soliplex.cli.audit._audit_installation_section")
def test_audit_all(
    _audit_installation_section,
    _audit_secrets_section,
    _audit_environment_section,
    _audit_oidc_section,
    _audit_rooms_section,
    _audit_databases_section,
    _audit_admin_users_section,
    _audit_room_authz_section,
    _audit_completions_section,
    _audit_quizzes_section,
    _audit_skills_section,
    _audit_logging_section,
    _audit_logfire_section,
    _audit_ollama_section,
    _emit_errors,
    ctx,
    installation_path,
    w_quiet,
    w_errors,
):
    ctx.obj["quiet"] = w_quiet

    if w_errors:
        _audit_installation_section.return_value = {"installation": None}
        _audit_secrets_section.return_value = {"secrets": None}
        _audit_environment_section.return_value = {"environment": None}
        _audit_oidc_section.return_value = {"oidc": None}
        _audit_rooms_section.return_value = {"rooms": None}
        _audit_databases_section.return_value = {"databases": None}
        _audit_admin_users_section.return_value = {"admin_users": None}
        _audit_room_authz_section.return_value = {"room_authz": None}
        _audit_completions_section.return_value = {"completions": None}
        _audit_quizzes_section.return_value = {"quizzes": None}
        _audit_skills_section.return_value = {"skills": None}
        _audit_logging_section.return_value = {"logging": None}
        _audit_logfire_section.return_value = {"logfire": None}
        _audit_ollama_section.return_value = {"ollama": None}

        expected = {
            "installation": None,
            "secrets": None,
            "environment": None,
            "oidc": None,
            "rooms": None,
            "databases": None,
            "admin_users": None,
            "room_authz": None,
            "completions": None,
            "quizzes": None,
            "skills": None,
            "logging": None,
            "logfire": None,
            "ollama": None,
        }
    else:
        _audit_installation_section.return_value = {}
        _audit_secrets_section.return_value = {}
        _audit_environment_section.return_value = {}
        _audit_oidc_section.return_value = {}
        _audit_rooms_section.return_value = {}
        _audit_databases_section.return_value = {}
        _audit_admin_users_section.return_value = {}
        _audit_room_authz_section.return_value = {}
        _audit_completions_section.return_value = {}
        _audit_quizzes_section.return_value = {}
        _audit_skills_section.return_value = {}
        _audit_logging_section.return_value = {}
        _audit_logfire_section.return_value = {}
        _audit_ollama_section.return_value = {}

        expected = {}

    cli_audit.audit_all(ctx, installation_path)

    _emit_errors.assert_called_once_with(expected, w_quiet)

    _audit_installation_section.assert_called_once_with(ctx, installation_path)
    _audit_secrets_section.assert_called_once_with(ctx, installation_path)
    _audit_environment_section.assert_called_once_with(ctx, installation_path)
    _audit_oidc_section.assert_called_once_with(ctx, installation_path)
    _audit_rooms_section.assert_called_once_with(ctx, installation_path)
    _audit_admin_users_section.assert_called_once_with(ctx, installation_path)
    _audit_room_authz_section.assert_called_once_with(ctx, installation_path)
    _audit_completions_section.assert_called_once_with(ctx, installation_path)
    _audit_quizzes_section.assert_called_once_with(ctx, installation_path)
    _audit_skills_section.assert_called_once_with(ctx, installation_path)
    _audit_logging_section.assert_called_once_with(ctx, installation_path)
    _audit_logfire_section.assert_called_once_with(ctx, installation_path)
    _audit_ollama_section.assert_called_once_with(ctx, installation_path)


@pytest.mark.parametrize("w_error", [False, True])
@mock.patch("soliplex.models.Installation.from_config")
def test__invalid_installation(mifc, the_installation, w_error):
    if w_error:
        mifc.side_effect = ModelException()

    found = cli_audit._invalid_installation(the_installation)

    if w_error:
        assert found == {"installation_model": TESTING_MODEL_ERROR}
    else:
        assert found == {}

    mifc.assert_called_once_with(the_installation._config)


# _audit_installation_section: ui only
# audit_installation: command


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

    found = cli_audit._missing_secrets(the_installation)

    if exp_missing is not None:
        assert found == {"missing_secrets": exp_missing}
    else:
        assert found == {}

    resolve_secrets.assert_called_once_with()


# _audit_secrets_section: ui only
# audit_secrets: command


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

    found = cli_audit._missing_env_vars(the_installation)

    if w_missing is not None:
        assert found == {"missing_env_vars": w_missing}
    else:
        assert found == {}

    resolve_environment.assert_called_once_with()


# _audit_environment_section: ui only
# audit_environment: command


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
        side_effects.append(ModelException() if has_error else None)

    the_installation._config.oidc_auth_system_configs = oidc_configs
    moafc.side_effect = side_effects

    found = cli_audit._invalid_oidc_auth_providers(the_installation)

    if exp_invalid_ids:
        assert found == {
            "oidc": {cid: TESTING_MODEL_ERROR for cid in exp_invalid_ids},
        }
    else:
        assert found == {}

    assert moafc.call_args_list == [mock.call(cfg) for cfg in oidc_configs]


# _audit_oidc_section: ui only
# audit_oidc_auth_providers: command


@pytest.mark.parametrize("w_count", [0, 5])
@pytest.mark.anyio
async def test__async_count(w_count):
    rag = mock.AsyncMock()
    rag_a = rag.__aenter__.return_value
    rag_a.count_documents = mock.AsyncMock(return_value=w_count)

    found = await cli_audit._async_count(rag)

    assert found == w_count
    rag_a.count_documents.assert_awaited_once_with()


@pytest.mark.parametrize(
    "w_count, exp_result",
    [
        (0, ("0 documents", None)),
        (5, ("5 documents", None)),
        (None, ("ERROR: boom", "boom")),
    ],
)
def test__count_rag_documents(w_count, exp_result):
    rag = mock.AsyncMock()
    rag_a = rag.__aenter__.return_value

    if w_count is None:
        rag_a.count_documents = mock.AsyncMock(
            side_effect=RuntimeError("boom"),
        )
    else:
        rag_a.count_documents = mock.AsyncMock(return_value=w_count)

    found = cli_audit._count_rag_documents(rag)

    assert found == exp_result
    rag_a.count_documents.assert_awaited_once_with()


@pytest.mark.parametrize(
    "w_room_id_and_error, exp_invalid_ids",
    [
        ([], []),
        ([("r1", False)], []),
        ([("r1", True)], ["r1"]),
        ([("r1", False), ("r2", True)], ["r2"]),
        ([("r1", True), ("r2", True)], ["r1", "r2"]),
    ],
)
@mock.patch("soliplex.models.Room.from_config")
def test__invalid_rooms(
    mrfc,
    the_installation,
    w_room_id_and_error,
    exp_invalid_ids,
):
    room_configs = {}
    side_effects = []
    for room_id, has_error in w_room_id_and_error:
        cfg = mock.Mock()
        cfg.id = room_id
        room_configs[room_id] = cfg
        side_effects.append(ModelException() if has_error else None)

    the_installation._config.room_configs = room_configs
    mrfc.side_effect = side_effects

    found = cli_audit._invalid_rooms(the_installation)

    if exp_invalid_ids:
        assert found == {
            "room": {rid: TESTING_MODEL_ERROR for rid in exp_invalid_ids},
        }
    else:
        assert found == {}

    assert mrfc.call_args_list == [
        mock.call(cfg) for cfg in room_configs.values()
    ]


def _rag_cfg(**attrs):
    cfg = object.__new__(config_rag._RAGConfigBase)
    for k, v in attrs.items():
        setattr(cfg, k, v)
    return cfg


@pytest.mark.parametrize(
    "w_agent_rag, skills_and_rag, tools_and_rag",
    [
        (False, [], []),
        (False, [("s1", False)], [("t1", False)]),
        (True, [], []),
        (False, [("s1", True), ("s2", False)], []),
        (False, [], [("t1", True), ("t2", False)]),
        (
            True,
            [("s1", True), ("s2", False)],
            [("t1", True), ("t2", False)],
        ),
    ],
)
def test__iter_room_rag_candidates(w_agent_rag, skills_and_rag, tools_and_rag):
    room_config = mock.Mock()

    if w_agent_rag:
        room_config.agent_config = _rag_cfg()
    else:
        room_config.agent_config = mock.Mock()

    skill_configs = {
        s_name: _rag_cfg() if is_rag else mock.Mock()
        for s_name, is_rag in skills_and_rag
    }
    skills = mock.Mock()
    skills.skill_configs = skill_configs
    room_config.skills = skills

    tool_configs = {
        t_name: _rag_cfg(tool_name=t_name) if is_rag else mock.Mock()
        for t_name, is_rag in tools_and_rag
    }
    room_config.tool_configs = tool_configs

    found = list(cli_audit._iter_room_rag_candidates(room_config))

    expected = []
    if w_agent_rag:
        expected.append(("agent", room_config.agent_config))
    for s_name, is_rag in skills_and_rag:
        if is_rag:
            expected.append((f"skill:{s_name}", skill_configs[s_name]))
    for t_name, is_rag in tools_and_rag:
        if is_rag:
            expected.append((f"tool:{t_name}", tool_configs[t_name]))

    assert found == expected


def test__iter_room_rag_candidates_skills_none():
    room_config = mock.Mock()
    room_config.agent_config = mock.Mock()
    room_config.skills = None
    room_config.tool_configs = {}

    found = list(cli_audit._iter_room_rag_candidates(room_config))

    assert found == []


@pytest.mark.parametrize(
    "rooms_and_features, registered, exp_errors",
    [
        ([], (), {}),
        ([("r1", ())], (), {}),
        ([("r1", ("a",))], ("a",), {}),
        (
            [("r1", ("a", "missing"))],
            ("a",),
            {"agui_features": {"r1": ["missing"]}},
        ),
        (
            [
                ("r1", ("a", "missing")),
                ("r2", ("a",)),
                ("r3", ("x", "y")),
            ],
            ("a",),
            {
                "agui_features": {
                    "r1": ["missing"],
                    "r3": ["x", "y"],
                },
            },
        ),
    ],
)
def test__invalid_room_agui_features(
    the_installation,
    patched_agui_features,
    rooms_and_features,
    registered,
    exp_errors,
):
    for name in registered:
        patched_agui_features[name] = mock.Mock()

    room_configs = {}
    for room_id, feature_names in rooms_and_features:
        cfg = mock.Mock()
        cfg.id = room_id
        cfg.agui_feature_names = feature_names
        room_configs[room_id] = cfg

    the_installation._config.room_configs = room_configs

    found = cli_audit._invalid_room_agui_features(the_installation)

    assert found == exp_errors


@pytest.mark.parametrize(
    "rooms_and_candidates, exp_errors",
    [
        ([], {}),
        ([("r1", [])], {}),
        ([("r1", [("agent", False)])], {}),
        (
            [("r1", [("agent", True)])],
            {"rag": {"r1": {"agent": TESTING_RAG_ERROR}}},
        ),
        (
            [
                ("r1", [("agent", False), ("tool:t1", True)]),
                ("r2", [("skill:s1", False)]),
                ("r3", [("agent", True)]),
            ],
            {
                "rag": {
                    "r1": {"tool:t1": TESTING_RAG_ERROR},
                    "r3": {"agent": TESTING_RAG_ERROR},
                },
            },
        ),
    ],
)
@mock.patch("soliplex.cli.audit._iter_room_rag_candidates")
def test__invalid_room_rag_dbs(
    iter_candidates,
    the_installation,
    rooms_and_candidates,
    exp_errors,
):
    room_configs = {}
    side_effects = []
    for room_id, candidate_specs in rooms_and_candidates:
        room_cfg = mock.Mock()
        room_cfg.id = room_id
        room_configs[room_id] = room_cfg
        side_effects.append(
            [
                (source, _ErrRagCfg() if has_error else _OkRagCfg())
                for source, has_error in candidate_specs
            ]
        )

    the_installation._config.room_configs = room_configs
    iter_candidates.side_effect = side_effects

    found = cli_audit._invalid_room_rag_dbs(the_installation)

    assert found == exp_errors
    assert iter_candidates.call_args_list == [
        mock.call(rc) for rc in room_configs.values()
    ]


@mock.patch("soliplex.cli.audit._iter_room_rag_candidates")
def test__invalid_room_rag_dbs_w_rag_databases(
    iter_candidates,
    the_installation,
):
    """Each named database is probed and reported under its own name"""
    room_cfg = mock.Mock()
    room_cfg.id = "r1"
    the_installation._config.room_configs = {"r1": room_cfg}
    iter_candidates.side_effect = [[("skill:rag", _MultiRagCfg())]]

    found = cli_audit._invalid_room_rag_dbs(the_installation)

    assert found == {"rag": {"r1": {"skill:rag#wiki": TESTING_RAG_ERROR}}}


@mock.patch("soliplex.cli.audit._iter_room_rag_candidates")
def test__invalid_room_rag_dbs_wo_database(
    iter_candidates,
    the_installation,
):
    """A config naming no database is reported, not raised at the caller"""
    room_cfg = mock.Mock()
    room_cfg.id = "r1"
    the_installation._config.room_configs = {"r1": room_cfg}
    iter_candidates.side_effect = [[("skill:rag", _NoDbRagCfg())]]

    found = cli_audit._invalid_room_rag_dbs(the_installation)

    assert "rag_lancedb_path" in found["rag"]["r1"]["skill:rag"]


@mock.patch("soliplex.cli.audit._iter_room_rag_candidates")
def test__invalid_room_rag_dbs_w_deferred_database(
    iter_candidates,
    the_installation,
):
    """A config placing no database of its own has no path to probe"""
    room_cfg = mock.Mock()
    room_cfg.id = "r1"
    the_installation._config.room_configs = {"r1": room_cfg}
    iter_candidates.side_effect = [[("skill:rag", _DeferringRagCfg())]]

    assert cli_audit._invalid_room_rag_dbs(the_installation) == {}


@mock.patch("soliplex.cli.audit._iter_room_rag_candidates")
def test__invalid_room_rag_dbs_w_unbuildable_config(
    iter_candidates,
    the_installation,
):
    """A config that will not build reports that, not its unresolved path

    Its path fails to resolve as well, but naming the missing file sends
    the operator to create it, which is not the fix.
    """
    room_cfg = mock.Mock()
    room_cfg.id = "r1"
    the_installation._config.room_configs = {"r1": room_cfg}
    iter_candidates.side_effect = [[("skill:rag", _UnbuildableRagCfg())]]

    found = cli_audit._invalid_room_rag_dbs(the_installation)

    (reported,) = found["rag"]["r1"].values()
    assert reported == TESTING_RAG_UNBUILDABLE
    assert TESTING_RAG_ERROR not in reported
    assert list(found["rag"]["r1"]) == ["skill:rag"]


# _audit_rooms_section: ui only
# audit_rooms: command


@pytest.mark.anyio
@mock.patch("soliplex.cli.audit.cli_util._room_authz_policy")
async def test__list_room_policies(authz_policy):
    # The helper is a pass-through; the return value emulates the
    # 'models.RoomPolicyUnchecked' shape 'list_room_policies' yields.
    policies = [
        {
            "room_id": "faux",
            "default_allow_deny": authz.AllowDeny.DENY,
            "acl_entries": [
                {
                    "allow_deny": authz.AllowDeny.ALLOW,
                    "everyone": False,
                    "authenticated": False,
                    "preferred_username": None,
                    "email": "alice@example.com",
                    "json_path": None,
                },
            ],
        },
    ]
    policy = mock.AsyncMock()
    policy.list_room_policies.return_value = policies
    authz_policy.return_value.__aenter__.return_value = policy

    found = await cli_audit._list_room_policies(mock.sentinel.installation)

    assert found == policies
    authz_policy.assert_called_once_with(
        mock.sentinel.installation,
        "audit room-authz",
        allow_ram=True,
        must_exist=True,
    )
    policy.list_room_policies.assert_awaited_once_with()


@pytest.mark.anyio
@mock.patch("soliplex.cli.audit.cli_util._admin_user_policy")
async def test__list_admin_discriminators(authz_policy):
    # The helper is a pass-through; 'list_admin_user_discriminators'
    # yields the stored 'AdminUser.json_path' query strings.
    discriminators = [
        '$[?$.email == "alice@example.com"]',
        '$[?$.role == "admin"]',
    ]
    policy = mock.AsyncMock()
    policy.list_admin_user_discriminators.return_value = discriminators
    authz_policy.return_value.__aenter__.return_value = policy

    found = await cli_audit._list_admin_discriminators(
        mock.sentinel.installation
    )

    assert found == discriminators
    authz_policy.assert_called_once_with(
        mock.sentinel.installation,
        "audit admin-users",
        allow_ram=True,
        must_exist=True,
    )
    policy.list_admin_user_discriminators.assert_awaited_once_with()


def _tables(db_path):
    """The tables in a SQLite file. Connecting creates the file itself --
    an empty one -- so the schema is what says whether anything was
    created."""
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        return set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _uncreated_installation(the_installation, tmp_path):
    """Point an installation at an authz database nothing has created."""
    db_path = tmp_path / "authz.sqlite"
    the_installation._config.authorization_async_dburi = (
        f"sqlite+aiosqlite:///{db_path}"
    )
    the_installation._config.authorization_sync_dburi = f"sqlite:///{db_path}"
    return the_installation, db_path


def test__room_policies_on_an_uncreated_database(the_installation, tmp_path):
    the_installation, db_path = _uncreated_installation(
        the_installation, tmp_path
    )

    found_policies, found_error = cli_audit._room_policies(the_installation)

    assert found_policies == []
    assert found_error is None
    # Reading is all an audit does: no schema was created.
    assert _tables(db_path) == set()


@pytest.mark.parametrize(
    "policies, exc, exp_policies, exp_error",
    [
        # A database nothing has created -- an in-memory one included --
        # holds no policies, and that is not a finding.
        (None, cli_util.DatabaseNotCreated("authz"), [], None),
        # Created, with no stored rows.
        ([], None, [], None),
        # Stored rows pass through in the order they are read.
        (["p1", "p2"], None, ["p1", "p2"], None),
        # A database the driver cannot reach: reported, not raised.
        (None, AuthzDBError(), [], EXP_AUTHZ_DB_ERROR),
    ],
)
@mock.patch("soliplex.cli.audit._list_room_policies")
def test__room_policies(
    list_room_policies,
    the_installation,
    policies,
    exc,
    exp_policies,
    exp_error,
):
    # The helper is a pass-through, so opaque stand-ins stand in for the
    # 'models.RoomPolicyUnchecked' instances the policy yields.
    if exc is not None:
        list_room_policies.side_effect = exc
    else:
        list_room_policies.return_value = policies

    found_policies, found_error = cli_audit._room_policies(the_installation)

    assert found_policies == exp_policies
    assert found_error == exp_error
    list_room_policies.assert_called_once_with(the_installation)


@pytest.mark.parametrize(
    "configured_rooms, policy_specs, exp_groups",
    [
        # Empty configuration + empty DB.
        ([], [], {"default": [], "public": [], "private": [], "stale": []}),
        # Configured rooms but no DB rows -> all default.
        (
            ["alpha", "beta"],
            [],
            {
                "default": ["alpha", "beta"],
                "public": [],
                "private": [],
                "stale": [],
            },
        ),
        # Only DB rows for unconfigured rooms -> all stale.
        (
            [],
            [("old", "ALLOW"), ("removed", "DENY")],
            {
                "default": [],
                "public": [],
                "private": [],
                "stale": ["old", "removed"],
            },
        ),
        # Mixed: one row in each of the four buckets.
        (
            ["alpha", "beta", "gamma", "delta"],
            [
                ("beta", "ALLOW"),
                ("gamma", "DENY"),
                ("ghost", "DENY"),
            ],
            {
                "default": ["alpha", "delta"],
                "public": ["beta"],
                "private": ["gamma"],
                "stale": ["ghost"],
            },
        ),
    ],
)
def test__room_authz_groups(
    the_installation,
    configured_rooms,
    policy_specs,
    exp_groups,
):
    the_installation._config.room_configs = {
        rid: mock.Mock() for rid in configured_rooms
    }
    room_policies = [
        models.RoomPolicyUnchecked(
            room_id=room_id,
            default_allow_deny=(
                authz.AllowDeny.ALLOW
                if allow_deny == "ALLOW"
                else authz.AllowDeny.DENY
            ),
        )
        for room_id, allow_deny in policy_specs
    ]

    found = cli_audit._room_authz_groups(the_installation, room_policies)

    assert found == exp_groups


@pytest.mark.parametrize(
    "policy_specs, exp_invalid",
    [
        # No policies.
        ([], {}),
        # All entries valid.
        (
            [
                ("chat", [None, '$[?$.email == "alice@example.com"]']),
            ],
            {},
        ),
        # One invalid entry.
        (
            [
                ("chat", ["$[?missing_func($.email)]"]),
            ],
            {"chat": [("$[?missing_func($.email)]", "<error>")]},
        ),
        # Mix of valid and invalid across rooms.
        (
            [
                (
                    "chat",
                    [
                        '$[?$.email == "alice@example.com"]',
                        "$[?missing_func($.email)]",
                    ],
                ),
                ("search", [None]),
                ("ghost", ["$[?other_missing($.email)]"]),
            ],
            {
                "chat": [("$[?missing_func($.email)]", "<error>")],
                "ghost": [("$[?other_missing($.email)]", "<error>")],
            },
        ),
    ],
)
def test__invalid_acl_json_paths(policy_specs, exp_invalid):
    room_policies = [
        models.RoomPolicyUnchecked(
            room_id=room_id,
            acl_entries=[
                models.ACLEntryUnchecked(
                    allow_deny=authz.AllowDeny.DENY,
                    json_path=jp,
                )
                for jp in json_paths
            ],
        )
        for room_id, json_paths in policy_specs
    ]

    found = cli_audit._invalid_acl_json_paths(room_policies)

    # The error message is implementation-detail; normalize for compare.
    normalized = {
        room_id: [(jp, "<error>") for (jp, _err) in entries]
        for room_id, entries in found.items()
    }
    assert normalized == exp_invalid


# _audit_room_authz_section: ui only
# audit_room_authz: command


def test__admin_user_json_paths_on_an_uncreated_database(
    the_installation, tmp_path
):
    the_installation, db_path = _uncreated_installation(
        the_installation, tmp_path
    )

    found_paths, found_error = cli_audit._admin_user_json_paths(
        the_installation
    )

    assert found_paths == []
    assert found_error is None
    assert _tables(db_path) == set()


@pytest.mark.parametrize(
    "json_paths, exc, exp_json_paths, exp_error",
    [
        # A database nothing has created -- an in-memory one included --
        # holds no admin rows, and that is not a finding.
        (None, cli_util.DatabaseNotCreated("authz"), [], None),
        # Created, with no stored admins.
        ([], None, [], None),
        # Stored rows pass through in the order they are read.
        (
            [
                '$[?$.email == "alice@example.com"]',
                "$[?some_func($.email)]",
            ],
            None,
            [
                '$[?$.email == "alice@example.com"]',
                "$[?some_func($.email)]",
            ],
            None,
        ),
        # A database the driver cannot reach: reported, not raised.
        (None, AuthzDBError(), [], EXP_AUTHZ_DB_ERROR),
    ],
)
@mock.patch("soliplex.cli.audit._list_admin_discriminators")
def test__admin_user_json_paths(
    list_admin_discriminators,
    the_installation,
    json_paths,
    exc,
    exp_json_paths,
    exp_error,
):
    if exc is not None:
        list_admin_discriminators.side_effect = exc
    else:
        list_admin_discriminators.return_value = json_paths

    found_json_paths, found_error = cli_audit._admin_user_json_paths(
        the_installation
    )

    assert found_json_paths == exp_json_paths
    assert found_error == exp_error
    list_admin_discriminators.assert_called_once_with(the_installation)


@pytest.mark.parametrize(
    "json_paths, exp_invalid",
    [
        # No admins.
        ([], []),
        # All valid.
        (
            [
                '$[?$.email == "alice@example.com"]',
                '$[?$.preferred_username == "bob"]',
            ],
            [],
        ),
        # Mixed: one invalid.
        (
            [
                '$[?$.email == "alice@example.com"]',
                "$[?missing_func($.email)]",
            ],
            [("$[?missing_func($.email)]", "<error>")],
        ),
        # All invalid.
        (
            ["$[?one_missing()]", "$[?another_missing()]"],
            [
                ("$[?one_missing()]", "<error>"),
                ("$[?another_missing()]", "<error>"),
            ],
        ),
    ],
)
def test__invalid_admin_user_json_paths(json_paths, exp_invalid):
    found = cli_audit._invalid_admin_user_json_paths(json_paths)

    normalized = [(jp, "<error>") for (jp, _err) in found]
    assert normalized == exp_invalid


# _audit_admin_users_section: ui only
# audit_admin_users: command


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
        side_effects.append(ModelException() if has_error else None)

    the_installation._config.completion_configs = completion_configs
    mcfc.side_effect = side_effects

    found = cli_audit._invalid_completions(the_installation)

    if exp_invalid_ids:
        assert found == {
            "completions": {
                cid: TESTING_MODEL_ERROR for cid in exp_invalid_ids
            },
        }
    else:
        assert found == {}

    assert mcfc.call_args_list == [
        mock.call(cfg) for cfg in completion_configs.values()
    ]


# _audit_completions_section: ui only
# audit_completions: command


@pytest.mark.parametrize(
    "w_layout, exp_yields",
    [
        ([], []),
        ([("p1", [])], []),
        ([("p1", ["readme.txt"])], []),
        ([("p1", ["q1.json"])], [("p1", "q1.json")]),
        (
            [("p1", ["q1.json", "readme.txt", "q2.json"])],
            [("p1", "q1.json"), ("p1", "q2.json")],
        ),
        (
            [
                ("p1", ["q1.json"]),
                ("p2", []),
                ("p3", ["q2.json", "q3.json"]),
            ],
            [
                ("p1", "q1.json"),
                ("p3", "q2.json"),
                ("p3", "q3.json"),
            ],
        ),
    ],
)
def test__iter_quiz_configs(
    tmp_path,
    the_installation,
    w_layout,
    exp_yields,
):
    quizzes_paths = []
    for dir_name, files in w_layout:
        d = tmp_path / dir_name
        d.mkdir()
        for f_name in files:
            (d / f_name).write_text("{}")
        quizzes_paths.append(d)

    the_installation._config.quizzes_paths = quizzes_paths

    found = sorted(
        cli_audit._iter_quiz_configs(the_installation),
        key=lambda t: (str(t[0]), str(t[1])),
    )

    expected = sorted(
        [
            (
                tmp_path / dir_name,
                tmp_path / dir_name / f_name,
                config_quizzes.QuizConfig(
                    id="check",
                    question_file=str(tmp_path / dir_name / f_name),
                ),
            )
            for dir_name, f_name in exp_yields
        ],
        key=lambda t: (str(t[0]), str(t[1])),
    )

    for found_item, exp_item in zip(found, expected, strict=True):
        assert found_item == exp_item


@pytest.mark.parametrize(
    "w_quiz_specs, exp_errors",
    [
        ([], {}),
        ([("p1", "q1.json", False)], {}),
        (
            [("p1", "q1.json", True)],
            {"quizzes": {"p1": {"q1.json": TESTING_QUIZ_ERROR}}},
        ),
        (
            [("p1", "q1.json", True), ("p1", "q2.json", False)],
            {"quizzes": {"p1": {"q1.json": TESTING_QUIZ_ERROR}}},
        ),
        (
            [("p1", "q1.json", True), ("p1", "q2.json", True)],
            {
                "quizzes": {
                    "p1": {
                        "q1.json": TESTING_QUIZ_ERROR,
                        "q2.json": TESTING_QUIZ_ERROR,
                    },
                },
            },
        ),
        (
            [("p1", "q1.json", True), ("p2", "q2.json", True)],
            {
                "quizzes": {
                    "p1": {"q1.json": TESTING_QUIZ_ERROR},
                    "p2": {"q2.json": TESTING_QUIZ_ERROR},
                },
            },
        ),
    ],
)
@mock.patch("soliplex.cli.audit._iter_quiz_configs")
def test__invalid_quizzes(
    iter_quiz_configs,
    the_installation,
    w_quiz_specs,
    exp_errors,
):
    quiz_tuples = []
    for path_name, file_name, has_error in w_quiz_specs:
        q_path = pathlib.Path(path_name)
        q_file = mock.Mock()
        q_file.name = file_name
        q_config = mock.Mock()
        if has_error:
            q_config.get_questions.side_effect = QuizError()
        quiz_tuples.append((q_path, q_file, q_config))

    iter_quiz_configs.return_value = quiz_tuples

    found = cli_audit._invalid_quizzes(the_installation)

    assert found == exp_errors
    iter_quiz_configs.assert_called_once_with(the_installation)


# _audit_quizzes_section: ui only
# audit_quizzes: command


@pytest.mark.parametrize(
    "w_self_has_skill, w_subs, exp_yields",
    [
        (True, [], ["."]),
        (True, [("a", True), ("b", True)], ["."]),
        (False, [], []),
        (False, [("a", False), ("b", False)], []),
        (False, [("a", True), ("b", False), ("c", True)], ["a", "c"]),
        (False, [(".hidden", True), ("a", True)], ["a"]),
        (False, [("c", True), ("a", True), ("b", True)], ["a", "b", "c"]),
    ],
)
def test__find_skill_paths(
    tmp_path,
    w_self_has_skill,
    w_subs,
    exp_yields,
):
    to_search = tmp_path / "search"
    to_search.mkdir()

    if w_self_has_skill:
        (to_search / "SKILL.md").write_text("")

    for sub_name, has_skill in w_subs:
        sub = to_search / sub_name
        sub.mkdir()
        if has_skill:
            (sub / "SKILL.md").write_text("")

    found = list(cli_audit._find_skill_paths(to_search))

    expected = [
        to_search if name == "." else to_search / name for name in exp_yields
    ]

    assert found == expected


@pytest.mark.parametrize(
    "w_skill_specs, exp_errors",
    [
        ([], {}),
        ([("s1", None)], {}),
        ([("s1", 0)], {}),
        ([("s1", 1)], {"skills": {"s1": [TESTING_SKILL_ERROR]}}),
        (
            [("s1", 2)],
            {"skills": {"s1": [TESTING_SKILL_ERROR, TESTING_SKILL_ERROR]}},
        ),
        (
            [("s1", None), ("s2", 1), ("s3", 0), ("s4", 2)],
            {
                "skills": {
                    "s2": [TESTING_SKILL_ERROR],
                    "s4": [TESTING_SKILL_ERROR, TESTING_SKILL_ERROR],
                },
            },
        ),
    ],
)
def test__invalid_skill_configs(
    the_installation,
    w_skill_specs,
    exp_errors,
):
    skill_configs = {}
    for skill_name, errors_count in w_skill_specs:
        cfg = mock.Mock()
        if errors_count is None:
            cfg.errors = None
        else:
            cfg.errors = [SkillError() for _ in range(errors_count)]
        skill_configs[skill_name] = cfg

    the_installation._config.skill_configs = skill_configs

    found = cli_audit._invalid_skill_configs(the_installation)

    assert found == exp_errors


@pytest.mark.parametrize(
    "w_path_specs, exp_errors",
    [
        ([], {}),
        ([("p1", [])], {}),
        ([("p1", [("s1", 0)])], {}),
        (
            [("p1", [("s1", 1)])],
            {"skills_filesystem": {"s1": [TESTING_SKILL_ERROR]}},
        ),
        (
            [("p1", [("s1", 2)])],
            {
                "skills_filesystem": {
                    "s1": [TESTING_SKILL_ERROR, TESTING_SKILL_ERROR],
                },
            },
        ),
        (
            [
                ("p1", [("s1", 1), ("s2", 0)]),
                ("p2", []),
                ("p3", [("s3", 1), ("s4", 2)]),
            ],
            {
                "skills_filesystem": {
                    "s1": [TESTING_SKILL_ERROR],
                    "s3": [TESTING_SKILL_ERROR],
                    "s4": [TESTING_SKILL_ERROR, TESTING_SKILL_ERROR],
                },
            },
        ),
    ],
)
@mock.patch("soliplex.cli.audit.skill_validator.validate")
@mock.patch("soliplex.cli.audit._find_skill_paths")
def test__invalid_filesystem_skills(
    find_skill_paths,
    validate,
    the_installation,
    w_path_specs,
    exp_errors,
):
    fs_paths = []
    find_side_effects = []
    validate_side_effects = []
    for path_name, skill_specs in w_path_specs:
        fs_paths.append(pathlib.Path(path_name))
        skill_paths_for_this = []
        for skill_name, errors_count in skill_specs:
            skill_paths_for_this.append(pathlib.Path(skill_name))
            validate_side_effects.append(
                [SkillError() for _ in range(errors_count)]
            )
        find_side_effects.append(skill_paths_for_this)

    the_installation._config.filesystem_skills_paths = fs_paths
    find_skill_paths.side_effect = find_side_effects
    validate.side_effect = validate_side_effects

    found = cli_audit._invalid_filesystem_skills(the_installation)

    assert found == exp_errors
    assert find_skill_paths.call_args_list == [mock.call(p) for p in fs_paths]


# _audit_skills_section: ui only
# audit_skills: command


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
        found = cli_audit._load_logging_config(the_installation)

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
@mock.patch("soliplex.cli.audit._load_logging_config")
def test__invalid_logging(
    load_logging_config,
    the_installation,
    w_exc,
    exp_errors,
):
    if w_exc is not None:
        load_logging_config.side_effect = w_exc

    found = cli_audit._invalid_logging(the_installation)

    assert found == exp_errors
    load_logging_config.assert_called_once_with(the_installation)


# _audit_logging_section: ui only
# audit_logging: command


# _audit_logfire_section: ui only
# audit_logfire: command


@pytest.mark.parametrize(
    "w_provider_info, w_responses, exp_errors",
    [
        # No Ollama URLs configured -> no errors.
        ({}, {}, {}),
        # URL present but no models referenced -> skipped, no errors.
        (
            {"ollama": {"http://a.example.com": {}}},
            {},
            {},
        ),
        # All required models are available -> no errors.
        (
            {
                "ollama": {
                    "http://a.example.com": {
                        "llama3": CHAT_ROLE,
                        "mistral": CHAT_ROLE,
                    },
                },
            },
            {
                "http://a.example.com": {
                    "models": [{"name": "llama3"}, {"name": "mistral"}],
                },
            },
            {},
        ),
        # Some required models are missing -> sorted list reported.
        (
            {
                "ollama": {
                    "http://a.example.com": {
                        "llama3": CHAT_ROLE,
                        "mistral": CHAT_ROLE,
                        "phi3": CHAT_ROLE,
                    },
                },
            },
            {
                "http://a.example.com": {"models": [{"name": "llama3"}]},
            },
            {
                "ollama": {
                    "http://a.example.com": {
                        "missing_models": ["mistral", "phi3"],
                    },
                },
            },
        ),
        # Server returns an empty 'models' list -> everything is missing.
        (
            {
                "ollama": {
                    "http://a.example.com": {"llama3": CHAT_ROLE},
                },
            },
            {"http://a.example.com": {"models": []}},
            {
                "ollama": {
                    "http://a.example.com": {"missing_models": ["llama3"]},
                },
            },
        ),
        # Multiple URLs: a mix of OK and missing.
        (
            {
                "ollama": {
                    "http://a.example.com": {"llama3": CHAT_ROLE},
                    "http://b.example.com": {"mistral": CHAT_ROLE},
                },
            },
            {
                "http://a.example.com": {
                    "models": [{"name": "llama3"}],
                },
                "http://b.example.com": {"models": []},
            },
            {
                "ollama": {
                    "http://b.example.com": {"missing_models": ["mistral"]},
                },
            },
        ),
    ],
)
@mock.patch("soliplex.cli.audit.ollama.REST_API")
def test__missing_ollama_models_compares_available_to_required(
    rest_api_cls,
    the_installation,
    w_provider_info,
    w_responses,
    exp_errors,
):
    the_installation._all_provider_info = w_provider_info

    instances = {}
    for url, response in w_responses.items():
        instance = mock.Mock()
        instance.get_available_models.return_value = response
        instances[url] = instance

    rest_api_cls.side_effect = lambda url: instances[url]

    found = cli_audit._missing_ollama_models(the_installation)

    assert found == exp_errors

    # Only URLs with a required-model set should have triggered an
    # 'all_models' call.
    expected_calls = [
        mock.call(url)
        for url, models in w_provider_info.get("ollama", {}).items()
        if models
    ]
    assert rest_api_cls.call_args_list == expected_calls


@mock.patch("soliplex.cli.audit.ollama.REST_API")
def test__missing_ollama_models_reports_unreachable_server(
    rest_api_cls,
    the_installation,
):
    the_installation._all_provider_info = {
        "ollama": {
            "http://a.example.com": {"llama3": CHAT_ROLE},
        }
    }

    instance = mock.Mock()
    instance.get_available_models.side_effect = requests.ConnectionError(
        "refused",
    )
    rest_api_cls.return_value = instance

    found = cli_audit._missing_ollama_models(the_installation)

    assert found == {
        "ollama": {
            "http://a.example.com": {"unreachable": "('refused',)"},
        },
    }


def test__unresponsive_ollama_models_all_respond():
    rest_api = mock.Mock()
    models = {"llama3": CHAT_ROLE, "mistral": CHAT_ROLE}

    found = cli_audit._unresponsive_ollama_models(rest_api, models)

    assert found == {}
    assert rest_api.chat_completion.call_args_list == [
        mock.call("llama3"),
        mock.call("mistral"),
    ]


def test__unresponsive_ollama_models_records_failures():
    rest_api = mock.Mock()
    rest_api.chat_completion.side_effect = [
        None,
        requests.ConnectionError("boom"),
    ]
    models = {"llama3": CHAT_ROLE, "mistral": CHAT_ROLE}

    found = cli_audit._unresponsive_ollama_models(rest_api, models)

    assert found == {"mistral": "('boom',)"}


def test__unresponsive_ollama_models_probes_embedding_model():
    # Regression, soliplex#1356: an embedding model answers 400 to a
    # chat completion, so probing it as a chat model reports a healthy
    # model as unresponsive.
    rest_api = mock.Mock()
    models = {"embed-me": EMBEDDING_ROLE}

    found = cli_audit._unresponsive_ollama_models(rest_api, models)

    assert found == {}
    rest_api.embeddings.assert_called_once_with("embed-me")
    rest_api.chat_completion.assert_not_called()


def test__unresponsive_ollama_models_records_embedding_failure():
    rest_api = mock.Mock()
    rest_api.embeddings.side_effect = requests.ConnectionError("boom")
    models = {"embed-me": EMBEDDING_ROLE}

    found = cli_audit._unresponsive_ollama_models(rest_api, models)

    assert found == {"embed-me": "('boom',)"}


def test__unresponsive_ollama_models_skips_rerank_model():
    # Ollama serves no rerank endpoint, so there is nothing to probe:
    # a rerank model must not be reported broken for failing one it
    # never claimed.
    rest_api = mock.Mock()
    models = {"rerank-me": RERANKING_ROLE}

    found = cli_audit._unresponsive_ollama_models(rest_api, models)

    assert found == {}
    rest_api.chat_completion.assert_not_called()
    rest_api.embeddings.assert_not_called()


@mock.patch("soliplex.cli.audit.ollama.REST_API")
def test__missing_ollama_models_checks_responsiveness_when_requested(
    rest_api_cls,
    the_installation,
):
    the_installation._all_provider_info = {
        "ollama": {
            "http://a.example.com": {
                "llama3": CHAT_ROLE,
                "mistral": CHAT_ROLE,
                "phi3": CHAT_ROLE,
            },
        },
    }

    instance = mock.Mock()
    instance.get_available_models.return_value = {
        "models": [{"name": "llama3"}, {"name": "mistral"}],
    }

    # 'llama3' answers; 'mistral' fails. 'phi3' is missing, so never probed.
    def chat_completion(model_name):
        if model_name == "mistral":
            raise requests.ConnectionError("boom")

    instance.chat_completion.side_effect = chat_completion
    rest_api_cls.return_value = instance

    found = cli_audit._missing_ollama_models(
        the_installation,
        check_responsive=True,
    )

    assert found == {
        "ollama": {
            "http://a.example.com": {
                "missing_models": ["phi3"],
                "unresponsive_models": {"mistral": "('boom',)"},
            },
        },
    }
    # Only installed-and-required models are probed for responsiveness.
    assert instance.chat_completion.call_args_list == [
        mock.call("llama3"),
        mock.call("mistral"),
    ]


@mock.patch("soliplex.cli.audit.ollama.REST_API")
def test__missing_ollama_models_responsive_all_ok(
    rest_api_cls,
    the_installation,
):
    the_installation._all_provider_info = {
        "ollama": {
            "http://a.example.com": {"llama3": CHAT_ROLE},
        },
    }

    instance = mock.Mock()
    instance.get_available_models.return_value = {
        "models": [{"name": "llama3"}],
    }
    rest_api_cls.return_value = instance

    found = cli_audit._missing_ollama_models(
        the_installation,
        check_responsive=True,
    )

    assert found == {}
    instance.chat_completion.assert_called_once_with("llama3")


@mock.patch("soliplex.cli.audit.ollama.REST_API")
def test__missing_ollama_models_skips_responsiveness_by_default(
    rest_api_cls,
    the_installation,
):
    the_installation._all_provider_info = {
        "ollama": {
            "http://a.example.com": {"llama3": CHAT_ROLE},
        },
    }

    instance = mock.Mock()
    instance.get_available_models.return_value = {
        "models": [{"name": "llama3"}],
    }
    rest_api_cls.return_value = instance

    found = cli_audit._missing_ollama_models(the_installation)

    assert found == {}
    instance.chat_completion.assert_not_called()


# _audit_ollama_section: ui only
# audit_ollama: command


# --------------------------------------------------------------------------
# The 'databases' section: state of the 'agui' / 'authz' pair
# --------------------------------------------------------------------------
_HEAD = "head-revision"

_DB_STATES = cli_audit.alembic_migrations.DatabaseState


def _report(**kwargs):
    """A 'DatabaseReport' with the boilerplate filled in."""
    kwargs.setdefault("name", cli_util.AUTHZ)
    kwargs.setdefault("dburi", "sqlite+aiosqlite://")
    kwargs.setdefault("head", _HEAD)
    return cli_audit.DatabaseReport(**kwargs)


def _pair_installation(the_installation, tmp_path):
    """Point an installation at its own throwaway file databases."""
    paths = {}
    for db_type, db_pfx in (
        (cli_util.AGUI, "thread_persistence"),
        (cli_util.AUTHZ, "authorization"),
    ):
        paths[db_type] = db_path = tmp_path / f"{db_type}.sqlite"
        setattr(
            the_installation._config,
            f"{db_pfx}_async_dburi",
            f"sqlite+aiosqlite:///{db_path}",
        )
        setattr(
            the_installation._config,
            f"{db_pfx}_sync_dburi",
            f"sqlite:///{db_path}",
        )
    return the_installation, paths


@pytest.mark.parametrize(
    "state, revision, known, error, expected",
    [
        (_DB_STATES.STAMPED, _HEAD, True, None, False),
        (_DB_STATES.STAMPED, "older", True, None, True),
        # A stamp this release does not have is ahead, not behind.
        (_DB_STATES.STAMPED, "newer", False, None, False),
        # Neither an empty nor an unstamped database is 'behind' anything.
        (_DB_STATES.EMPTY, None, True, None, False),
        (_DB_STATES.UNSTAMPED, None, True, None, False),
        (None, None, True, "OperationalError: refused", False),
    ],
)
def test_database_report_behind_head(state, revision, known, error, expected):
    report = _report(state=state, revision=revision, known=known, error=error)

    assert report.behind_head is expected


@pytest.mark.parametrize(
    "state, revision, known, expected",
    [
        (_DB_STATES.STAMPED, "newer", False, True),
        (_DB_STATES.STAMPED, _HEAD, True, False),
        (_DB_STATES.STAMPED, "older", True, False),
        # An unstamped database has no revision to be ahead with.
        (_DB_STATES.UNSTAMPED, None, True, False),
        (_DB_STATES.EMPTY, None, True, False),
    ],
)
def test_database_report_downgrade_required(state, revision, known, expected):
    report = _report(state=state, revision=revision, known=known)

    assert report.downgrade_required is expected


@pytest.mark.parametrize(
    "state, revision, error, expected",
    [
        (_DB_STATES.STAMPED, _HEAD, None, f"OK ({_HEAD})"),
        (
            _DB_STATES.STAMPED,
            "older",
            None,
            f"behind head (older -> {_HEAD})",
        ),
        (
            _DB_STATES.EMPTY,
            None,
            None,
            "not created (the next writable open creates it)",
        ),
        (None, None, "OperationalError: refused", None),
        (_DB_STATES.UNSTAMPED, None, None, None),
    ],
)
def test__database_summary(state, revision, error, expected):
    report = _report(state=state, revision=revision, error=error)

    found = cli_audit._database_summary(report)

    if expected is not None:
        assert found == expected
    elif error is not None:
        assert found == f"ERROR: unreachable: {error}"
    else:
        assert found.startswith("ERROR: ")
        assert cli_audit.BOOTSTRAP_SCRIPT in found


def test__database_summary_for_a_stamp_needing_a_downgrade():
    report = _report(state=_DB_STATES.STAMPED, revision="newer", known=False)

    found = cli_audit._database_summary(report)

    assert found.startswith("ERROR: newer: ")
    assert "downgrade has to come from" in found
    # Deliberately suggests no command: the revisions needed to move this
    # database are not in this release, so none can be run here.
    assert "alembic" not in found


def test__database_findings_reports_an_unreachable_database():
    reports = {
        cli_util.AGUI: _report(
            name=cli_util.AGUI, state=_DB_STATES.STAMPED, revision=_HEAD
        ),
        cli_util.AUTHZ: _report(error="OperationalError: refused"),
    }

    found = cli_audit._database_findings(reports)

    assert found == {
        "databases": {
            cli_util.AUTHZ: {"unreachable": "OperationalError: refused"}
        }
    }


def test__database_findings_reports_an_unstamped_database():
    reports = {
        cli_util.AGUI: _report(name=cli_util.AGUI, state=_DB_STATES.UNSTAMPED),
        cli_util.AUTHZ: _report(state=_DB_STATES.STAMPED, revision=_HEAD),
    }

    found = cli_audit._database_findings(reports)

    assert (
        cli_audit.BOOTSTRAP_SCRIPT
        in (found["databases"][cli_util.AGUI]["unstamped"])
    )
    assert cli_util.AUTHZ not in found["databases"]


@pytest.mark.parametrize(
    "state, revision",
    [
        # At head, and behind head: neither is a finding, because the next
        # writable open migrates a database that is behind.
        (_DB_STATES.STAMPED, _HEAD),
        (_DB_STATES.STAMPED, "older"),
        (_DB_STATES.EMPTY, None),
    ],
)
def test__database_findings_stays_quiet(state, revision):
    reports = {
        name: _report(name=name, state=state, revision=revision)
        for name in (cli_util.AGUI, cli_util.AUTHZ)
    }

    found = cli_audit._database_findings(reports)

    assert found == {}


def test__database_findings_reports_a_stamp_needing_a_downgrade():
    reports = {
        cli_util.AGUI: _report(
            name=cli_util.AGUI,
            state=_DB_STATES.STAMPED,
            revision="newer",
            known=False,
        ),
        cli_util.AUTHZ: _report(state=_DB_STATES.STAMPED, revision=_HEAD),
    }

    found = cli_audit._database_findings(reports)

    assert found["databases"][cli_util.AGUI]["downgrade_required"].startswith(
        "newer: "
    )
    assert cli_util.AUTHZ not in found["databases"]


def test__database_reports_returns_the_cached_probe(ctx, the_installation):
    already = {"agui": object()}
    ctx.obj["database_reports"] = already

    found = cli_audit._database_reports(ctx, the_installation)

    assert found is already


@mock.patch.object(cli_audit.alembic_migrations, "head_revision")
@mock.patch.object(cli_audit, "_probe_database", new_callable=mock.AsyncMock)
def test__database_reports_probes_and_caches(
    probe, head_revision, ctx, the_installation
):
    head_revision.return_value = _HEAD
    probe.side_effect = [
        (_DB_STATES.STAMPED, _HEAD),
        (_DB_STATES.UNSTAMPED, None),
    ]

    found = cli_audit._database_reports(ctx, the_installation)

    assert found[cli_util.AGUI].state is _DB_STATES.STAMPED
    assert found[cli_util.AGUI].revision == _HEAD
    assert found[cli_util.AUTHZ].state is _DB_STATES.UNSTAMPED
    assert all(report.head == _HEAD for report in found.values())
    assert ctx.obj["database_reports"] is found


@mock.patch.object(cli_audit.alembic_migrations, "head_revision")
@mock.patch.object(cli_audit, "_probe_database", new_callable=mock.AsyncMock)
def test__database_reports_maps_an_uncreated_database_to_empty(
    probe, head_revision, ctx, the_installation
):
    head_revision.return_value = _HEAD
    probe.side_effect = cli_util.DatabaseNotCreated("authz")

    found = cli_audit._database_reports(ctx, the_installation)

    assert [report.state for report in found.values()] == [
        _DB_STATES.EMPTY,
        _DB_STATES.EMPTY,
    ]
    assert all(report.error is None for report in found.values())


@mock.patch.object(cli_audit.alembic_migrations, "head_revision")
@mock.patch.object(cli_audit, "_probe_database", new_callable=mock.AsyncMock)
def test__database_reports_records_an_unreachable_database(
    probe, head_revision, ctx, the_installation
):
    head_revision.return_value = _HEAD
    probe.side_effect = RuntimeError("refused")

    found = cli_audit._database_reports(ctx, the_installation)

    assert all(
        report.error == "RuntimeError: refused" for report in found.values()
    )
    assert all(report.state is None for report in found.values())


def test__probe_database_reads_a_migrated_database(the_installation, tmp_path):
    # Driven against real files: the probe has to agree with what alembic
    # actually wrote, which a mocked connection could not show.
    the_installation, paths = _pair_installation(the_installation, tmp_path)
    cli_audit.alembic_migrations.upgrade(
        "head",
        dburis={name: f"sqlite:///{path}" for name, path in paths.items()},
    )

    state, revision = cli_audit.asyncio.run(
        cli_audit._probe_database(the_installation, cli_util.AUTHZ)
    )

    assert state is _DB_STATES.STAMPED
    assert revision == cli_audit.alembic_migrations.head_revision()


def test__probe_database_reads_an_unstamped_database(
    the_installation, tmp_path
):
    the_installation, paths = _pair_installation(the_installation, tmp_path)
    cli_audit.alembic_migrations.upgrade(
        "head",
        dburis={name: f"sqlite:///{path}" for name, path in paths.items()},
    )
    engine = sa.create_engine(f"sqlite:///{paths[cli_util.AUTHZ]}")
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    f"DROP TABLE {cli_audit.alembic_migrations.VERSION_TABLE}"
                )
            )
    finally:
        engine.dispose()

    state, revision = cli_audit.asyncio.run(
        cli_audit._probe_database(the_installation, cli_util.AUTHZ)
    )

    assert state is _DB_STATES.UNSTAMPED
    assert revision is None


# _audit_databases_section: ui only
# audit_databases: command
