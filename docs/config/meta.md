# Installation Metaconfiguration

The `meta` section of an installation configuration enables registration of
custom "kinds" of entities (tool configurations, MCP client toolset
configurations, etc.), so that they can be used within the rest of the
installation.

E.g., registering a new tool configuration class in the `meta.tool_configs`
section allows use of that class when configuring a custom tool in a given
room.

Most subsections register into a global registry which Soliplex has
already populated with its own defaults at import time. Registration is
additive: a `meta` entry adds to those defaults, or replaces one of them
when it reuses the same key. To discard the defaults instead, see
[Clearing Default Registrations](#clearing-default-registrations) below.

## Clearing Default Registrations

Any subsection may include the string `"$$CLEAR$$"` as one of its
entries. The registry that subsection feeds is emptied before the
remaining entries in that same list are registered, so the installation
ends up with *only* what it configured explicitly.

This is useful for locking an installation down: a deployment which must
resolve every secret through a corporate vault, for example, can discard
the built-in secret sources rather than merely adding to them.

```yaml
meta:
  secret_sources:
  - "$$CLEAR$$"
  - "my_package.config.VaultSecretSource"
  secret_getters:
  - kind: "vault"
    func: "my_package.secrets.get_vault_secret"
```

The same lockdown can be written with the combined shorthand, which is
equivalent -- the kind is read from the class, so it need not be spelled:

```yaml
meta:
  secret_sources:
  - "$$CLEAR$$"
  - config_klass: "my_package.config.VaultSecretSource"
    registered_func: "my_package.secrets.get_vault_secret"
```

The marker clears only the registry (or registries) belonging to the
subsection that contains it, and each subsection is cleared
independently. Its position within the list does not matter, and
repeating it has no additional effect: the clear always happens first,
before any entry in that list is registered.

Two subsections clear more than one registry, because their registries
cannot meaningfully be separated:

- `tool_configs` also clears `mcp_server_tool_wrappers`, since a wrapper
  cannot outlive the tool configuration it wraps.

- `secret_sources` also clears `secret_getters`, since a getter cannot
  outlive the source class it resolves. Clearing the sources therefore
  suppresses the built-in kinds completely, leaving no orphaned getter
  behind; re-register a getter for every kind the installation keeps.

One subsection clears only part of its registry: `jsonpath_functions`
removes the functions supplied by configuration but keeps the RFC 9535
built-ins, which the shared JSONPath environment requires.

Subsections are applied in the order in which they are listed in this
document. That matters when one subsection validates against another:
see [Registering MCP Server Tool Wrapper
Types](#registering-mcp-server-tool-wrapper-types).

## Registering AG-UI Feature Classes

See [AG-UI Features](agui.md) for the full registry lifecycle; this
section covers only the YAML stanza.

The `meta.agui_features` section registers AG-UI feature types so that
they can be referenced by their `name`.  Each feature is a contract
between the client application and the server, defining the schema for
a named field in the AG-UI state, and which parties are expected to write
to that field.

The section contains a list of mappings, each of which include:

- `name`, a string identifying the field in the AG-UI state.

- `model_klass`, a Python "dotted name" which can be used to import the
   model class which defines the field's schema.

- `source` (optional), a  key indicating which party is allowed to set
  the feature's field in the AG-UI state. Allowed values are "client",
  "server", and "either";  the default is "either".

Example:

```yaml
meta:
  agui_features:

  - name: "my_feature"
    model_klass: "my_package.features.MyFeature"
    source: "server"
```

By default, importing Soliplex's skill configurations registers the
features used by the `haiku.rag` skills, just as though we configured
explicitly:

```yaml
meta:
  agui_features:
  - name: "rag"
    model_klass: "haiku.rag.capabilities.rag.RAGState"
    source: "server"
  - name: "analysis"
    model_klass: "haiku.rag.capabilities.analysis.AnalysisState"
    source: "server"
  - name: "citation_policy"
    model_klass: "haiku.rag.capabilities.policy.CitationPolicyState"
    source: "server"
```

## Registering Tool Configuration Classes

The `meta.tool_configs` section enumerates tool configuration types so that
they can be referenced by their `tool_name`.

The section contains a list of Python "dotted names", i.e. strings which
can be used to import the configuration class. Each entry may instead be
a mapping with a `config_klass` key, whose value is that same dotted name.

Example:

```yaml
meta:
  tool_configs:
  - "my_package.config.MyToolConfig"
```

The mapping form also accepts an optional `tool_name` key, naming the
registry key under which the class is registered. It defaults to the
`tool_name` declared by the class itself; supplying it explicitly
registers the class under an additional alias, which is how a renamed
tool keeps accepting its former name:

```yaml
meta:
  tool_configs:
  - "my_package.config.MyToolConfig"
  - tool_name: "my_package.tools.old_name"
    config_klass: "my_package.config.MyToolConfig"
```

`as_yaml` always emits the mapping form, so aliases survive a
dump-and-reload of the installation configuration.

By default, Soliplex registers its own tool config class, just as though
we configured explicitly:

```yaml
meta:
  tool_configs:
  - "soliplex.config.tools.SearchDocumentsToolConfig"
```

## Registering MCP Client Toolset Configuration Classes

The `meta.mcp_toolset_configs` section enumerates MCP client toolset
configuration types so that they can be referenced by their 'kind'.

The section contains a list of Python "dotted names", i.e. strings which
can be used to import the configuration class. Each entry may instead be
a mapping with a `config_klass` key, whose value is that same dotted
name, plus an optional `kind` key naming the registry key under which
the class is registered. `kind` defaults to the one declared by the
class itself; supplying it explicitly registers the class under an
additional alias, and `as_yaml` preserves it.

By default, Soliplex registers its own toolset config classes, just as
though we configured explicitly:

```yaml
meta:
  mcp_toolset_configs:
  - "soliplex.config.tools.Stdio_MCP_ClientToolsetConfig"
  - "soliplex.config.tools.HTTP_MCP_ClientToolsetConfig"
  - "soliplex.config.tools.SSE_MCP_ClientToolsetConfig"
```

## Registering MCP Server Tool Wrapper Types

The `meta.mcp_server_tool_wrappers` section maps tool configuration classes
to the equivalent wrapper class, used when offering the tool to external
MCP clients.

Soliplex registers no tool config wrappers by default: this registry is empty
unless an installation populates it.

The section contains a list of mappings with keys `config_klass` and
`wrapper_klass`.  Values for both keys are Python "dotted names", i.e.
strings which can be used to import the corresponding class.

Example:

```yaml
meta:
  mcp_server_tool_wrappers:
  - config_klass: "my_package.config.MyToolConfig"
    wrapper_klass: "my_package.config.MyMCPWrapper"
```

Each mapping also accepts an optional `tool_name` key, naming the
tool config registry key for which the wrapper is registered. It defaults
to the `tool_name` declared by `config_klass`. Supplying a different
`tool_name` wraps the tool config registered under that alias, and
`as_yaml` preserves it. Because wrappers are keyed by tool name rather
than by class, a tool registered under both its own name and an alias
requires a separate wrapper entry for each registered tool name.

That `tool_name` must already be registered as a tool configuration,
either by Soliplex itself or by the `meta.tool_configs` section of this
same installation configuration; `tool_configs` is applied first for
exactly that reason. Naming an unregistered `tool_name` is an error, and
loading the configuration fails rather than silently skipping the
wrapper. Note that it is the name which must be registered, not the
class: naming a registered class under a `tool_name` which is not itself
registered fails just the same.

## Registering Skill Configuration Classes

The `meta.skill_configs` section enumerates skill
configuration types so that they can be referenced by their 'kind'.

The section contains a list of Python "dotted names", i.e. strings which
can be used to import the configuration class. Each entry may instead be
a mapping with a `config_klass` key, whose value is that same dotted
name, plus an optional `kind` key naming the registry key under which
the class is registered. `kind` defaults to the one declared by the
class itself; supplying it explicitly registers the class under an
additional alias, and `as_yaml` preserves it. A skill whose `kind` has
been renamed can therefore keep accepting its former spelling in room
configurations:

```yaml
meta:
  skill_configs:
  - "my_package.config.MySkillConfig"
  - kind: "my_package.old_skill_name"
    config_klass: "my_package.config.MySkillConfig"
```

By default, Soliplex registers its own skill config classes, just as
though we configured explicitly:

```yaml
meta:
  skill_configs:
  - "soliplex.config.skills.HR_RAG_SkillConfig"
  - "soliplex.config.skills.HR_Analysis_SkillConfig"
  - "soliplex.config.skills.HR_EvidenceCompaction_SkillConfig"
  - "soliplex.config.skills.HR_CitationPolicy_SkillConfig"
  - "soliplex.config.skills.BwrapSandboxSkillConfig"
  - "soliplex.config.skills.EntrypointCapabilityConfig"
```

## Registering Agent Capability Types

The `meta.agent_capability_types` section enumerates agent capability
types so that they can be referenced by name in a room's agent
configuration. The name a capability is registered under is its Python
class name, not a separate `kind` string.

The section contains a list of Python "dotted names", i.e. strings which
can be used to import the capability class. Each entry may instead be a
mapping with a `config_klass` key, whose value is that same dotted name,
plus an optional `capability_name` key naming the registry key under
which the class is registered. `capability_name` defaults to the class'
own `__name__`; supplying it explicitly registers the class under an
additional alias, and `as_yaml` preserves it. A capability class which
has been renamed can therefore keep answering to its former class name:

```yaml
meta:
  agent_capability_types:
  - "my_package.capabilities.MyCapability"
  - capability_name: "MyOldCapability"
    config_klass: "my_package.capabilities.MyCapability"
```

By default, Soliplex registers the capability types published by
`pydantic_ai.capabilities` — `NativeTool`, `Thinking`, `WebSearch` and
the rest — so the set available without configuration follows the
installed `pydantic-ai` version.

## Registering Agent Configuration Classes

The `meta.agent_configs` section enumerates agent configuration types so that
they can be referenced by their `kind`.

The section contains a list of Python "dotted names", i.e. strings which
can be used to import the configuration class. Each entry may instead be
a mapping with a `config_klass` key, whose value is that same dotted
name, plus an optional `kind` key naming the registry key under which
the class is registered. `kind` defaults to the one declared by the
class itself; supplying it explicitly registers the class under an
additional alias, and `as_yaml` preserves it. An agent whose `kind` has
been renamed can therefore keep accepting its former spelling in room
configurations:

```yaml
meta:
  agent_configs:
  - "my_package.config.MyAgentConfig"
  - kind: "my_package.old_agent_kind"
    config_klass: "my_package.config.MyAgentConfig"
```

By default, Soliplex registers its own agent config classes, just as
though we configured explicitly:

```yaml
meta:
  agent_configs:
  - "soliplex.config.agents.AgentConfig"
  - "soliplex.config.agents.FactoryAgentConfig"
```

## Registering Secret Source Configurations

Each [installation secret](installation.md#secrets) can be
configured with multiple "sources" of different kinds. Each source
configuration kind corresponds to a Python function which is used to
retrieve the secret value.

The `meta.secret_sources` section registers the source configuration
classes, so that they can be referenced by their `kind`. The functions
which resolve those sources are registered separately, in
[`meta.secret_getters`](#registering-secret-getter-functions) below.

Like most sections above, it contains a list of Python "dotted names".
Each entry may instead be a mapping with a `config_klass` key, whose
value is that same dotted name, plus an optional `kind` key naming the
registry key under which the class is registered. `kind` defaults to the
one declared by the class itself; supplying it explicitly registers the
class under an additional alias, and `as_yaml` preserves it.

By default, Soliplex registers its own source classes, just as though we
configured explicitly:

```yaml
meta:
  secret_sources:
  - "soliplex.config.secrets.EnvVarSecretSource"
  - "soliplex.config.secrets.FilePathSecretSource"
  - "soliplex.config.secrets.SubprocessSecretSource"
  - "soliplex.config.secrets.RandomCharsSecretSource"
```

## Registering Secret Getter Functions

A source configuration class describes *where* a secret lives; a getter
function is what actually fetches it. The `meta.secret_getters` section
registers those functions, one per source kind.

The section contains a list of mappings, each of which must include:

- `kind`, the secret source kind the function resolves. Its source
  configuration class must already be registered -- a getter for an
  unregistered kind is an error, not a no-op.

- `func`, a Python "dotted name" which can be used to import the
  callable. It is passed the source configuration instance and returns
  the secret value, raising a `soliplex.secrets.SecretError` subclass if
  it cannot.

By default, Soliplex registers the corresponding functions from
`soliplex.secrets`, just as though we configured explicitly:

```yaml
meta:
  secret_getters:
  - kind: "env_var"
    func: "soliplex.secrets.get_env_var_secret"
  - kind: "file_path"
    func: "soliplex.secrets.get_file_path_secret"
  - kind: "subprocess"
    func: "soliplex.secrets.get_subprocess_secret"
  - kind: "random_chars"
    func: "soliplex.secrets.get_random_chars_secret"
```

Because `secret_sources` is applied first (see [Clearing Default
Registrations](#clearing-default-registrations) on ordering), a getter
naming a kind with no registered source class raises
`GetterForUnknownSecretSource` when the configuration is loaded.

### The combined shorthand

A new source kind almost always ships its class and its getter together,
so a `secret_sources` entry may carry `registered_func` alongside
`config_klass` as shorthand for both registrations:

```yaml
meta:
  secret_sources:
  - config_klass: "my_package.config.VaultSecretSource"
    registered_func: "my_package.secrets.get_vault_secret"
```

That is exactly equivalent to writing the two sections out, reading the
`kind` from `config_klass` -- or from the entry's own `kind` key, when
it carries one, so that an aliased source and its getter land under the
same kind. The shorthand is expanded while the `meta` section is parsed,
so an explicit `secret_getters` entry for the same kind takes precedence
over one implied by `registered_func`. Note that
`registered_func` is only meaningful in this combined position: it is not
accepted anywhere else, and `soliplex-cli config` always dumps the two
sections separately.

### Registering a source without its getter

The two registries are independent, so it is possible to register a
source class and never register a getter for its kind. Nothing fails at
load time -- the configuration parses, and a `sources:` entry of that
kind is accepted -- but resolving a secret from it raises
`soliplex.secrets.NoGetterForSecretSourceKind`. That counts as one failed
source, so a secret listing further sources still resolves from the next
one, and `soliplex-cli audit` reports the miss in its secrets section.

Three configurations reach that state:

- registering a source class alone, with no matching getter;

- registering a source class under an additional `kind` alias without a
  getter for that alias: getters are keyed by kind, so the getter
  registered for the class' own kind does not cover the alias;

- clearing `secret_getters` without clearing `secret_sources`, which
  strands every built-in kind whose getter is not re-registered:

  ```yaml
  meta:
    secret_getters:
    - "$$CLEAR$$"
    - kind: "env_var"
      func: "soliplex.secrets.get_env_var_secret"
  ```

  Here `file_path`, `subprocess` and `random_chars` remain registered as
  sources but can no longer be resolved. To suppress kinds entirely,
  clear `secret_sources` instead: the clear cascades to the getters.

## Registering JSONPath Filter Functions

Room authorization ACL entries can match a user's token using an
[RFC 9535](https://www.rfc-editor.org/rfc/rfc9535) JSONPath query (the
`json_path` predicate). Queries are evaluated against a single, shared
JSONPath environment (`soliplex.authz.the_jsonpath_environment`).

The `meta.jsonpath_functions` section registers named filter functions
into that environment, making them callable as `name(...)` inside a
filter expression. This lets a deployment express authorization rules
that the RFC 9535 built-ins cannot.

The section contains a list of mappings, each of which include:

- `name`, the identifier by which the function is invoked inside a
  JSONPath filter expression.

- `func`, a Python "dotted name" which can be used to import a callable
  implementing the function. The callable must conform to
  [python-jsonpath](https://jg-rp.github.io/python-jsonpath/)'s
  filter-function protocol (a callable, optionally carrying `arg_types`
  and `return_type` for RFC 9535 well-typedness checks).

A `name` that collides with one of the RFC 9535 built-ins (e.g. `match`,
`search`, `length`, `count`, `value`) is rejected.

Example:

```yaml
meta:
  jsonpath_functions:
  - name: "is_admin"
    func: "my_package.jsonpath.is_admin"
```

Given the registration above, a room ACL entry could allow access with a
predicate such as `$[?is_admin($.roles)]`.
