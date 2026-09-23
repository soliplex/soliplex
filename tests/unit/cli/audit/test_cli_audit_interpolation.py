from __future__ import annotations

import dataclasses
import pathlib
from unittest import mock

import pytest

from soliplex import installation
from soliplex.cli.audit import interpolation as audit_interpolation
from soliplex.config import interpolation as config_interp

A_CONFIG_PATH = pathlib.Path("/tmp/installation.yaml")


# ---------------------------------------------------------------------------
# Interpolation findings
# ---------------------------------------------------------------------------
_SECRET = config_interp.MarkerKind.SECRET
_ENVIRONMENT = config_interp.MarkerKind.ENVIRONMENT
_BOTH = config_interp.MarkerKind.BOTH
_EMBEDDED = config_interp.MarkerArity.EMBEDDED
_SEQUENCE = config_interp.ValueShape.SEQUENCE
_MAPPING = config_interp.ValueShape.MAPPING
_UNDECLARED = audit_interpolation._InterpolationFindingCode.UNDECLARED_NAME
_IGNORED = audit_interpolation._InterpolationFindingCode.IGNORED_MARKER
_WRONG_KIND = audit_interpolation._InterpolationFindingCode.WRONG_KIND
_INTERP_CFG_NAME = f"{__name__}._InterpCfg"
_DERIVED_CFG_NAME = f"{__name__}._DerivedInterpCfg"

_DECLARED = audit_interpolation._InterpolationDeclarations(
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

    return audit_interpolation._InterpolationFinding(**kw)


def test__interpolation_declarations_from_installation_config():
    installation_config = mock.Mock(
        secrets_map={"A_SECRET": object()},
        environment={"AN_ENV": "a value"},
    )
    klass = audit_interpolation._InterpolationDeclarations

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
    found = list(audit_interpolation._iter_markers(w_text))

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
    found = audit_interpolation._whole_marker(w_text)

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
    found = list(audit_interpolation._iter_field_strings("field", w_value))

    assert found == exp_strings


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

    found = audit_interpolation._holds_declared_default(config, w_field_name)

    assert found is exp_holds


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

    found = audit_interpolation._field_interpolation_findings(
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

    found = audit_interpolation._field_interpolation_findings(
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

    found = audit_interpolation._config_interpolation_findings(
        config, _DECLARED
    )

    assert found == exp_findings


def test__iter_installation_interpolation_configs():
    agent_config = _InterpCfg(id="the-agent")
    installation_config = _InterpInstallationCfg(
        id="the-installation",
        agent_configs=[agent_config],
    )

    found = list(
        audit_interpolation._iter_installation_interpolation_configs(
            installation_config
        )
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

    found = list(
        audit_interpolation._iter_room_interpolation_configs(room_config)
    )

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
        audit_interpolation._iter_completion_interpolation_configs(
            completion_config
        )
    )

    assert [config.id for config in found] == exp_ids


def test__interpolation_findings():
    configs = [
        _InterpCfg(id="first", secret_whole="secret:MISSING"),
        _InterpCfg(id="second", secret_whole="secret:KNOWN_SECRET"),
        _InterpCfg(id="third", env_embedded="env:MISSING_ENV"),
    ]

    found = audit_interpolation._interpolation_findings(configs, _DECLARED)

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

    found = audit_interpolation._installation_declarations(the_installation)

    assert found.secrets == frozenset({"A_SECRET"})
    assert found.environment == frozenset({"AN_ENV"})


@pytest.mark.parametrize("w_finding", [False, True])
def test__invalid_installation_interpolations(w_finding):
    marker = "secret:MISSING" if w_finding else "secret:KNOWN_SECRET"
    agent_config = _InterpCfg(id="the-agent", secret_whole=marker)
    the_installation = _the_installation(agent_configs=[agent_config])

    found = audit_interpolation._invalid_installation_interpolations(
        the_installation
    )

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

    found = audit_interpolation._invalid_logfire_interpolations(
        the_installation
    )

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

    found = audit_interpolation._invalid_oidc_interpolations(the_installation)

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

    found = audit_interpolation._invalid_room_interpolations(the_installation)

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

    found = audit_interpolation._invalid_completion_interpolations(
        the_installation
    )

    if w_finding:
        assert found == {
            "completions_interpolation": [
                _finding(config_id="the-agent").as_json,
            ],
        }
    else:
        assert found == {}


# _print_interpolation_findings: ui only
