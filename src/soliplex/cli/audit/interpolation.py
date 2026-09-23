from __future__ import annotations

import dataclasses
import enum
import pathlib

from soliplex import installation
from soliplex.config import _utils as config_utils
from soliplex.config import interpolation as config_interp

# ---------------------------------------------------------------------------
# Interpolation markers which will not resolve as written.
#
# Read declarations only: ask whether a marker names something the
# installation declares, never whether that name resolves.  Resolving runs
# a secret's source chain, which may spawn a subprocess, and ties the check
# to the host the installation runs on.  Reading declarations keeps it
# answerable from the configuration alone.
# ---------------------------------------------------------------------------


class _InterpolationFindingCode(enum.StrEnum):
    """Why one marker will not resolve as written."""

    #: The field interpolates this marker's kind, but the installation
    #: declares no such name.  Raises when a request first reaches it.
    UNDECLARED_NAME = "undeclared_name"

    #: The field does not interpolate at all, or does not interpolate the
    #: whole value it was given, so the marker is passed through verbatim.
    #: Silent.
    IGNORED_MARKER = "ignored_marker"

    #: The field interpolates, but not this marker's kind -- an 'env:'
    #: marker in a secrets-only field, say.
    WRONG_KIND = "wrong_kind"


InterpNames = frozenset[str]


InterpNamesByKind = dict[str, InterpNames]


@dataclasses.dataclass(kw_only=True)
class _InterpolationDeclarations:
    """The names an installation declares.

    Hold names only: a value is never read.
    """

    secrets: InterpNames
    environment: InterpNames
    _names_by_kind: InterpNamesByKind | None = None

    @classmethod
    def from_installation_config(cls, installation_config):
        return cls(
            secrets=frozenset(installation_config.secrets_map),
            environment=frozenset(installation_config.environment),
        )

    def __post_init__(self):
        self._names_by_kind = {
            config_interp.MarkerKind.ENVIRONMENT: self.environment,
            config_interp.MarkerKind.SECRET: self.secrets,
        }

    @property
    def names_by_kind(self) -> InterpNamesByKind:
        return self._names_by_kind

    def declares(self, kind, name: str) -> bool:
        return name in self.names_by_kind[kind]


@dataclasses.dataclass(frozen=True, kw_only=True)
class _InterpolationFinding:
    """One marker which will not resolve as written.

    'location' names the element holding the marker for a sequence or
    mapping field, and is 'None' for a scalar.  See `_iter_field_strings`
    below for how the strings are constructed.

    'config_key' is the YAML key, which differs from 'field_name' for
    a private field.
    """

    code: _InterpolationFindingCode
    config_type: config_utils.DottedName
    config_id: str | None
    config_path: pathlib.Path | None
    field_name: str
    config_key: str
    marker_kind: config_interp.MarkerKind
    marker_name: str
    location: str | None = None

    def __str__(self) -> str:
        return _interpolation_finding_line(self.as_json)

    @property
    def as_json(self) -> dict:
        """Return a mapping suitable for the '--quiet' error report."""
        return {
            "code": str(self.code),
            "config_type": self.config_type,
            "config_id": self.config_id,
            "config_path": (
                str(self.config_path) if self.config_path else None
            ),
            "field_name": self.field_name,
            "config_key": self.config_key,
            "marker_kind": self.marker_kind.name.lower(),
            "marker_name": self.marker_name,
            "location": self.location,
        }


def _interpolation_finding_line(as_json: dict) -> str:
    """Return the one-line display form of a finding mapping."""
    where = as_json["location"] or as_json["config_key"]
    owner = as_json["config_id"] or as_json["config_type"]

    return (
        f"{owner}: {where}: {as_json['code']} "
        f"({as_json['marker_kind']}:{as_json['marker_name']})"
    )


def _iter_markers(text: str):
    """Yield '(kind, name)' for each marker found in 'text'."""

    for match in config_interp.SECRET_RE.finditer(text):
        yield config_interp.MarkerKind.SECRET, match.group("secret_name")

    for match in config_interp.ENVIRONMENT_RE.finditer(text):
        yield config_interp.MarkerKind.ENVIRONMENT, match.group("env_name")


def _whole_marker(text: str):
    """Return '(kind, name)' when 'text' is exactly one marker, else None."""
    match = config_interp.SECRET_RE.fullmatch(text)

    if match is not None:
        return config_interp.MarkerKind.SECRET, match.group("secret_name")

    match = config_interp.ENVIRONMENT_RE.fullmatch(text)

    if match is not None:
        return config_interp.MarkerKind.ENVIRONMENT, match.group("env_name")

    return None


