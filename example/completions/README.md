# Disk-based Completions Endpoint Configuration

This directory tree is the location for on-disk completions endpoint
configuration.

## Completions Endpoint Configuration Filesystem Layout

Within this directory, each endpoint is represented by a subdirectory, whose
name is the endpoint ID.

Within that subdirectory should be one or two files:

- `completion_config.yaml` holds metadata about the endpoint (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the endpoint.


Example layout:

```
completions/
    chat/
        prompt.txt
        completion_config.yaml
    simple/
        completion_config.yaml
```

## Completions Endpoint Configuration File Schema

### Required endpoint elements

The `completion_config.yaml`  file should be a mapping, with at least
the following required elements:

- `id` (a string) should match the name of the endpoint's directory.

- `agent` (a mapping, see next section)

A minimal completion endpoing configuration must include the above
elements, e.g.:

  ```yaml
  id: "chat"
  agent:
    system_prompt: |
        You are an..... #
  ```

For agent configuration options, please see `rooms/README.md`, which uses the
same schema.  Likewise, RAG database files are expected to be found in
the same location: a given room and completion endpoint might be sharing one!
