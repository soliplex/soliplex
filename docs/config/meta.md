# Installation Metaconfiguration

The `meta` section of an installation configuration enables registration of
custom "kinds" of entities (tool configurations, MCP client toolset
configurations, etc.), so that they can be used within the rest of the
installation.

E.g., registering a new tool configuration class in the `meta.tool_configs`
section allows use of that class when configuring a custom tool in a given
room.

## Registering Tool Configuration Classes

The `meta.tool_configs` section enumerates tool configuration types so that
they can be referenced by their `tool_name`.

The section contains a list of Python "dotted names", i.e. strings which
can be used to import the configuration class.

By default, Soliplex registers its own tool config classes, just as though
we configured explicitly:

```yaml
meta:
  tool_configs:
  - "soliplex.config.SearchDocumentsToolConfig"
```

## Registering MCP Client Toolset Configuration Classes
The `meta.mcp_toolset_configs` section enumerates MCP client toolset
configuration types so that they can be referenced by their 'kind'.

The section contains a list of Python "dotted names", i.e. strings which
can be used to import the configuration class.

By default, Soliplex registers its own tool config classes, just as though
we configured explicitly:
 
```yaml
meta:
  mcp_toolset_configs:
  - "soliplex.config.Stdio_MCP_ClientToolsetConfig"
  - "soliplex.config.HTTP_MCP_ClientToolsetConfig"
```
## Registering MCP Server Tool Wrapper Types

The `meta.mcp_server_tool_wrappers` section maps tool configuration classs to
the equivalent wrapper class, used then offering the tool to external
MCP clients.

The section contains a list of mappings with keys `config_klass` and
`wrapper_klass`.  Values for both keys Python "dotted names", i.e. strings
which can be used to import the corresponding class.

By default, Soliplex configures its 'soliplex.config.WithQueryMCPWrapper'
as the wrapper for 'soliplex.config.SearchDocumentsToolConfig',
just as if we configured here:

```yaml
meta:
  mcp_server_tool_wrappers:
  - config_klass: "soliplex.config.SearchDocumentsToolConfig"
    wrapper_klass: "soliplex.config.WithQueryMCPWrapper"
```

## Registering Secret Source Configurations

Each [installation secret](installation.md#secrets) can be
configured with multiple "sources" of different kinds. Each source
configuration kind corresponds to a Python function which is used to
retrieve the secret value.

The `meta.secret_sources` section allows configuring new secret source
configurations and their corresponding functions.

By default, these classes are configured to use the corresponding
functions in 'soliplex.secrets', just as if we configured here:

```yaml
meta:
  secret_sources:
  - config_klass: "soliplex.config.EnvVarSecretSource"
    registered_func: "soliplex.secrets.get_env_var_secret"
  - config_klass: "soliplex.config.FilePathSecretSource"
    registered_func: "soliplex.secrets.get_file_path_secret"
  - config_klass: "soliplex.config.SubprocessSecretSource"
    registered_func: "soliplex.secrets.get_subprocess_secret"
  - config_klass: "soliplex.config.RandomCharsSecretSource"
    registered_func: "soliplex.secrets.get_random_chars_secret"
```