def _iter_field_strings(field_name: str, value):
    """Yield '(location, text)' for each string the value holds.

    Walk a sequence or mapping without consulting a declared shape, so an
    unannotated field is read the same way as an annotated one.
    """
    if isinstance(value, str):
        yield None, value
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str):
                yield f"{field_name}[{key!r}]", item
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            if isinstance(item, str):
                yield f"{field_name}[{index}]", item


def _make_interpolation_finding(
    config, field_name, spec, code, marker, location
):
    kind, name = marker
    public_name = spec.public_name if spec is not None else None

    return _InterpolationFinding(
        code=code,
        config_type=config_utils._dotted_name(type(config)),
        config_id=getattr(config, "id", None),
        config_path=getattr(config, "_config_path", None),
        field_name=field_name,
        config_key=public_name or field_name,
        marker_kind=kind,
        marker_name=name,
        location=location,
    )


def _annotated_field_findings(config, field_name, spec, declarations):
    """Report markers an interpolating field will not resolve.

    A whole-value field consults only a value which is entirely one
    marker.  Where such a field carries a marker inside a longer value,
    report it as ignored when the field tolerates a literal; a field
    which requires a marker raises at runtime instead, and needs no
    finding here.
    """
    findings = []
    embedded = spec.arity is config_interp.MarkerArity.EMBEDDED
    tolerates_literal = spec.arity is config_interp.MarkerArity.WHOLE_OPTIONAL

    for location, text in _iter_field_strings(
        field_name, getattr(config, field_name)
    ):
        if embedded:
            markers = list(_iter_markers(text))
        else:
            whole = _whole_marker(text)

            if whole is not None:
                markers = [whole]
            else:
                markers = []

                if tolerates_literal:
                    findings.extend(
                        _make_interpolation_finding(
                            config,
                            field_name,
                            spec,
                            _InterpolationFindingCode.IGNORED_MARKER,
                            marker,
                            location,
                        )
                        for marker in _iter_markers(text)
                    )

        for marker in markers:
            kind, name = marker

            if not kind & spec.kinds:
                code = _InterpolationFindingCode.WRONG_KIND
            elif declarations.declares(kind, name):
                continue
            else:
                code = _InterpolationFindingCode.UNDECLARED_NAME

            findings.append(
                _make_interpolation_finding(
                    config, field_name, spec, code, marker, location
                )
            )

    return findings


def _unannotated_field_findings(config, field_name):
    """Report a whole-value marker in a field which declares nothing.

    Consider only a value which is entirely one marker: an installation
    holds prose -- a description, a system prompt -- in which text
    resembling a marker is ordinary.
    """
    findings = []

    for location, text in _iter_field_strings(
        field_name, getattr(config, field_name)
    ):
        marker = _whole_marker(text)

        if marker is not None:
            findings.append(
                _make_interpolation_finding(
                    config,
                    field_name,
                    None,
                    _InterpolationFindingCode.IGNORED_MARKER,
                    marker,
                    location,
                )
            )

    return findings


def _holds_declared_default(config, field_name) -> bool:
    """True when the field still holds the default its class declares."""
    field = type(config).__dataclass_fields__[field_name]

    return (
        field.default is not dataclasses.MISSING
        and getattr(config, field_name) == field.default
    )


def _field_interpolation_findings(config, field_name, declarations):
    """Return findings for one field of one config.

    Report an unannotated field's markers unconditionally.  Whether a
    class is checked that way at all is decided by
    '_config_interpolation_findings', which holds the opt-in rule.

    Drop an undeclared-name finding for a field still holding the default
    its class declares: six 'LogfireConfig' fields default to an
    'env:LOGFIRE_*' marker, which Logfire itself falls back on when the
    installation declares no such name.  A marker the operator wrote is
    reported as usual, and a stock default which names the wrong kind
    stays a finding either way.
    """
    spec = config_interp.spec_for(config, field_name)

    if spec is None:
        findings = _unannotated_field_findings(config, field_name)
    elif spec.kinds is None:
        findings = []
    else:
        findings = _annotated_field_findings(
            config, field_name, spec, declarations
        )

        if _holds_declared_default(config, field_name):
            findings = [
                finding
                for finding in findings
                if finding.code
                is not _InterpolationFindingCode.UNDECLARED_NAME
            ]

    return findings


