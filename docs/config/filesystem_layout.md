# Installation Filesystem Layout

An "installation" is a set of filesystem-based configuration files, organized
as a directory tree.

At the root of an installation directory is a file, `installation.yaml`, which
is used to configure environment variables and secrets used by the
installation.  There may be alternative configrations available, e.g. to
configure how the installation runs inside a container.

See [this page](installation.md) for
documentation on the schema of one of these configurations.

An installation directory typically containts subdirectories, each holding
configurations for a given type of entity.

Example layout:

```
/
  installation.yaml
  completions/
    chat-bot/
      completion_config.yaml
      prompt.txt
    ...
  oidc/
    cacert.pem
    config.yaml
  quizzes/
    quiz_name.json
    ...
  rooms/
    quiztest/
      prompt.txt
      room_config.yaml
    ...
```

### Room Configuration

Within a "rooms" directory, each room is represented by a subdirectory,
whose name is the room ID.

Within that subdirectory should be one or two files:

- `room_config.yaml` holds metadata about the room (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the room.

- A logo image file (optional)

See [this page](rooms.md) for documentation on the contents and
schema of these files.

### Completions Endpoint Configuration

Within a "completions" directory, each endpoint is represented by a
subdirectory, whose name is the endpoint ID.

Within that subdirectory should be one or two files:

- `completion_config.yaml` holds metadata about the endpoint (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the endpoint.

See [this page](completions.md) for documentation on the contents and
schema of these files.


### Quiz Configuration

This directory contains question sets as individual JSON files, derived
from the evaluation dataset entries.

See [this page](quizzes.md) for documentation on the contents
and schema of these files.

### OIDC Provider Configuration

This directory contains configuration files defining the OIDC identity
providers configured for use in this installation.

See [this page](oidc_providers.md) for documentation on the contents and
schema of these files.

