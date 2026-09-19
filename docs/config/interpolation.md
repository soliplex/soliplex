# Environment / Secret Interpolation

An installation resolves two kinds of marker found in configuration
values: `secret:NAME` from the its [secrets](secrets.md), and
`env:NAME` from the its [environment](environment.md).

Which markers a given field honors, and how much of the value they may occupy,
is that field's "interpolation contract".

Each config class carries the contract on the fields themselves, in
`dataclasses.field(metadata=...)`.:

- `config.interpolation.resolve_field` reads a field's declaration to
  decide how to substitute values from the installation.

- `soliplex-cli audit` reads the same declarations to decide whether a marker
  in the configuration will resolve as written.

This page defines the contract for an out-of-tree configuration class, e.g.:
a tool config, an MCP toolset config, or an agent config, registered
through [`meta`](meta.md).

For the inventory of which *shipped* fields interpolate what, see
[Installation Secret / Environment
Interpolation](installation.md#installation-secret-environment-interpolation).

## Declaring a contract

Everything below lives in `soliplex.config.interpolation`:

```python
from soliplex.config import interpolation as config_interp
```

Six shorthands cover the combinations which occur in practice. Each takes
the keywords `dataclasses.field()` takes -- `default`, `default_factory`,
`repr`, `compare` -- and forwards them verbatim, so a field with no
default stays required:

| Shorthand | Honors | Value must be |
|---|---|---|
| `secret_whole_field()` | `secret:` | exactly one marker; anything else is rejected |
| `secret_whole_or_literal_field()` | `secret:` | exactly one marker, or a literal |
| `secret_embedded_field()` | `secret:` | anything; markers substituted in place |
| `env_whole_or_literal_field()` | `env:` | exactly one marker, or a literal |
| `env_embedded_field()` | `env:` | anything; markers substituted in place |
| `both_embedded_field()` | both | anything; markers substituted in place |
| `no_interpolation_field()` | neither | no interpolation is to be performed |

Declaring nothing at all is a third state, and means something different:
see [Opting in](#opting-in) below.

### The three axes

The shorthands are `functools.partial` over `interpolated_field()`, which
takes the axes directly. Reach for it when no shorthand fits -- most
often because the value is a list or a mapping rather than a string:

```python
env: dict[str, str] = config_interp.interpolated_field(
    kinds=config_interp.MarkerKind.BOTH,
    arity=config_interp.MarkerArity.EMBEDDED,
    shape=config_interp.ValueShape.MAPPING,
    default_factory=dict,
)
```

`kinds` -- which marker styles the field honors:

| `MarkerKind` | Meaning |
|---|---|
| `SECRET` | `secret:` only |
| `ENVIRONMENT` | `env:` only |
| `BOTH` | either, and both may appear in one value |
| `None` | none: the field is literal text |

`arity` -- how much of the value a marker may occupy:

| `MarkerArity` | Meaning |
|---|---|
| `EMBEDDED` | zero or more markers anywhere within the value |
| `WHOLE_REQUIRED` | the whole value is one marker; anything else is rejected |
| `WHOLE_OPTIONAL` | the whole value may be one marker; anything else is a literal |

`shape` -- which strings within the value are examined:

| `ValueShape` | Meaning |
|---|---|
| `SCALAR` | the value itself |
| `SEQUENCE` | each string item |
| `MAPPING` | each string value; keys are never interpolated |

The shorthands all pin `shape=ValueShape.SCALAR`.

Three combinations are rejected at class-definition time rather than at
resolution time, so a mistake surfaces on import:

- a literal field (`kinds=None`) which also names an `arity` or a `shape`
- an interpolating field which omits its `arity` or its `shape`
- `kinds=MarkerKind.BOTH` with a whole-value arity -- a whole value is one
  marker, and one marker has one kind

### Private fields

Where the field is private and read through a property, name the YAML key
and the property so audit findings can quote what an operator actually
wrote:

```python
_dburi: str = config_interp.both_embedded_field(
    public_name="thread_persistence_db.sync_dburi",
    accessor="thread_persistence_sync_dburi",
    default=None,
)
```

Neither is consulted to resolve a value; they serve to document the field's
sourc for operators and for audit messages.

## Resolving interpolations

`config_interp.resolve_field` returns the value with its interpolation
markers substituted:

```python
@property
def api_key(self) -> str:
    return config_interp.resolve_field(self, "_api_key")
```

- `resolve_field` finds the installation through the config's own
  `_installation_config` attribute, which Soliplex sets when it loads a
   child config.

  To resolve a field for a config which does not have its
  `_installation_config` set (for instance, for the installation config
  itself), pass the `installation_config=` keyword argment explicitly.

- `resolve_field` preserves the field's declared shape:
  resolving a `SEQUENCE` field returns a list, while resolving a `MAPPING`
  field returns a dict with its keys untouched, and its values interpolated.

- `resolve_field` does not mutate the field, so the config keeps
  its markers.  Application code should do likewise:

  - Resolve inside a property, not in `__post_init__`.

  - Have `as_yaml` emit the unresolved field, never the resolving property.
    Doing otherwise writes resolved secrets / env vars to disk.

  - If the field is not private, give the resolving accessor a different name
    from the field it reads (`model_name` / `llm_model_name`), so a later edit
    does point `as_yaml` at the resolving one by accident.

- `resolve_field` raises rather than guessing:

| Raised | When |
|---|---|
| `FieldDeclaresNoInterpolation` | the field does not have a declaration |
| `NoSuchField` | the name does not name a field |
| `WholeFieldNeedsInstallationConfig` | a `WHOLE_REQUIRED` field has no installation to resolve against |

- `resolve_field` returns the value for a literal field (`kinds=None`)
  unchanged.

## Auditing interpolations

`soliplex-cli audit` walks the configs each section owns and reports every
marker which will not resolve as written. Auditing reads the declarations,
and checks whether the installation declares a name, but does *not* resolve
the field value: reading only declarations allows auding based on the
configuration alone, e.g. in CI.

Three findings, one per way a marker fails to do what its author meant:

| Code | Meaning |
|---|---|
| `undeclared_name` | the field interpolates this kind, but the installation declares no such name -- raises when a request first reaches it |
| `ignored_marker` | the field does not interpolate, or not the whole value it was given, so the marker is passed through verbatim -- silent |
| `wrong_kind` | the field interpolates, but not this marker's kind -- an `env:` marker in a secrets-only field, or vice-versa |

Findings surface under the section owning the stanza:

- `installation_interpolation` (fields in the `InstallationConfig` itself).

- `logfire_interpolation` (fields in the ICs' `logfire` stanza)

- `oidc_interpolation` (fields in one of the `OIDC` config files)

- `rooms_interpolation` (fields in one of the room config files)

- `completions_interpolation` (fields in one of the completion config files)

Each finding names the config type, its id, the file it came from,
the field, and -- for a sequence or mapping -- the element
holding the marker.

A field still holding the default its class declares is exempt from
`undeclared_name`: a marker in a default is the framework's own
placeholder, not something an operator typed.

## Opting in

The three finding classes are gated differently, and the asymmetry is
what keeps an unannotated extension quiet.

`undeclared_name` and `wrong_kind` fire on every annotated field,
including those inherited from a base class. a subclass resolves an
inherited field exactly as its base does, so it is checked the same way.

`ignored_marker` fires on unannotated fields, but only for a class
which declares at least one interpolation *of its own*.  This choice allows
third-party extensions to adopt interpolation annotations when convenient,
without triggering audit findings in existing configurations until they do.

The practical consequence for an out-of-tree config class: annotate a
config class all at once, or not at all.

- With no annotations, a class which resolves markers through hand-written
  properties keeps working, with no findings.

- With *any* annotations, any string value property container markers
  is checked, even if not annotated; use `no_interpolation_field()` on
  free-text fields to suppress the check.

## A worked example

A tool config resolving a Gitea host, organization and access token:

```python
import dataclasses

from soliplex.config import interpolation as config_interp


@dataclasses.dataclass(kw_only=True)
class CreateGiteaIssueToolConfig:
    tool_name: str = "my_package.tools.create_gitea_issue"

    _host: str = config_interp.env_whole_or_literal_field(default=None)
    _owner: str = config_interp.env_whole_or_literal_field(default=None)
    _token: str = config_interp.secret_whole_field(default=None)

    # Free text: declared literal, so marker-like prose is not reported.
    description: str = config_interp.no_interpolation_field(default="")

    _installation_config: object = None

    @property
    def host(self) -> str:
        return config_interp.resolve_field(self, "_host")

    @property
    def owner(self) -> str:
        return config_interp.resolve_field(self, "_owner")

    @property
    def token(self) -> str:
        return config_interp.resolve_field(self, "_token")

    @property
    def as_yaml(self) -> dict:
        # The raw fields, so a dump never writes a resolved secret.
        return {
            "tool_name": self.tool_name,
            "host": self._host,
            "owner": self._owner,
            "token": self._token,
            "description": self.description,
        }
```

Registered through
[`meta.tool_configs`](meta.md#registering-tool-configuration-classes),
this class is now audited alongside Soliplex's own: an installation which
writes `token: "secret:GITEA_TOKEN"` without declaring `GITEA_TOKEN` gets
an `undeclared_name` finding naming the file and the key, rather than a
failure on the first request that reaches the tool.
