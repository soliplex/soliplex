# Completion Configuration Filesystem Layout

A completion is configured via a directory, whose name is the completion ID.

**NOTE:** directories whose names start with '.' are ignored.

Within that directory should be one or two files:

- `completion_config.yaml` holds metadata about the completion (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the completion.

Example layout without external prompt:

```yaml
simple/
    completion_config.yaml

```

Example layout with external prompt:

```yaml
chat/
    prompt.txt
    completion_config.yaml

```

## Completions Configuration File Schema

### Required completion elements

The `completion_config.yaml`  file should be a mapping, with at least
the following required elements:

- `id` (a string) should match the name of the completion's directory.

- `agent` (a mapping)

A minimal completion  configuration must include the above
elements, e.g.:

  ```yaml
  id: "chat"
  agent:
    system_prompt: |
        You are an..... #
  ```

Please see [this page](agents.md) which documents the `agent` element
schema.

### Optional completion elements

- `name` (a string, defaults to the value of `id`) is a display name for
  the completion, surfaced via the completions API.

### Tool Configurations

- `tools` should be a list of mappings, with at least the key
  `tool_name`, whose value is a dotted name identifying a Python function
   (or callable) which can serve as a "tool" for the LLM.  E.g.:

   ```yaml
   tools:
       - tool_name: "soliplex.tools.get_current_datetime"
       - tool_name: "soliplex.tools.get_current_user"
   ```

  Each tool mapping can contain additional elements, which are used to
  configure the tool's behavior.

### MCP Client Toolsets

- `mcp_client_toolsets` should be a mapping of toolset name to a toolset
  configuration.  Each configuration selects a transport via its `kind`:

  - `"stdio"` runs an MCP server as a subprocess, configured with
    `command`, `args`, and `env`.

  - `"http"` or `"sse"` connect to a remote MCP server, configured with
    `url`, `headers`, and `query_params`.

  Any configuration may also set `allowed_tools` (a list of strings) to
  restrict which of the server's tools are exposed.  E.g.:

  ```yaml
  mcp_client_toolsets:
    google_maps:
      kind: "stdio"
      command: "npx"
      args:
        - "-y"
        - "@modelcontextprotocol/server-google-maps"
      env:
        GOOGLE_MAPS_API_KEY: "secret:GOOGLE_MAPS_API_KEY"
  ```

  String values in these fields can interpolate installation secrets and
  environment variables; see [Installation Secret / Environment
  Interpolation](installation.md#installation-secret-environment-interpolation).