def _config_interpolation_findings(config, declarations):
    """Return findings for every field of one config.

    Check an annotated field wherever it is declared, inherited included:
    a subclass resolves an inherited field exactly as its base does.

    Check an *un*annotated field only for a class which declares at least
    one interpolation of its own.  A class declaring none has not adopted
    the vocabulary, and its fields are not ours to judge -- which keeps an
    out-of-tree config silent until it opts in.
    """
    klass = type(config)
    annotated = dict(config_interp.iter_specs(klass))
    findings = []

    for field_name in sorted(annotated):
        findings.extend(
            _field_interpolation_findings(config, field_name, declarations)
        )

    if any(True for _ in config_interp.iter_own_specs(klass)):
        own = config_interp.own_field_names(klass)

        for field_name in sorted(own - set(annotated)):
            findings.extend(
                _field_interpolation_findings(config, field_name, declarations)
            )

    return findings


def _iter_installation_interpolation_configs(installation_config):
    """Yield the configs whose markers belong to 'installation.yaml'.

    'logfire_config:' and the OIDC stanzas live in the same file, but are
    reported by their own sections.
    """
    yield installation_config
    yield from installation_config.agent_configs


def _iter_room_interpolation_configs(room_config):
    """Yield the configs whose markers belong to a room's YAML."""
    yield room_config

    if room_config.agent_config is not None:
        yield room_config.agent_config

    yield from room_config.tool_configs.values()
    yield from room_config.mcp_client_toolset_configs.values()

    for quiz_config in room_config.quizzes:
        yield quiz_config

        if quiz_config.judge_agent is not None:
            yield quiz_config.judge_agent


def _iter_completion_interpolation_configs(completion_config):
    """Yield the configs whose markers belong to a completion's YAML."""
    yield completion_config

    if completion_config.agent_config is not None:
        yield completion_config.agent_config

    yield from completion_config.tool_configs.values()
    yield from completion_config.mcp_client_toolset_configs.values()


def _interpolation_findings(configs, declarations) -> list[dict]:
    """Return the findings for 'configs', as report mappings."""
    return [
        finding.as_json
        for config in configs
        for finding in _config_interpolation_findings(config, declarations)
    ]


def _installation_declarations(
    the_installation: installation.Installation,
) -> _InterpolationDeclarations:
    """Return the names the installation declares.

    Read the declarations, never the values: a secret source may spawn a
    subprocess, which would tie the audit to the host it runs on.
    """
    return _InterpolationDeclarations.from_installation_config(
        the_installation._config
    )


def _invalid_installation_interpolations(
    the_installation: installation.Installation,
) -> dict:
    installation_config = the_installation._config
    findings = _interpolation_findings(
        _iter_installation_interpolation_configs(installation_config),
        _installation_declarations(the_installation),
    )

    if findings:
        return {"installation_interpolation": findings}

    return {}


def _invalid_logfire_interpolations(
    the_installation: installation.Installation,
) -> dict:
    logfire_config = the_installation._config.logfire_config
    findings = []

    if logfire_config is not None:
        findings = _interpolation_findings(
            [logfire_config],
            _installation_declarations(the_installation),
        )

    if findings:
        return {"logfire_interpolation": findings}

    return {}


def _invalid_oidc_interpolations(
    the_installation: installation.Installation,
) -> dict:
    findings = _interpolation_findings(
        the_installation.oidc_auth_system_configs,
        _installation_declarations(the_installation),
    )

    if findings:
        return {"oidc_interpolation": findings}

    return {}


def _invalid_room_interpolations(
    the_installation: installation.Installation,
) -> dict:
    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_rooms = the_installation._config.room_configs
    declarations = _installation_declarations(the_installation)
    findings = []

    for room_config in available_rooms.values():
        findings.extend(
            _interpolation_findings(
                _iter_room_interpolation_configs(room_config),
                declarations,
            )
        )

    if findings:
        return {"rooms_interpolation": findings}

    return {}


def _invalid_completion_interpolations(
    the_installation: installation.Installation,
) -> dict:
    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_completions = the_installation._config.completion_configs
    declarations = _installation_declarations(the_installation)
    findings = []

    for completion_config in available_completions.values():
        findings.extend(
            _interpolation_findings(
                _iter_completion_interpolation_configs(completion_config),
                declarations,
            )
        )

    if findings:
        return {"completions_interpolation": findings}

    return {}


def _print_interpolation_findings(
    tc_print,
    errors: dict,
) -> None:  # pragma NO COVER UI ONLY
    """Print a block naming each finding, or nothing when there are none."""
    for findings in errors.values():
        tc_print()
        tc_print("Interpolation")

        for finding in findings:
            tc_print(f"- {_interpolation_finding_line(finding)}")

            config_path = finding["config_path"]

            if config_path is not None:
                tc_print(f"    {config_path}")

        tc_print()
