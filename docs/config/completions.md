# Completion Configuration Filesystem Layout

A completion is configured via directory, whose name is the completion ID.

Within that directory should be one or two files:

- `completion_config.yaml` holds metadata about the completion (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the room.


Example layout without external prompt:
```yaml
simple/
    room_config.yaml

```

Example layout with external prompt:
```yaml
chat/
    prompt.txt
    room_config.yaml

```

# Completions Endpoint Configuration File Schema

## Required endpoint elements

The `completion_config.yaml`  file should be a mapping, with at least
the following required elements:

- `id` (a string) should match the name of the endpoint's directory.

- `agent` (a mapping)

A minimal completion endpoing configuration must include the above
elements, e.g.:

  ```yaml
  id: "chat"
  agent:
    system_prompt: |
        You are an..... #
  ```

Please see [this page](`agents.md`) which documents the `agent` element
schema.
