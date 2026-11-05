# Installation Filesystem Layout

An "installation" is a set of filesystem-based configuration files, organized
as a directory tree.

At the root of an installation directory is a file, `installation.yaml`, which
configures the installation as a whole:  its environment variables and
secrets, its databases, and where to find the other configuration files
described below.  There may be alternative configurations available, e.g. to
configure how the installation runs inside a container.

See [this page](installation.md) for
documentation on the schema of one of these configurations.

An installation directory typically contains subdirectories, each holding
configurations for a given type of entity.

Example layout:

```text
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

## Databases

Soliplex keeps AG-UI thread history and authorization data in two
databases, configured by the `thread_persistence_db` and
`authorization_db` stanzas of `installation.yaml`.  By default both are
in-memory SQLite databases, so nothing is written to the installation
directory.

The example configurations instead use SQLite files under `db/sqlite/`,
e.g. `sqlite:///db/sqlite/thread_persistence.sqlite`.  A relative path
like this is resolved against the server's working directory, not the
installation directory, and its parent directory must already exist.

See [SQLAlchemy DBURIs](dburis.md) for the full reference, including
PostgreSQL and database migrations.

## Room Configuration

Within a "rooms" directory, each room is represented by a subdirectory,
whose name is the room ID.

Within that subdirectory should be one or two files:

- `room_config.yaml` holds metadata about the room (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the room.

- A logo image file (optional)

See [this page](rooms.md) for documentation on the contents and
schema of these files.

## Completions Endpoint Configuration

Within a "completions" directory, each endpoint is represented by a
subdirectory, whose name is the endpoint ID.

Within that subdirectory should be one or two files:

- `completion_config.yaml` holds metadata about the endpoint (see below)

- `prompt.txt` (if present) holds the system prompt for conversations
  which are initiated from the endpoint.

See [this page](completions.md) for documentation on the contents and
schema of these files.

## Quiz Configuration

This directory contains question sets as individual JSON files, derived
from the evaluation dataset entries.

See [this page](quizzes.md) for documentation on the contents
and schema of these files.

## OIDC Provider Configuration

This directory contains configuration files defining the OIDC identity
providers configured for use in this installation.

See [this page](oidc_providers.md) for documentation on the contents and
schema of these files.
