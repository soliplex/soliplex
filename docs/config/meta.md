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

- `secret_sources` clears both the source configuration classes and their
  corresponding getter functions, since a source kind is registered as a
  pair.

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
a mapping with a single `config_klass` key, whose value is that same
dotted name.

Example:

```yaml
meta:
  tool_configs:
  - "my_package.config.MyToolConfig"
```

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
a mapping with a single `config_klass` key, whose value is that same
dotted name.

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

Soliplex registers no wrappers by default: this registry is empty unless
an installation populates it.

The class named by `config_klass` must already be registered as a tool
configuration, either by Soliplex itself or by the `meta.tool_configs`
section of this same installation configuration; `tool_configs` is
applied first for exactly that reason. Naming an unregistered class is an
error, and loading the configuration fails rather than silently skipping
the wrapper.

## Registering Skill Configuration Classes

The `meta.skill_configs` section enumerates skill
configuration types so that they can be referenced by their 'kind'.

The section contains a list of Python "dotted names", i.e. strings which
can be used to import the configuration class. Each entry may instead be
a mapping with a single `config_klass` key, whose value is that same
dotted name.

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
mapping with a single `config_klass` key, whose value is that same dotted
name.

Example:

```yaml
meta:
  agent_capability_types:
  - "my_package.capabilities.MyCapability"
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
a mapping with a single `config_klass` key, whose value is that same
dotted name.

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

The `meta.secret_sources` section allows configuring new secret source
configurations and their corresponding functions.

The section contains a list of mappings, each of which must include:

- `config_klass`, a Python "dotted name" which can be used to import the
  source configuration class. The kind it is registered under is taken
  from that class, not spelled separately.

- `registered_func`, a Python "dotted name" which can be used to import
  the callable which resolves a secret from an instance of
  `config_klass`. It is passed the source configuration instance and
  returns the secret value, raising a `soliplex.secrets.SecretError`
  subclass if it cannot.

Unlike the sections above, a bare dotted name is not accepted here: both
keys are required, because a source kind is only usable when its
configuration class and its getter are both registered.

By default, these classes are configured to use the corresponding
functions in `soliplex.secrets`, just as if we configured here:

```yaml
meta:
  secret_sources:
  - config_klass: "soliplex.config.secrets.EnvVarSecretSource"
    registered_func: "soliplex.secrets.get_env_var_secret"
  - config_klass: "soliplex.config.secrets.FilePathSecretSource"
    registered_func: "soliplex.secrets.get_file_path_secret"
  - config_klass: "soliplex.config.secrets.SubprocessSecretSource"
    registered_func: "soliplex.secrets.get_subprocess_secret"
  - config_klass: "soliplex.config.secrets.RandomCharsSecretSource"
    registered_func: "soliplex.secrets.get_random_chars_secret"
```

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
