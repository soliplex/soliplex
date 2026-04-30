# AG-UI Features

Soliplex uses the [AG-UI protocol](https://docs.ag-ui.com/) to communicate
with web and TUI clients. AG-UI carries a free-form `state` mapping
between client and server; **AG-UI features** are the contracts that
define the schema and write semantics for individual top-level keys
within that mapping.

Each feature is described by an `AGUI_Feature` dataclass
(`soliplex.config.agui.AGUI_Feature`) carrying:

- `name` -- the key under which the feature's data appears in the
  AG-UI `state` mapping.
- `model_klass` -- a Pydantic model class defining the schema for
  the feature's data.
- `source` -- one of `client`, `server`, or `either`, describing
  which party is allowed to write the feature's portion of the
  AG-UI state.

## The `AGUI_FEATURES_BY_NAME` Registry

`soliplex.config.agui.AGUI_FEATURES_BY_NAME` is a module-level
`dict[str, AGUI_Feature]` that maps each feature's `name` to its
registration. The registry starts empty and is populated by mutation
during application startup.

The registry is the single source of truth for "which AG-UI features
does this installation know about?" Code elsewhere in Soliplex (and
in the TUI client) looks features up here whenever it needs the
schema, default value, or write-direction for a particular state key.

## How the Registry Gets Populated

The registry is filled from three sources, applied in this order
during installation load:

### 1. Soliplex-Builtin Registrations

Importing `soliplex.config.skills` (which happens transitively
whenever `soliplex.config` is imported) registers Soliplex's own
built-in features. As of this writing, that includes the
`bwrap-sandbox` skill's state namespace, registered with
`source=server`.

These registrations happen at module-import time and are present
before any installation YAML is parsed.

### 2. Entrypoint Skill Discovery

When an `InstallationConfig` is loaded,
`_load_entrypoint_skill_configs` walks every Haiku skill discovered
via Python entry points. For each skill whose `state_namespace` is
set, it adds an entry to the registry using `skill.state_type` as
`model_klass` and `server` as `source` -- but only if the
`state_namespace` is **not already present** in the registry. This
makes entrypoint discovery a no-op for features that have already
been registered by other means.

### 3. The `meta.agui_features` YAML Stanza

Finally, the
[`meta.agui_features`](meta.md#registering-ag-ui-feature-classes)
stanza of the installation YAML is processed by
`InstallationConfigMeta.__post_init__`. Each entry produces an
`AGUI_Feature` which is **unconditionally** written into the
registry, overwriting any earlier entry with the same `name`.

This ordering means installation YAML wins over both built-in
registrations and entrypoint discovery, so site operators can
override the default `model_klass` or `source` for any feature
shipped by Soliplex or by an installed skill package.

## How the Application Uses the Registry After Startup

Once the installation is loaded, the registry is read (never
written) by the runtime. The main consumers are:

### `InstallationConfig.agui_features`

The `InstallationConfig.agui_features` property simply returns
`list(AGUI_FEATURES_BY_NAME.values())`. This is the canonical
"what features does this installation expose?" accessor.

### The `Installation` Runtime Model

`soliplex.models.Installation.from_config` converts each entry
from `InstallationConfig.agui_features` into a serializable
`models.AGUI_Feature` carrying `name`, `description`, `source`,
and `json_schema`. The result is exposed to clients through the
installation views, so a Soliplex client can introspect the full
set of features (and their JSON schemas) without reading the
server's YAML.

### Initial AG-UI State Synthesis

When a new AG-UI thread is started without a client-supplied
state, `soliplex.views.agui` builds a default state by iterating
over the room's `agui_feature_names` and, for each name,
instantiating `AGUI_FEATURES_BY_NAME[name].model_klass()` with no
arguments and dumping it to a dict. The TUI client
(`soliplex.tui.main`) does the same thing on its side when
opening a new room.

This means every model class registered in the registry must be
constructible with no arguments -- typically by giving every
field a default value.

### Schema Export

The `soliplex-cli agui-feature-schemas` command iterates the
registry (via `installation._config.agui_features`) and emits a
JSON document mapping each feature name to `{source, json_schema}`.
The `scripts/generate_feature_schemas.sh` helper uses this output
to regenerate `schemas/schema.json`, which downstream client
projects consume to generate type-safe client code.

### YAML Round-Trip

`InstallationConfigMeta.as_yaml` walks the registry to emit a
`meta.agui_features` block recording every registered feature
(including those that arrived via paths #1 and #2 above). This is
used by `soliplex-cli` export commands so that a fully expanded
configuration can be written back to disk.

## Notes for Test and Plugin Authors

- Because the registry is a module-level mutable global, unit tests
  must isolate themselves from each other. The standard fixture
  is `patched_agui_features` in `tests/unit/conftest.py`, which uses
  `mock.patch.dict` to give each test a fresh empty registry.

- A name listed in a room's `agui_feature_names` that is not present
  in the registry will raise `KeyError` when the server tries to
  synthesize an initial AG-UI state for a new thread. Run
  `soliplex-cli audit rooms <installation.yaml>` to detect this before
  deploying; each room's aggregate feature names are listed with
  `OK` or `UNREGISTERED`.

- Plugin authors who want to register a feature have two options:
  ship it as an entrypoint skill (path #2 above), or document a
  `meta.agui_features` entry that operators can paste into their
  installation YAML (path #3).
