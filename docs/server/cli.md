# `soliplex-cli` Command Reference

## Global Options

These apply to all `soliplex-cli` subcommands:

- `-v` / `--version` — show installed version (plus git tag / branch / hash
  when run from a source checkout) and exit.
- `-h` / `--help` — show help and exit.

## A Note on Renamed Commands

Several subcommands were renamed and regrouped after the `0.62.x` release.
The previous flat names (`check-config`, `list-secrets`, `pull-models`,
etc.) are preserved as hidden aliases so existing scripts continue to
work, but new scripts should use the grouped form documented below.
See [Deprecated Command Names](#deprecated-command-names) at the bottom
of this page for the full mapping.

## `serve` Command

Run the Soliplex FastAPI backend under uvicorn.

```bash
soliplex-cli serve [OPTIONS] [INSTALLATION_CONFIG_PATH]
```

### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

### Network Options

- `-H HOST` / `--host HOST` — bind to this host (default: `127.0.0.1`).
  Use `0.0.0.0` to accept connections on any interface.
- `-p PORT` / `--port PORT` — listen on this port (default: `8000`).
- `--uds PATH` — bind to a Unix domain socket instead of a TCP address.
- `--fd INTEGER` — bind to an already-open socket from this file descriptor
  (useful for socket-activated deployments).

### Authentication Options

- `--no-auth-mode` — disable OIDC authentication providers
  (development/testing only). **Never use in production.**
- `--add-admin-user USERNAME` — **removed.** Passing it now fails with a
  non-zero exit and a pointer to seed admins out of band with
  [`admin-users add`](#admin-users-add). The option is retained only so
  that scripts still passing it get a clear error rather than an
  "unknown option" failure.

### Hot Reload Options

- `-r {python,config,both}` / `--reload {python,config,both}` — enable
  uvicorn's reloader, watching Python sources, YAML config, or both.
  Not valid together with `--workers`.

  When `--reload python` or `--reload both` is set, the `soliplex`
  package directories are added to the watch list automatically.

  When `--reload config` or `--reload both` is set, the installation
  file's directory is added to the watch list automatically, and
  `*.yaml`, `*.yml`, `*.txt` are added to the include patterns.

- `--reload-dirs DIR` — additional directory to watch (repeatable).
- `--reload-includes PATTERN` — additional file glob to include in the
  watch (repeatable).

### Process Options

- `--workers INTEGER` — number of uvicorn worker processes. Defaults to
  `$WEB_CONCURRENCY` if set, otherwise `1`. Not valid with `--reload`.

### Logging Options

- `--log-config PATH` — logging configuration file; `.ini`, `.json`, and
  `.yaml` are supported. Overrides any `logging_config_file` configured
  in the installation YAML.
- `--log-level {critical,error,warning,info,debug,trace}` — uvicorn log
  level.
- `--access-log` / `--no-access-log` — enable or disable the uvicorn
  access log. Unset by default (uvicorn's own default applies).

### Proxy Options

- `--proxy-headers` — honor `X-Forwarded-Proto` / `X-Forwarded-For` from
  upstream proxies (nginx, traefik, etc.).
- `--forwarded-allow-ips IPS` — comma-separated list of IPs, CIDR
  networks, or socket paths to trust for `X-Forwarded-*` headers. The
  literal `*` trusts everything. Unset by default; if unset, reads
  `$FORWARDED_ALLOW_IPS`; if that is also unset, uvicorn's fallback of
  `127.0.0.1` applies.

### Examples

Development with hot reload and authentication disabled:

```bash
soliplex-cli serve example/installation.yaml \
  --reload both \
  --no-auth-mode
```

Behind a reverse proxy:

```bash
soliplex-cli serve example/installation.yaml \
  --host 127.0.0.1 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips "127.0.0.1"
```

Production with multiple workers:

```bash
soliplex-cli serve example/installation.yaml \
  --host 0.0.0.0 \
  --workers 4
```

Bootstrap the first admin user on a fresh authz database (seed out of
band, then start the server):

```bash
soliplex-cli admin-users add example/installation.yaml alice@example.com
soliplex-cli serve example/installation.yaml
```

## `audit`

The `audit` group bundles read-only validation and listing commands —
each one inspects some aspect of an installation configuration without
mutating state. Run `soliplex-cli audit --help` for the full list.

This group replaces the deprecated flat `check-config` / `list-*`
commands; see [Deprecated Command Names](#deprecated-command-names).

**Tolerant of missing environment variables.** All `audit` subcommands
load the installation in an audit-only mode that swallows
`MissingEnvVars` during initial config resolution, so unresolved
entries never abort the listing. Use `audit all` (or `audit
environment`) to validate the environment separately.

### Group Options

These options apply to every `audit` subcommand and must be placed
**before** the subcommand name (i.e., `soliplex-cli audit -q secrets
example/minimal.yaml`, *not* `soliplex-cli audit secrets
example/minimal.yaml -q`). They also work with the
[shorthand](#default-subcommand): `soliplex-cli audit -q
example/minimal.yaml`.

- `-q` / `--quiet` — suppress per-subcommand human-focused output (the
  section headers and per-item listings). When combined with a failing
  run, the errors are emitted as a single JSON document on stdout
  (suitable for piping into `jq` or a CI log parser); each subcommand
  documents its own JSON shape under "Exit Status".

### Default Subcommand

If the first positional argument to `soliplex-cli audit` does not name
one of its subcommands (`all`, `installation`, `secrets`, `environment`,
`oidc`, `rooms`, `completions`, `quizzes`, `skills`, `logging`,
`logfire`), it is treated as the `INSTALLATION_CONFIG_PATH` argument to
`audit all`. If no positional argument is given at all (e.g. plain
`soliplex-cli audit`, or `soliplex-cli audit -q`), `audit all` is still
invoked and resolves `INSTALLATION_CONFIG_PATH` from the
`SOLIPLEX_INSTALLATION_PATH` environment variable. The following four
invocations are equivalent (the latter two require the env var to be
set):

```bash
soliplex-cli audit example/minimal.yaml          # preferred
soliplex-cli audit all example/minimal.yaml
SOLIPLEX_INSTALLATION_PATH=example/minimal.yaml \
    soliplex-cli audit
SOLIPLEX_INSTALLATION_PATH=example/minimal.yaml \
    soliplex-cli audit all
```

The shorthand is the **preferred spelling** for invoking `audit all`
in every case — with an explicit path or with the env-var fallback.
Group help (`soliplex-cli audit --help`) is still reachable via the
explicit `--help` flag.

### `audit all`

Validate an installation configuration: resolve secrets and environment
variables, instantiate the runtime models, and check the referenced
resources (RAG databases, quiz files, skills, Python logging config).
Intended to be run before `serve` (or in CI) to catch missing secrets,
typos, and broken references up front. (Replaces the deprecated
`soliplex-cli check-config`.)

```bash
# preferred:
soliplex-cli audit [OPTIONS] INSTALLATION_CONFIG_PATH
# canonical (equivalent) form:
soliplex-cli audit [OPTIONS] all [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`, and
[Default Subcommand](#default-subcommand) for the rules that make the
first form a shortcut for the second.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### What Gets Checked

The command runs the following validation passes in order. Each pass
prints the same body it would print under its focused subcommand
(`audit secrets`, `audit environment`, etc.) — see those sections
below for output details and JSON-error shapes.

1. **Installation model** — the top-level installation config converts
   cleanly to its runtime model.
2. **Secrets** — every declared secret is listed with an `OK` or
   `MISSING` flag.
3. **Environment** — every declared environment variable is listed
   with its resolved value (or `MISSING`).
4. **OIDC authentication systems** — every configured OIDC provider
   is listed with its title and server URL; an `ERROR:` line is
   appended on runtime-model failure.
5. **Rooms** — every room is listed with its description, plus a
   per-RAG-source row for each agent / named-skill / named-tool that
   has a RAG database. Each LanceDB is opened and a live document
   count is issued (so this pass requires read access to the RAG
   files and may be slow against many large databases).
6. **Completions** — every completion endpoint is listed with its
   name; runtime-model failures are flagged with `ERROR:`.
7. **Quizzes** — every `*.json` question file under each configured
   quizzes path loads and parses.
8. **Skills** — every configured `skill_config` is checked for
   load-time validation errors, and every skill found under each
   configured filesystem skills path is run through the full
   `skills_ref` validator.
9. **Python logging** — if a `logging_config_file` is configured, it
   parses as YAML and the logging headers / claims maps are printed.
10. **Logfire** — the Logfire config (if any) is printed for review.
11. **Ollama** — for each Ollama server URL referenced by the
    installation, the available-models list is fetched and compared
    against the models the installation requires. Unreachable servers
    and missing models are flagged. (See [`audit ollama`](#audit-ollama)
    for the full output and JSON shape.)

#### Exit Status

- `0` — all sections validated successfully.
- `1` — at least one section reported an error. In `--quiet` mode, the
  combined error report is printed as JSON on stdout before exit.

#### Examples

Validate the minimal example:

```bash
soliplex-cli audit example/minimal.yaml
```

Validate a directory-style installation (uses `example/installation.yaml`
within the directory):

```bash
soliplex-cli audit example/
```

CI-style invocation — only print output on failure, and capture the
error JSON:

```bash
soliplex-cli audit --quiet example/installation.yaml \
  > audit-errors.json || cat audit-errors.json
```

Use the env-var form instead of a positional argument (the shorthand
also works here — with no positional argument, `audit` dispatches to
`audit all`, which then reads the path from the env var):

```bash
export SOLIPLEX_INSTALLATION_PATH=example/minimal.yaml
soliplex-cli audit
```

### `audit installation`

Validate that the top-level installation config converts cleanly to its
runtime model. This is the same check `audit all` runs first, exposed
as a focused subcommand for callers that want a quick model-only smoke
test without re-resolving secrets, opening RAG databases, or walking
skill paths.

```bash
soliplex-cli audit [OPTIONS] installation [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

A single status line under a "Configured installation model" header:

```text
OK
```

If `models.Installation.from_config(...)` raises, the `OK` is replaced
by `ERROR: <message>`.

#### Exit Status

- `0` — the installation config rendered as a model.
- `1` — model construction raised. In `--quiet` mode, the error is
  printed as JSON (under the key `installation_model`) on stdout before
  exit.

#### Examples

Quick model-validity check on the minimal example:

```bash
soliplex-cli audit installation example/minimal.yaml
```

Audit a directory-style installation:

```bash
soliplex-cli audit installation example/
```

### `audit secrets`

List the secrets declared in the installation configuration and report
whether each one resolves. Useful for auditing a configuration — e.g.,
confirming that every secret listed in the YAML has at least one working
source — without exposing the values themselves. (Replaces the
deprecated `soliplex-cli list-secrets`.)

```bash
soliplex-cli audit [OPTIONS] secrets [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

For each secret declared in the installation, one line is printed in the
form:

```text
- <secret_name>               OK
- <secret_name>               MISSING
```

`OK` means the secret resolved via at least one of its configured
sources; `MISSING` means no source produced a value.

#### Exit Status

- `0` — every declared secret resolved.
- `1` — at least one declared secret is missing. In `--quiet` mode, the
  list of missing secrets is printed as JSON on stdout before exit.

#### Security Notes

Resolved secret values are never printed — only the secret name and a
status flag. The command is safe to run in shared terminals or to pipe
into logs.

#### Examples

List secrets for the minimal example:

```bash
soliplex-cli audit secrets example/minimal.yaml
```

Audit a directory-style installation:

```bash
soliplex-cli audit secrets example/
```

Quick visual check for anything missing:

```bash
soliplex-cli audit secrets example/installation.yaml | grep MISSING
```

### `audit environment`

List the environment variables declared in the installation configuration
along with their resolved values. Useful for confirming that the values
Soliplex will see at runtime match your expectations, and — with
`--verbose` — for diagnosing *why* a particular value was chosen when
multiple sources are configured. (Replaces the deprecated
`soliplex-cli list-environment`.)

```bash
soliplex-cli audit [OPTIONS] environment [-v] [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Options

- `-v` / `--verbose` — after each variable, also list every configured
  source and its candidate value. The selected source is flagged with a
  leading `*`; others are flagged with a space. Suppressed by the
  group-level `-q` / `--quiet`.

#### Output

For each environment variable declared in the installation, one line is
printed in the form:

```text
- <env_var_name>              : <resolved_value>
```

If a variable cannot be resolved from any of its configured sources, its
value is shown as `MISSING`.

With `--verbose`, each variable is followed by its source list:

```text
- SOLIPLEX_EXAMPLE            : http://localhost:11434
  *<source_type>              : http://localhost:11434
   <source_type>              : <other_candidate>
```

The `*` marks the source whose value was selected; each remaining line
shows a fallback source that was not used.

#### Exit Status

- `0` — every declared environment variable resolved.
- `1` — at least one declared environment variable is missing. In
  `--quiet` mode, the list of missing variables is printed as JSON on
  stdout before exit.

#### Security Notes

Unlike `audit secrets`, this command **does** print resolved values.
Environment variables in Soliplex are intended for non-secret
configuration — anything sensitive should be declared as a secret and
audited with `audit secrets` instead. Avoid piping `audit environment`
output into shared logs if any of your environment entries happen to
contain sensitive values.

#### Examples

List environment variables for the minimal example:

```bash
soliplex-cli audit environment example/minimal.yaml
```

Show source details to diagnose which value will win:

```bash
soliplex-cli audit environment example/installation.yaml --verbose
```

Audit a directory-style installation:

```bash
soliplex-cli audit environment example/
```

Quick visual check for anything missing:

```bash
soliplex-cli audit environment example/installation.yaml | grep MISSING
```

### `audit oidc`

List the OIDC authentication providers declared in the installation
configuration, and validate that each one converts cleanly to its
runtime model. Useful for confirming which providers will be offered on
the login screen and what server URLs Soliplex will contact for token
validation. (Replaces the deprecated
`soliplex-cli list-oidc-auth-providers`.)

```bash
soliplex-cli audit [OPTIONS] oidc [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

For each OIDC provider declared in the installation, a two-line entry
is printed:

```text
- [ <provider_id> ] <title>:
  <server_url>
```

`<provider_id>` is the key Soliplex uses internally to refer to the
provider; `<title>` is the human-readable label surfaced to clients; and
`<server_url>` is the OIDC issuer / discovery base URL. If the provider
fails runtime-model validation, an `ERROR: <message>` line is appended
to its entry.

#### Behavior Notes

- **Validation is offline.** The command does not contact the OIDC
  server itself; it only checks that the YAML-declared configuration
  converts cleanly to the runtime model.

#### Exit Status

- `0` — every declared OIDC provider validated.
- `1` — at least one provider failed runtime-model validation. In
  `--quiet` mode, the per-provider errors are printed as JSON on stdout
  before exit.

#### Examples

List OIDC providers for the full installation example:

```bash
soliplex-cli audit oidc example/installation.yaml
```

Audit a directory-style installation:

```bash
soliplex-cli audit oidc example/
```

### `audit rooms`

List the rooms declared in the installation configuration, along with
their names, descriptions, the AG-UI feature names each room aggregates
(checked against the
[AG-UI feature registry](../config/agui.md)), and any RAG databases
they reference (including a live document count for each). (Replaces
the deprecated `soliplex-cli list-rooms`.)

```bash
soliplex-cli audit [OPTIONS] rooms [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

For each room declared in the installation, an entry is printed of the
form:

```text
- [ <room_id> ] <name>:
  <description>

   AG-UI features
   - <feature_name>                : OK

   Haiku Rag DBs
   - <source>              : <db_path>                     <N> documents
```

`<source>` identifies where the RAG database reference came from within
the room — `agent`, `skill:<name>`, or `tool:<name>`. `<db_path>` is
shown relative to the current working directory.

If `Room.from_config(...)` fails for a room (i.e. the room cannot be
converted to its runtime model), an extra line is printed beneath the
room header before the "AG-UI features" block:

```text
  ERROR: <message>
```

Rooms with no AG-UI features in their aggregate set
([agent](../config/agents.md) ∪ room ∪ tools ∪ skills) omit the
"AG-UI features" block. Within the block, each feature name is checked
against the [AG-UI feature registry](../config/agui.md) and flagged
either `OK` or `UNREGISTERED`. An `UNREGISTERED` flag means a name in
the room's aggregate set has no corresponding registration; the server
will raise `KeyError` when synthesizing initial AG-UI state for a new
thread in that room.

Rooms with no RAG configuration omit the "Haiku Rag DBs" block.
Within the block, each RAG-bearing sub-config (the agent, a named
skill, or a named tool) gets its own row — successes and failures are
intermixed. If a configured RAG database file cannot be located, that
row is replaced by `- <source>: ERROR: <message>`. If the database
is present but the `count_documents` query fails, the count column is
shown as `error` rather than a number.

#### Behavior Notes

- **Bypasses authorization.** This command deliberately lists every room
  configured in the installation, regardless of which rooms any given
  user would be authorized to see via the normal `get_room_configs`
  path. It reflects configuration, not per-user visibility.
- **Opens each RAG database.** The document count is obtained by
  opening the LanceDB at each configured `db_path` and issuing a
  `count_documents` query. Expect the command to be slower than the
  other `audit` subcommands when many rooms have large RAG databases,
  and to require read access to those files.
- **Paths are `cwd`-relative.** The `<db_path>` column depends on where
  you run the command from; two invocations from different directories
  may show different-looking (but equivalent) paths.

#### Exit Status

- `0` — every room's runtime model converted, every aggregated AG-UI
  feature name resolved against the registry, every RAG configuration
  resolved, and every document count completed.
- `1` — at least one room failed runtime-model validation, referenced
  an unregistered AG-UI feature name, had a missing RAG file, or had
  a failing `count_documents` query. In `--quiet` mode, the per-room
  errors are printed as JSON on stdout before exit; unregistered
  feature names appear under the `agui_features` key.

#### Examples

List rooms for the minimal example:

```bash
soliplex-cli audit rooms example/minimal.yaml
```

Audit a directory-style installation:

```bash
soliplex-cli audit rooms example/
```

Just the room IDs and names, skipping the RAG detail:

```bash
soliplex-cli audit rooms example/installation.yaml | grep '^- \['
```

### `audit room-authz`

Bucket the configured rooms by their authorization state, and surface
any stale `RoomPolicy` rows left behind in the authorization database
by past room renames or removals.

```bash
soliplex-cli audit [OPTIONS] room-authz [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

Four buckets are printed (each a bulleted list of `room_id`s, or
`(none)` when empty):

- **Default** — configured rooms with no `RoomPolicy` row in the
  authorization database; public to all authenticated users by
  default.
- **Public** — configured rooms with a `RoomPolicy` row whose
  `default_allow_deny=ALLOW` (public-by-policy).
- **Private** — configured rooms with a `RoomPolicy` row whose
  `default_allow_deny=DENY`.
- **Stale** — `RoomPolicy` rows whose `room_id` is **not** present
  in the installation YAML. Each entry is suffixed with the literal
  marker `STALE`. These rows are typically orphaned leftovers from
  a room rename or removal, and they cannot be inspected or cleaned
  up through the (non-deprecated) `room-authz` commands, which
  require a configured `ROOM_ID`. Use
  [`room-authz show --allow-stale`](#room-authz-show) to inspect a
  specific stale policy.

When the installation's `authorization_dburi` is the in-memory
default (`sqlite://`), every configured room falls into the
**Default** bucket and the other three buckets are empty.

#### Exit Status

- `0` when the **Stale** bucket is empty.
- `1` when one or more stale rows are detected, regardless of how
  the configured rooms are distributed across the other three
  buckets. In `-q` / `--quiet` mode, the stale list is emitted to
  stdout as JSON of the form
  `{"room_authz": {"stale_rooms": ["<room_id>", …]}}`.

#### Examples

Inspect the room/authz state of the example installation:

```bash
soliplex-cli audit room-authz example/installation.yaml
```

CI-friendly check that no stale policies remain:

```bash
soliplex-cli audit -q room-authz example/installation.yaml
```

### `audit completions`

List the OpenAI-compatible completion endpoints declared in the
installation configuration, and validate that each one converts cleanly
to its runtime model. Each completion exposes a Soliplex agent as a
`/v1/chat/completions`-style endpoint so that existing OpenAI-client
code can talk to it unchanged. (Replaces the deprecated
`soliplex-cli list-completions`.)

```bash
soliplex-cli audit [OPTIONS] completions [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

For each completion endpoint declared in the installation, a two-line
entry is printed:

```text
- [ <completion_id> ] <name>:
  OK
```

`<completion_id>` is the key Soliplex uses internally to refer to the
endpoint; `<name>` is the human-readable label. Descriptions, model
bindings, and authorization rules are not shown — use
`audit all` (or read the YAML directly) to inspect those. If
the completion fails runtime-model validation, the `OK` line is
replaced by `ERROR: <message>`.

#### Behavior Notes

- **Bypasses authorization.** Like `audit rooms`, this command
  deliberately lists every completion configured in the installation,
  regardless of which endpoints any given user would be authorized to
  reach at runtime. It reflects configuration, not per-user visibility.

#### Exit Status

- `0` — every declared completion validated.
- `1` — at least one completion failed runtime-model validation. In
  `--quiet` mode, the per-completion errors are printed as JSON on
  stdout before exit.

#### Examples

List completions for the full installation example:

```bash
soliplex-cli audit completions example/installation.yaml
```

Audit a directory-style installation:

```bash
soliplex-cli audit completions example/
```

### `audit quizzes`

List the quiz question files declared in the installation configuration,
and validate that each `*.json` file under each configured quizzes path
loads and parses cleanly.

```bash
soliplex-cli audit [OPTIONS] quizzes [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

Each configured quizzes path is printed once as a header, followed by a
`- Question file: <name>` row for each `*.json` file found under that
path:

```text
Quiz path: <path>
- Question file: <name>
  OK
```

`<path>` is a directory configured in the installation's
`quizzes_paths`; `<name>` is the question file's full filename. If a
quiz file fails to load or parse, the `OK` line is replaced by
`Invalid quiz file: <message>`.

#### Exit Status

- `0` — every quiz file loaded and parsed.
- `1` — at least one quiz file failed to load or parse. In `--quiet`
  mode, the per-file errors are printed as JSON on stdout before exit.

#### Examples

List quizzes for the full installation example:

```bash
soliplex-cli audit quizzes example/installation.yaml
```

Audit a directory-style installation:

```bash
soliplex-cli audit quizzes example/
```

### `audit skills`

List the Haiku skills declared in the installation configuration and
run two complementary validation passes against them: (1) for each
configured `skill_config`, surface any errors recorded at load time;
(2) for each `SKILL.md`-bearing directory found under the configured
filesystem skills paths, run the full `skills_ref` validator.
(Replaces the deprecated `soliplex-cli list-skills`.)

```bash
soliplex-cli audit [OPTIONS] skills [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

The output has two parts. First, each configured skill is listed with
its kind, identifier, and description:

```text
- [ <kind>:<skill_name>  ]
  <description>
```

`<kind>` names the skill source type (e.g., the mechanism used to
discover or load it); `<skill_name>` is the identifier Soliplex uses
internally.

If a skill recorded errors at load time, its description is replaced
by a list of errors:

```text
- [ <kind>:<skill_name>  ]
  Validation errors:
  - <first error message>
  - <second error message>
```

Second, each filesystem skills path is walked, and every discovered
`SKILL.md` directory is run through the `skills_ref` validator:

```text
Filesystem skills path: <path>
- <skill_dir_name>
  OK
```

If validator errors are reported for a discovered directory, its `OK`
line is replaced by one line per error.

#### Exit Status

- `0` — every configured skill loaded cleanly **and** every filesystem
  skill directory passed the `skills_ref` validator.
- `1` — at least one configured skill recorded load-time errors, or at
  least one filesystem skill directory failed validation. In `--quiet`
  mode, the errors are printed as JSON on stdout before exit, with two
  top-level keys: `skills` (per-name configured-skill errors) and
  `skills_filesystem` (per-path filesystem-validator errors). Either
  key is omitted if its pass produced no errors.

#### Examples

List skills for the full installation example:

```bash
soliplex-cli audit skills example/installation.yaml
```

Audit a directory-style installation:

```bash
soliplex-cli audit skills example/
```

### `audit logging`

Show the Python-logging configuration referenced by the installation,
and validate that the configured YAML file (if any) loads and parses.

```bash
soliplex-cli audit [OPTIONS] logging [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

If the installation does not configure a `logging_config_file`, a single
line is printed:

```text
OK (defaults)
```

Otherwise, the configured path is shown along with the parsed YAML and
the installation's request-headers / token-claims maps:

```text
Logging config: <path>
<parsed YAML as a Python dict>
Headers map: <headers_map>
Claims map: <claims_map>
OK
```

If the file cannot be opened or fails to parse as YAML, the listing is
truncated after the path and the error message is printed in place of
the parsed body and `OK` line.

#### Exit Status

- `0` — no logging file configured, or the configured file loaded and
  parsed cleanly.
- `1` — the configured `logging_config_file` could not be opened or
  failed to parse as YAML. In `--quiet` mode, the error is printed as
  JSON (under the key `logging`) on stdout before exit.

#### Examples

Show the logging config for an installation that defines one:

```bash
soliplex-cli audit logging example/installation-openai.yaml
```

Confirm the default-logging path for an installation that does not
configure one:

```bash
soliplex-cli audit logging example/minimal.yaml
```

### `audit logfire`

Show the Logfire configuration referenced by the installation. This
subcommand performs no validation that can fail — it is a read-only
view of the YAML body that Soliplex would hand to Logfire at startup.

```bash
soliplex-cli audit [OPTIONS] logfire [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

If the installation does not configure a `logfire_config`, a single
line is printed:

```text
OK (defaults)
```

Otherwise, the configured Logfire body is printed as YAML, followed by
`OK`:

```text
<parsed YAML body>
OK
```

#### Exit Status

- Always `0`.

#### Examples

Show the Logfire body for an installation that defines one:

```bash
soliplex-cli audit logfire example/installation-openai.yaml
```

Confirm the defaults branch for an installation that does not configure
Logfire:

```bash
soliplex-cli audit logfire example/minimal.yaml
```

### `audit ollama`

For each Ollama server URL referenced by the installation, fetch the
list of models currently available on the server (via the `/api/tags`
endpoint) and compare it against the set of model names the
installation requires for that URL. Models named by the installation
but absent from the server are reported as needing to be pulled.

```bash
soliplex-cli audit [OPTIONS] ollama [INSTALLATION_CONFIG_PATH]
```

See [Group Options](#group-options) for the available `[OPTIONS]`.

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Output

A `Configured Ollama URLs` rule is printed, followed by one entry per
URL referenced by the installation:

```text
- <url>
  OK | MISSING: <comma-separated model names> | ERROR: <reason>
```

When models are missing, the line directly below the `MISSING:` entry
points to the `ollama pull` command:

```text
  Run 'soliplex-cli ollama pull' to pull missing models.
```

If the installation references no Ollama URLs, a single
`No Ollama URLs referenced by the installation.` line is printed and
the command exits cleanly.

#### Exit Status

- `0` — every required Ollama model is available on its server (or the
  installation references no Ollama URLs).
- `1` — at least one server is unreachable, **or** at least one
  required model is missing from a reachable server.

When the group's `-q` / `--quiet` flag is in effect, a `1` exit is
accompanied by a single JSON document on stdout under the `ollama` key:

```json
{
  "ollama": {
    "http://a.example.com": {"missing_models": ["mistral", "phi3"]},
    "http://b.example.com": {"unreachable": "('Connection refused',)"}
  }
}
```

A URL appears under `ollama` only when something went wrong on it;
reachable servers with no missing models are omitted from the JSON.

#### Examples

Audit Ollama availability for an installation:

```bash
soliplex-cli audit ollama example/installation.yaml
```

Drive the audit from automation, capturing missing-models JSON:

```bash
soliplex-cli audit -q ollama example/installation.yaml
```

## `admin-users`

The `admin-users` group manages the installation's admin-user table.
Each admin entry is an RFC 9535 JSONPath query stored in the
installation's authorization database; a user whose OIDC token matches
any admin entry's query is granted administrator privileges by the
Soliplex authorization policy engine. The common case — an admin keyed
by email — is stored as `$[?$.email == "..."]`, mirroring how
`room-authz` ACL entries store their discriminators. The subcommands
below read from and modify that table directly.

This group replaces the deprecated flat `list-admin-users` /
`add-admin-user` / `clear-admin-users` commands; see
[Deprecated Command Names](#deprecated-command-names).

These subcommands only make sense against a *persistent* authorization
database (configured via `authorization_dburi` in the installation
YAML). When the installation uses the default in-memory SQLite DB
(`sqlite://`), each command detects the RAM-based URI, prints a note
that the operation would be a no-op, and exits with status `1` without
touching the database. There is no override.

All three commands share the following conventions:

- Positional argument `INSTALLATION_CONFIG_PATH` — path to the
  installation configuration. May be a YAML file or a directory
  containing an `installation.yaml`. If omitted, falls back to the
  `SOLIPLEX_INSTALLATION_PATH` environment variable.
- On completion, the current admin-user list is dumped as a single
  JSON object on stdout (emitted via plain `print(...)`, not Rich, so
  the output pipes cleanly into `jq` or other tooling). Email-keyed
  admins surface as their email; an admin added with a non-email
  `--json-path` query surfaces as the raw query string:

  ```json
  {"admin_users": ["alice@example.com", "$[?$.role == \"admin\"]"]}
  ```

- The `-v` / `--verbose` and `-q` / `--quiet` flags at the **group**
  level (`soliplex-cli admin-users -v <subcommand> …`) toggle between
  the default JSON dump and a human-focused, Rich-rendered summary.
  Resolution: `--quiet` always forces JSON; `--verbose` (without
  `--quiet`) forces the human summary; with neither, the
  per-deployment default applies (currently JSON, set via
  `_DEFAULT_VERBOSE` in `cli/admin_users.py`). `--quiet` is intended
  as the override for scripts in a deployment that has flipped the
  default to verbose. Example verbose output:

  ```text
  ─── Admin users ───
  Admin users (2):
    1. alice@example.com
    2. bob@example.com
  ```

- Exit status is `0` on success, or `1` when the RAM-DB guard fires
  (or, for [`admin-users add`](#admin-users-add), when the discriminator
  selection is invalid or the resolved entry is already an admin).

### `admin-users list`

Dump the current set of admin users from the installation's
authorization database without changing anything. (Replaces the
deprecated `soliplex-cli list-admin-users`.)

```bash
soliplex-cli admin-users list [OPTIONS] [INSTALLATION_CONFIG_PATH]
```

#### Examples

List admin users for a full installation:

```bash
soliplex-cli admin-users list example/installation.yaml
```

Extract just the emails with `jq`:

```bash
soliplex-cli admin-users list example/installation.yaml \
  | jq -r '.admin_users[]'
```

### `admin-users add`

Insert a new admin entry into the installation's authorization database
and then dump the resulting list. (Replaces the deprecated
`soliplex-cli add-admin-user`.)

```bash
soliplex-cli admin-users add [OPTIONS] INSTALLATION_CONFIG_PATH [EMAIL]
```

Exactly one discriminator must be supplied, naming which user token(s)
the entry grants admin to: the positional `EMAIL` (shorthand for the
common case), `--preferred-username USERNAME`, or `--json-path QUERY`.
Each is stored as an RFC 9535 JSONPath query — `EMAIL` and
`--preferred-username` as `$[?$.email == "..."]` /
`$[?$.preferred_username == "..."]`, and `--json-path` verbatim (after
validation). `check_admin_access` admits a user when their token matches
any stored query, so `--json-path` can grant admin by an arbitrary
claim (e.g. group membership).

#### Positional Arguments

- `INSTALLATION_CONFIG_PATH` — as described above.
- `EMAIL` — optional; the email address to grant admin privileges,
  matched against the authenticated user's OIDC-asserted `email` claim.
  No format validation is performed by the CLI. Mutually exclusive with
  `--preferred-username` and `--json-path`.

#### Options

- `--preferred-username USERNAME` — grant admin by OIDC
  `preferred_username` claim. Mutually exclusive with `EMAIL` and
  `--json-path`.
- `--json-path QUERY` — grant admin to any user token matched by this
  RFC 9535 JSONPath query. The query is validated; a malformed query is
  reported and the command exits non-zero. Mutually exclusive with
  `EMAIL` and `--preferred-username`.

#### Behavior Notes

- **Exactly one discriminator.** Supplying none — or more than one — of
  `EMAIL` / `--preferred-username` / `--json-path` is reported and the
  command exits with status `1` without touching the table.
- **Rejects duplicates.** Before inserting, the command checks whether
  the resolved query is already an admin. If it is, the command prints a
  note and exits with status `1` without touching the table — the
  `AdminUser.json_path` column is unique, so a blind second insert would
  otherwise fail with a backend-specific `IntegrityError`. Re-adding an
  already-present admin is thus a safe, non-destructive no-op, signalled
  by the non-zero exit code; run `admin-users list` to see the current
  set.

#### Examples

Grant admin privileges to a new operator by email:

```bash
soliplex-cli admin-users add example/installation.yaml alice@example.com
```

Grant admin by `preferred_username`, or by an arbitrary claim:

```bash
soliplex-cli admin-users add example/installation.yaml \
  --preferred-username alice
soliplex-cli admin-users add example/installation.yaml \
  --json-path '$[?$.groups[?@ == "admins"]]'
```

### `admin-users clear`

Remove **every** row from the installation's admin-user table, then
dump the (now empty) list. (Replaces the deprecated
`soliplex-cli clear-admin-users`.)

```bash
soliplex-cli admin-users clear [OPTIONS] [INSTALLATION_CONFIG_PATH]
```

#### Behavior Notes

- **Destructive.** This command is unconditional: there is no
  per-email filter, no confirmation prompt, and no backup is taken.
  If you have multiple admins and only want to remove one, use your
  database's own tooling — this CLI has no single-user-delete
  subcommand.
- **Follow-up required.** After clearing, no user is an admin. If the
  installation relies on admin privileges for its bootstrap flow
  (e.g. to configure rooms or seed authorization), re-run
  `admin-users add` before restarting `serve`.

#### Examples

Drop all admins from a production-style installation:

```bash
soliplex-cli admin-users clear example/installation.yaml
```

Wipe-and-seed — start from a known state, then add a single admin:

```bash
soliplex-cli admin-users clear example/installation.yaml
soliplex-cli admin-users add example/installation.yaml alice@example.com
```

## `room-authz`

The `room-authz` group manages per-room authorization policies. Room-
level authorization lets the installation restrict which users can see
and interact with a given room, on top of the admin-user mechanism
described above. The subcommands below read from and modify the per-room
authorization policy stored in the installation's authorization
database.

This group replaces the deprecated flat `show-room-authz` command;
see [Deprecated Command Names](#deprecated-command-names).

### The Model in One Paragraph

Each room's authorization is captured by a `RoomPolicy` row plus zero or
more `ACLEntry` rows attached to it. A `RoomPolicy` has a
`default_allow_deny` flag (default: `DENY`) that applies when no ACL
entry matches the requesting user. An `ACLEntry` has an `allow_deny`
flag plus a discriminator — one of `everyone`, `authenticated`,
`preferred_username`, or `email` — used to decide whether it matches
the caller's token. The first matching entry wins; if none match, the
policy's `default_allow_deny` is used.

The critical distinction to keep in mind is between **no policy row**
and **an empty policy row**:

- A room with **no `RoomPolicy` row at all** is treated as **public**:
  every authenticated user is allowed in. This is the default state of
  every room on a fresh authz database.
- A room with a `RoomPolicy` row and **no matching ACL entries** falls
  through to `default_allow_deny`, which defaults to `DENY` — making
  the room effectively **private**.

The six commands below create, inspect, edit, and populate these
rows.

### Shared Conventions

All six commands share the following:

- Positional argument `INSTALLATION_CONFIG_PATH` — as documented in the
  [`admin-users`](#admin-users) section. If omitted, falls back to
  `SOLIPLEX_INSTALLATION_PATH`.
- Positional argument `ROOM_ID` — the `id` of a configured room (the
  same identifier surfaced by `audit rooms`). The commands validate
  that `ROOM_ID` matches a room in the installation YAML; an
  unknown id prints an error (with the list of configured rooms,
  when any are defined) and exits with status `1` without touching
  the authorization database. The read-only [`show`](#room-authz-show)
  command supports an `--allow-stale` escape hatch for inspecting
  policies left behind by removed or renamed rooms; the other
  commands do not, so cleanup of stale rows still requires direct
  database tooling.
- As with `admin-users`, when the installation's `authorization_dburi`
  is the in-memory default (`sqlite://`), each command detects the
  RAM-based URI, prints a note that the operation would be a no-op,
  and exits with status `1` without touching the database. There is
  no override.
- On completion, the resulting `RoomPolicy` is dumped as a single JSON
  object on stdout (emitted via plain `print(...)`, not Rich). If no
  policy row exists for the room, `null` is printed instead.

  Example output:

  ```json
  {
    "room_id": "chat",
    "default_allow_deny": "DENY",
    "acl_entries": [
      {
        "allow_deny": "ALLOW",
        "everyone": false,
        "authenticated": false,
        "preferred_username": null,
        "email": "alice@example.com"
      }
    ]
  }
  ```

- The `-v` / `--verbose` and `-q` / `--quiet` flags at the
  **group** level (`soliplex-cli room-authz -v <subcommand> …`)
  toggle between the default JSON dump and a human-focused,
  Rich-rendered summary. Resolution: `--quiet` always forces JSON;
  `--verbose` (without `--quiet`) forces the human summary; with
  neither, the per-deployment default applies (currently JSON, set
  via `_DEFAULT_VERBOSE` in `cli/room_authz.py`). `--quiet` is
  intended as the override for scripts in a deployment that has
  flipped the default to verbose. Example verbose output:

  ```text
  ─── Room policy: chat ───
  Default: DENY (private -- denies callers that don't match an ALLOW entry).
  ACL entries (2):
    1. ALLOW  email=alice@example.com
    2. DENY   everyone
  ```

- Exit status is `0` on success (including when no policy row exists
  for the room), or `1` when the RAM-DB guard fires or `ROOM_ID`
  doesn't match a configured room.

### `room-authz show`

Dump the current `RoomPolicy` for a single room without changing it.
(Replaces the deprecated `soliplex-cli show-room-authz`.)

```bash
soliplex-cli room-authz show [OPTIONS] INSTALLATION_CONFIG_PATH ROOM_ID
```

#### Options

- `--allow-stale` — skip the configured-room check that the rest of
  the `room-authz` commands enforce. `show` will dump whatever
  policy row (if any) exists in the authorization database for the
  given `ROOM_ID`, even when the id isn't present in the
  installation's current YAML. Useful for inspecting stale policies
  left behind by a room rename or removal.

#### Examples

Inspect the policy for the `chat` room:

```bash
soliplex-cli room-authz show example/installation.yaml chat
```

Extract just the list of allowed emails with `jq`:

```bash
soliplex-cli room-authz show example/installation.yaml chat \
  | jq -r '.acl_entries[] | select(.allow_deny == "ALLOW") | .email'
```

A `null` response means no `RoomPolicy` row exists yet — i.e. the room
is in its default public state:

```bash
$ soliplex-cli room-authz show example/installation.yaml search
null
```

Inspect a stale policy for a room that has since been removed from
the YAML — without `--allow-stale` this would exit with status `1`:

```bash
soliplex-cli room-authz show --allow-stale \
  example/installation.yaml old-room-id
```

### `room-authz as-yaml`

Dump a room's `RoomPolicy` and ACL entries as YAML. This is the YAML
counterpart of [`show`](#room-authz-show) (which emits JSON), and the
inverse of [`from-yaml`](#room-authz-from-yaml).

```bash
soliplex-cli room-authz as-yaml [OPTIONS] INSTALLATION_CONFIG_PATH ROOM_ID
```

#### Options

- `--output`, `-o PATH` — write the YAML to this file path. If
  omitted, the YAML is written to standard output with no console or
  rule decoration, so it is safe to pipe or redirect.
- `--allow-stale` — skip the configured-room check, so a policy left
  behind by a removed or renamed room can still be dumped (same
  semantics as [`show`](#room-authz-show)).

#### Behavior Notes

- **Public-model shape.** The YAML mirrors the public `ACLEntry`
  model, so an entry stored as a `preferred_username` or `email`
  query is surfaced back under `preferred_username` / `email` (with
  `json_path: null`), and a general-purpose query is surfaced under
  `json_path`. The document re-loads cleanly via
  [`from-yaml`](#room-authz-from-yaml).
- **No policy dumps as `null`.** A room with no `RoomPolicy` row dumps
  as a `null` document.

#### Exit Status

- `0` on success.
- `1` when the `ROOM_ID` is not configured and `--allow-stale` was not
  passed, or when the RAM-DB guard fires.

#### Examples

Dump the `chat` policy to standard output:

```bash
soliplex-cli room-authz as-yaml example/installation.yaml chat
```

Save a policy to a file (e.g. to back it up or edit it):

```bash
soliplex-cli room-authz as-yaml \
  --output chat-policy.yaml \
  example/installation.yaml chat
```

### `room-authz from-yaml`

Load a room's `RoomPolicy` and ACL entries from YAML, replacing any
existing policy for the target room. The YAML uses the same shape
produced by [`as-yaml`](#room-authz-as-yaml), so the two commands
round-trip.

```bash
soliplex-cli room-authz from-yaml [OPTIONS] INSTALLATION_CONFIG_PATH [ROOM_ID]
```

#### Arguments

- `ROOM_ID` (optional) — the target room. If omitted, the `room_id`
  recorded in the input YAML is used.

#### Options

- `--input`, `-i PATH` — read the YAML from this file path. If
  omitted, the YAML is read from standard input.

#### Behavior Notes

- **Target room resolution.** When `ROOM_ID` is given it is
  authoritative — the policy is written for `ROOM_ID` regardless of
  the `room_id` recorded in the YAML (useful for copying one room's
  policy onto another). When `ROOM_ID` is omitted, the YAML's own
  `room_id` is used.
- **Whole-policy replace.** Any existing policy for the target room
  (and all its ACL entries) is replaced by the imported one.
- **`null` removes the policy.** Importing a `null` document deletes
  the target room's `RoomPolicy` entirely, returning it to the default
  public state.
- **Configured-room check.** Unlike [`as-yaml`](#room-authz-as-yaml),
  `from-yaml` always requires the target room to be configured in the
  installation's YAML; there is no `--allow-stale` escape hatch.

#### Exit Status

- `0` on success.
- `1` when no target room can be resolved (a `null` import with no
  `ROOM_ID`), when the target room is not configured, or when the
  RAM-DB guard fires.

#### Examples

Round-trip a policy through a file (export, then re-import):

```bash
soliplex-cli room-authz as-yaml \
  --output chat-policy.yaml \
  example/installation.yaml chat
soliplex-cli room-authz from-yaml \
  --input chat-policy.yaml \
  example/installation.yaml chat
```

Copy the `chat` policy onto the `search` room (the explicit `ROOM_ID`
overrides the `room_id` in the piped YAML):

```bash
soliplex-cli room-authz as-yaml example/installation.yaml chat \
  | soliplex-cli room-authz from-yaml example/installation.yaml search
```

Apply a policy to whichever room its YAML names (omit `ROOM_ID`):

```bash
soliplex-cli room-authz from-yaml \
  --input chat-policy.yaml \
  example/installation.yaml
```

### `room-authz make-private`

Ensure a room is private by inserting an empty `RoomPolicy` row
(`default_allow_deny=DENY`, no ACL entries) when none exists for the
room. Idempotent for rooms that are already private; refuses to
silently overwrite an existing public-by-policy room unless
`--update` is passed.

This is the non-destructive counterpart to `clear --make-room-private`:
no existing ACL entries are deleted by this command.

```bash
soliplex-cli room-authz make-private [OPTIONS] INSTALLATION_CONFIG_PATH ROOM_ID
```

#### Options

- `--update` — when an existing `RoomPolicy` row is found with
  `default_allow_deny=ALLOW`, flip it in place to `DENY`. ACL entries
  are preserved either way. Without this flag, encountering an
  `ALLOW` policy is treated as an error (see Exit Status below).

#### Behavior Notes

- **Non-destructive.** ACL entries are never deleted. If a
  `RoomPolicy` already exists and is already private
  (`default_allow_deny=DENY`), the command is a no-op and the
  existing policy — including all its ACL entries — is dumped
  unchanged.
- **Public-no-row vs. public-by-policy.** A room with no policy row
  at all is the default public state; this command transitions it
  directly to private (`DENY`, no entries) without needing
  `--update`. A room with an explicit policy whose
  `default_allow_deny=ALLOW` is a deliberately public-by-policy
  room — the command refuses to flip it without `--update`, so an
  operator who relied on the explicit ALLOW isn't silently overridden.
- **Pairs with `add-acl-entry`.** Run `make-private` first to lock
  the room down, then use
  [`add-acl-entry`](#room-authz-add-acl-entry) to grant access to
  specific users.

#### Exit Status

- `0` on success — policy created, already private, or successfully
  flipped to `DENY` under `--update`.
- `1` when the existing policy has `default_allow_deny=ALLOW` and
  `--update` is not passed, or when the RAM-DB guard fires.

#### Examples

Make the `chat` room private as a fresh setup step:

```bash
soliplex-cli room-authz make-private example/installation.yaml chat
```

Re-run safely — the room is already private, so the command is a
no-op and dumps the existing policy:

```bash
soliplex-cli room-authz make-private example/installation.yaml chat
```

Flip an explicitly public-by-policy room to private while preserving
any existing ALLOW ACL entries (so previously-listed users keep
access and everyone else is now denied):

```bash
soliplex-cli room-authz make-private --update \
  example/installation.yaml chat
```

Make-private then grant a single user explicit access:

```bash
soliplex-cli room-authz make-private example/installation.yaml chat
soliplex-cli room-authz add-acl-entry \
  --allow --email alice@example.com \
  example/installation.yaml chat
```

### `room-authz make-public`

Ensure a room is public. Inverse of `make-private`: a room with no
`RoomPolicy` row is already public-to-all-authenticated-users, so the
command is a no-op in that case; a room with an existing policy whose
`default_allow_deny=ALLOW` is also already public-by-policy, again a
no-op. The command refuses to silently flip a private room
(`default_allow_deny=DENY`) to public unless `--update` is passed.

Existing ACL entries are preserved; the command only ever toggles
`default_allow_deny`.

```bash
soliplex-cli room-authz make-public [OPTIONS] INSTALLATION_CONFIG_PATH ROOM_ID
```

#### Options

- `--update` — when an existing `RoomPolicy` row is found with
  `default_allow_deny=DENY`, flip it in place to `ALLOW`. ACL entries
  are preserved either way. Without this flag, encountering a `DENY`
  policy is treated as an error (see Exit Status below).

#### Behavior Notes

- **Non-destructive.** ACL entries are never deleted. After
  `--update`, any existing `ALLOW` entries become redundant (everyone
  is now allowed by default) and any existing `DENY` entries continue
  to block their specific users; if that's not what you want, follow
  up with [`clear-acl`](#room-authz-clear-acl) and rebuild.
- **No row needed for "public."** Unlike `make-private`, this command
  does not create a `RoomPolicy` row in the no-row case — the room
  is already in the default public state. As a result, the JSON
  dump may be `null` after a successful run.

#### Exit Status

- `0` on success — already public, or successfully flipped to
  `ALLOW` under `--update`.
- `1` when the existing policy has `default_allow_deny=DENY` and
  `--update` is not passed, or when the RAM-DB guard fires.

#### Examples

Confirm a room is public (no-op when already in the default state):

```bash
soliplex-cli room-authz make-public example/installation.yaml chat
```

Flip a previously-private room to public while preserving its ACL
entries (so any `DENY` entries continue to block their specific
users):

```bash
soliplex-cli room-authz make-public --update \
  example/installation.yaml chat
```

Open a room back up *and* drop its ACL entries — combine with
[`clear-acl`](#room-authz-clear-acl):

```bash
soliplex-cli room-authz make-public --update example/installation.yaml chat
soliplex-cli room-authz clear-acl example/installation.yaml chat
```

### `room-authz add-acl-entry`

Add an `ACLEntry` to a room's `RoomPolicy`. The entry's allow/deny
flag is selected with `--allow` or `--deny`; the entry's
discriminator (what it matches against the caller's token) is
selected with one of `--everyone`, `--authenticated`, `--json-path`,
`--preferred-username`, or `--email`.

The room must already have a `RoomPolicy` row — run
[`make-private`](#room-authz-make-private) or
[`make-public`](#room-authz-make-public) first to establish the
policy's `default_allow_deny`. This avoids silently flipping a
public room to private as a side effect of adding the first entry.

```bash
soliplex-cli room-authz add-acl-entry [OPTIONS] INSTALLATION_CONFIG_PATH ROOM_ID
```

#### Options

Exactly one of:

- `--allow` — the entry grants access.
- `--deny` — the entry denies access.

Exactly one of (the discriminator — what the entry matches on):

- `--everyone` — matches every request, regardless of token. Useful
  as a catch-all that sets effective behavior independent of the
  policy's `default_allow_deny`.
- `--authenticated` — matches any caller with a valid OIDC token,
  regardless of identity.
- `--json-path TEXT` — matches when the [RFC 9535][rfc9535] JSONPath
  query `TEXT` selects at least one node from the caller's token.
  This is the underlying claim discriminator; the two options below
  are convenience aliases for the common equality case.
- `--preferred-username TEXT` — convenience alias matching a caller
  whose OIDC `preferred_username` claim equals `TEXT`. Stored as the
  equivalent `--json-path` query `$[?$.preferred_username == "TEXT"]`.
- `--email TEXT` — convenience alias matching a caller whose OIDC
  `email` claim equals `TEXT`. Stored as the equivalent `--json-path`
  query `$[?$.email == "TEXT"]`.

[rfc9535]: https://www.rfc-editor.org/rfc/rfc9535

#### Behavior Notes

- **Existing policy required.** If no `RoomPolicy` row exists for the
  room, the command prints an error and exits with status `1`. Run
  `make-private` (or `make-public`) first.
- **Dedup is per-discriminator.** Adding an entry whose discriminator
  matches an existing entry on the policy deletes the existing entry
  before inserting the new one. Adding `--allow --email alice@x.y`
  replaces any prior `email=alice@x.y` entry (whether previously
  `ALLOW` or `DENY`). Entries keyed by other discriminators
  (`--preferred-username alice`, `--email bob@x.y`, etc.) are left
  alone.
- **First-match-wins, in insertion order.** ACL entries are checked
  in their creation order at request time; the first one whose
  discriminator matches the caller wins (see
  `ACLEntry.check_token`). This means a `--deny --email alice@x.y`
  added *after* a `--allow --everyone` will still keep Alice out,
  because the `email` entry matches her token before the catch-all
  fires — but only if Alice's row was created *before* the
  `--everyone` row. When ordering matters, build the policy from
  most-specific to least-specific.

#### Exit Status

- `0` on success.
- `1` when `--allow`/`--deny` are both passed or both omitted; when
  no (or more than one) discriminator option is supplied; when no
  `RoomPolicy` exists for the room; or when the RAM-DB guard fires.

#### Examples

Grant a single user access to a private room:

```bash
soliplex-cli room-authz add-acl-entry \
  --allow --email alice@example.com \
  example/installation.yaml chat
```

Block a single user on a public-by-policy room:

```bash
soliplex-cli room-authz add-acl-entry \
  --deny --email mallory@example.com \
  example/installation.yaml chat
```

Open the room to every authenticated user, on top of an existing
private policy (useful for temporarily widening access without
flipping `default_allow_deny`):

```bash
soliplex-cli room-authz add-acl-entry \
  --allow --authenticated \
  example/installation.yaml chat
```

Keyed by `preferred_username` instead of `email`:

```bash
soliplex-cli room-authz add-acl-entry \
  --allow --preferred-username alice \
  example/installation.yaml chat
```

Catch-all `DENY` for a public-by-policy room, with selective ALLOW
exceptions added beforehand (because earlier entries win):

```bash
soliplex-cli room-authz make-public example/installation.yaml chat
soliplex-cli room-authz add-acl-entry \
  --allow --email alice@example.com \
  example/installation.yaml chat
soliplex-cli room-authz add-acl-entry \
  --deny --everyone \
  example/installation.yaml chat
```

### `room-authz delete-acl-entry`

Delete a single `ACLEntry` from a room's `RoomPolicy`. The entry is
identified by the same parameter shape as
[`add-acl-entry`](#room-authz-add-acl-entry): the combination of
`--allow`/`--deny` and one discriminator option (`--everyone`,
`--authenticated`, `--json-path`, `--preferred-username`, or
`--email`).

The room must already have a `RoomPolicy` row with at least one ACL
entry matching the supplied parameters. If no match is found, the
command exits with status `1` so the operator can tell that the
delete was a no-op.

```bash
soliplex-cli room-authz delete-acl-entry [OPTIONS] INSTALLATION_CONFIG_PATH ROOM_ID
```

#### Options

Exactly one of:

- `--allow` — match an `ALLOW` entry.
- `--deny` — match a `DENY` entry.

Exactly one of (the discriminator):

- `--everyone` — match an `everyone` entry.
- `--authenticated` — match an `authenticated` entry.
- `--json-path TEXT` — match an entry whose JSONPath query equals
  `TEXT`. This is the underlying claim discriminator; the two options
  below are convenience aliases for the common equality case.
- `--preferred-username TEXT` — convenience alias matching the entry
  stored as the equivalent `--json-path` query
  `$[?$.preferred_username == "TEXT"]`.
- `--email TEXT` — convenience alias matching the entry stored as the
  equivalent `--json-path` query `$[?$.email == "TEXT"]`.

#### Behavior Notes

- **Exact match on (allow/deny, discriminator).** An entry with the
  same discriminator but the opposite allow/deny flag is *not* a
  match. To swap an entry from `DENY` to `ALLOW` for the same
  discriminator, just call
  [`add-acl-entry`](#room-authz-add-acl-entry) with the new flag —
  its per-discriminator dedup will replace the existing row.
- **Policy preserved.** Only the matching ACL entries are removed;
  the `RoomPolicy` row remains. The room's `default_allow_deny`
  is unchanged.
- **Multiple matches.** If the database somehow contains more than
  one entry matching the supplied parameters (which the CLI cannot
  produce on its own, but a seed YAML or direct DB write could),
  all matches are deleted.

#### Exit Status

- `0` on success — at least one matching entry was deleted.
- `1` when `--allow`/`--deny` are both passed or both omitted; when
  no (or more than one) discriminator option is supplied; when no
  `RoomPolicy` exists for the room; when no entry matches the
  supplied parameters; or when the RAM-DB guard fires.

#### Examples

Revoke a single user's access:

```bash
soliplex-cli room-authz delete-acl-entry \
  --allow --email alice@example.com \
  example/installation.yaml chat
```

Remove a `DENY` blocking a specific user, so they fall back to the
policy's `default_allow_deny`:

```bash
soliplex-cli room-authz delete-acl-entry \
  --deny --email mallory@example.com \
  example/installation.yaml chat
```

Lift a temporary `--allow --authenticated` catch-all that was added
to widen access while keeping the policy private:

```bash
soliplex-cli room-authz delete-acl-entry \
  --allow --authenticated \
  example/installation.yaml chat
```

### `room-authz clear-acl`

Delete every `ACLEntry` attached to a room's `RoomPolicy` while
leaving the policy itself in place. The room's `default_allow_deny`
setting is preserved: a private room (`DENY`) stays private and now
denies *everyone* (no ACL entries left to grant exceptions); a
public-by-policy room (`ALLOW`) stays public-by-policy.

```bash
soliplex-cli room-authz clear-acl [OPTIONS] INSTALLATION_CONFIG_PATH ROOM_ID
```

#### Behavior Notes

- **Policy preserved.** The `RoomPolicy` row is not deleted, only
  its ACL entries; pair with `make-private` or `make-public` if
  you also need to change the room's `default_allow_deny`.
- **No-op on the no-row case.** If no `RoomPolicy` exists for the
  room, the command makes no changes and dumps `null`. (There are
  no ACL entries to clear without a parent policy.)
- **Destructive and unconditional.** There is no per-discriminator
  filter and no confirmation prompt — every ACL entry on the policy
  is removed in one call. If you want to revoke a single user, use
  your database tooling or rebuild the ACL with repeated
  [`add-acl-entry`](#room-authz-add-acl-entry) calls.
- **"Lock everyone out, then re-grant" primitive.** Run
  `clear-acl` on a private room and the policy row stays in place
  with zero allowed users; follow up with
  [`add-acl-entry`](#room-authz-add-acl-entry) to re-grant access
  to a fresh set of users.

#### Examples

Strip every ACL entry from the `chat` room while keeping it
private (no one can get in until `add-acl-entry` is run again):

```bash
soliplex-cli room-authz clear-acl example/installation.yaml chat
```

Reset-and-seed — clear all existing access without changing the
room's privacy setting, then grant one user:

```bash
soliplex-cli room-authz clear-acl example/installation.yaml chat
soliplex-cli room-authz add-acl-entry \
  --allow --email alice@example.com \
  example/installation.yaml chat
```

## `ollama`

The `ollama` group bundles subcommands that interact with Ollama servers
referenced by the installation. Currently a single subcommand,
`ollama pull`.

This group replaces the deprecated flat `pull-models` command; see
[Deprecated Command Names](#deprecated-command-names).

### Group Options

- `-q` / `--quiet` — suppress human-readable console output and emit
  any errors as a single JSON document on stdout. The command still
  exits non-zero on failure (see each subcommand's
  [Exit Status](#exit-status)). Useful for piping into `jq` or for
  driving the command from automation. Belongs to the group, so it
  must appear before the subcommand name (e.g.
  `soliplex-cli ollama -q pull example/installation.yaml`).

### `ollama pull`

Scan the installation for every Ollama model referenced by its agents,
completions, or tools, and pull each model onto the corresponding Ollama
server via that server's REST API. Intended to preload a fresh Ollama
deployment so that the first user-facing request against Soliplex
doesn't have to wait for a cold-start model download. (Replaces the
deprecated `soliplex-cli pull-models`.)

```bash
soliplex-cli ollama pull [OPTIONS] [INSTALLATION_CONFIG_PATH]
```

#### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

#### Options

- `-u URL` / `--ollama-url URL` — restrict the scan to one or more
  Ollama base URLs referenced by the installation. Repeatable: pass the
  flag once per URL (e.g. `-u http://a.example.com -u
  http://b.example.com`). If omitted, the command pulls models on
  *every* Ollama URL referenced by the installation (installations may
  point different rooms at different Ollama instances). Each supplied
  URL must already be referenced by the installation — see
  [Behavior Notes](#behavior-notes).
- `-n` / `--dry-run` — scan the installation and print the model list
  per URL without actually pulling. Useful for verifying what *would*
  happen before committing to potentially slow downloads.

#### Behavior

For each Ollama URL in scope, the command:

1. Reports the URL and the count of distinct models the installation
   references at it.
2. Iterates the model names in sorted order, printing
   `Pulling: <model_name>` for each. Unless `--dry-run` is set, the
   model is then pulled via Ollama's REST API (`stream=False` — each
   pull blocks until complete, so no per-chunk progress is shown) and
   the final status line returned by Ollama is printed below the
   `Pulling:` line.
3. Unless `--dry-run` is set, prints a summary in the form
   `Pulled <success_count>/<total> model(s) successfully`.

If a URL has no models referenced by the installation, a
`No Ollama models for URL: <url>` line is printed and nothing is
pulled for that URL.

#### Behavior Notes

- **Network-heavy and slow.** Each `pull` downloads potentially many
  gigabytes per model. Use `--dry-run` first if you're unsure what the
  command will fetch.
- **Per-model errors are reported inline.** Network failures
  (`requests.RequestException`) and missing-status responses are shown
  in red alongside the model name and counted against the success
  total, but do not abort the per-URL loop. Other models on the same
  URL will still be pulled. The command does exit non-zero at the end
  if any pull failed — see [Exit Status](#exit-status).
- **`--ollama-url` is validated against the installation.** Each
  supplied URL must already appear among the Ollama URLs the
  installation references. If any supplied URL is unknown, the command
  prints the list of configured Ollama URLs (or notes that there are
  none) and exits non-zero without pulling anything. The flag filters
  the existing set; it does not inject a new destination.
- **Non-Ollama providers are ignored.** Models bound to OpenAI, Gemini,
  or any other non-Ollama provider are not considered here; this
  command deals strictly with the local-model case.

#### Exit Status

- `0` — every requested pull succeeded, `--dry-run` was specified, or
  the in-scope URLs referenced no Ollama models.
- `1` — at least one individual model pull failed, **or** one or more
  `--ollama-url` values were not referenced by the installation.

When the group's `-q` / `--quiet` flag is in effect, a `1` exit is
accompanied by a single JSON document on stdout. The document is a
mapping whose keys identify the failure mode:

- `unknown_ollama_urls`: list of URLs supplied via `--ollama-url` that
  the installation does not reference.
- `pulls`: mapping of Ollama URL → mapping of model name → error
  message, populated when individual pulls fail.

The two keys are mutually exclusive in practice: the unknown-URLs
check fires before any pulls are attempted, so a run that fails on
unknown URLs reports `unknown_ollama_urls` and skips the pull loop.

#### Examples

Preview which models would be pulled, without pulling anything:

```bash
soliplex-cli ollama pull example/installation.yaml --dry-run
```

Pull every Ollama model referenced by a full installation:

```bash
soliplex-cli ollama pull example/installation.yaml
```

Pull models only for a specific Ollama instance (useful when an
installation references multiple Ollama URLs):

```bash
soliplex-cli ollama pull example/installation.yaml \
  --ollama-url http://ollama.internal:11434
```

Restrict the scan to several specific Ollama instances by repeating
`--ollama-url`:

```bash
soliplex-cli ollama pull example/installation.yaml \
  --ollama-url http://ollama-a.internal:11434 \
  --ollama-url http://ollama-b.internal:11434
```

Drive the command from automation, suppressing the rule-decorated
output and capturing any errors as JSON:

```bash
soliplex-cli ollama -q pull example/installation.yaml
```

## `config`

Dump the installation's fully-resolved declarative configuration as a
single YAML document on stdout. Useful for debugging how nested config
files and defaults combine, for diffing two installations, or for
producing a flattened reference copy of a configuration that is
normally split across many files.

```bash
soliplex-cli config [INSTALLATION_CONFIG_PATH]
```

### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

### Output

The command prints a three-line banner comment followed by the YAML
document:

```text
#------------------------------------------------------------------------------
# Source: <installation_config_path>
#------------------------------------------------------------------------------
<yaml document>
```

Key ordering is preserved from the original declaration (the dump uses
`sort_keys=False`), so the output tracks the structure of the
hand-written YAML rather than reshuffling it alphabetically.

The YAML is the **declarative** form of the config: every secret
appears as its configured source (kind + `secret_name` + source-specific
arguments such as `env_var_name`, `file_path`, or `command_line`), not
as the resolved value. Running `config` against an installation and
feeding the output back into Soliplex should yield an equivalent
installation.

### Behavior Notes

- **Tolerant of unresolved secrets and environment variables.** The
  command attempts to resolve both before dumping, but swallows
  `SecretsNotFound` and `MissingEnvVars`. This lets you export the
  declarative YAML even on a machine that is missing the credentials
  or environment needed to actually run the installation.
- **Redirect with care.** Although resolved secret *values* are never
  printed, the dump does include operationally sensitive material:
  configured subprocess command lines used to fetch secrets, file paths
  on the host, server URLs, database URIs (which may themselves
  embed credentials), and OIDC client identifiers. Treat the output
  with the same care you would give the installation YAML itself.

### Exit Status

- Always `0`. Use `audit all` if you need a non-zero exit on
  configuration problems.

### Examples

Dump the minimal example:

```bash
soliplex-cli config example/minimal.yaml
```

Snapshot a directory-style installation to a file:

```bash
soliplex-cli config example/ > snapshot.yaml
```

Diff two installations after normalizing both through `config`:

```bash
diff \
  <(soliplex-cli config example/minimal.yaml) \
  <(soliplex-cli config example/installation.yaml)
```

## `agui-feature-schemas`

Export the JSON Schemas for every AG-UI feature registered in the
installation. An AG-UI "feature" is a contract — named by a key within
the AG-UI protocol's `state` mapping — whose shape is defined by a
Pydantic model. This command dumps each feature's schema alongside its
source (`client`, `server`, or `either`), suitable for consumption by
client-side code generators or schema-diffing tools.

```bash
soliplex-cli agui-feature-schemas [INSTALLATION_CONFIG_PATH]
```

### Positional Argument

- `INSTALLATION_CONFIG_PATH` — path to the installation configuration.
  May be a YAML file, or a directory containing an `installation.yaml`.
  If omitted, falls back to the `SOLIPLEX_INSTALLATION_PATH` environment
  variable.

### Output

The command prints a single JSON object on stdout, mapping each
feature's `name` to a two-field record:

```json
{
  "<feature_name>": {
    "source": "<client|server|either>",
    "json_schema": { /* Pydantic-generated JSON Schema */ }
  }
}
```

- `source` identifies which side of the AG-UI protocol is allowed to
  write this feature's slot of the `state` mapping. `either` means
  both client and server may write it.
- `json_schema` is the Pydantic model's `model_json_schema()` output,
  suitable for feeding into any JSON-Schema-aware code generator.

The output is compact (`json.dumps` with no `indent`) and emitted on
raw stdout — no banner, no rich formatting, no trailing commentary —
so it pipes cleanly into `jq`, code generators, or file redirections.

### Exit Status

- Always `0`.

### Examples

Dump the feature schemas from the minimal example and pretty-print
with `jq`:

```bash
soliplex-cli agui-feature-schemas example/minimal.yaml | jq .
```

List just the registered feature names:

```bash
soliplex-cli agui-feature-schemas example/installation.yaml \
  | jq 'keys'
```

Snapshot the schemas to a file for client-side code generation:

```bash
soliplex-cli agui-feature-schemas example/ > agui-features.json
```

## Deprecated Command Names

Prior releases exposed each subcommand as a flat top-level name
(`check-config`, `list-secrets`, `pull-models`, etc.). Those names are
preserved as **hidden aliases** — existing scripts continue to work — but
they no longer appear in `soliplex-cli --help` and may be removed in a
future major release. New scripts should use the grouped form.

| Deprecated                    | Use instead                |
|-------------------------------|----------------------------|
| `check-config`                | `audit` (or `audit all`)   |
| `list-secrets`                | `audit secrets`            |
| `list-environment`            | `audit environment`        |
| `list-oidc-auth-providers`    | `audit oidc`               |
| `list-rooms`                  | `audit rooms`              |
| `list-completions`            | `audit completions`        |
| `list-skills`                 | `audit skills`             |
| `list-admin-users`            | `admin-users list`         |
| `add-admin-user`              | `admin-users add`          |
| `clear-admin-users`           | `admin-users clear`        |
| `show-room-authz`             | `room-authz show`          |
| `pull-models`                 | `ollama pull`              |

The `serve --add-admin-user` option is unrelated to this rename: it has
been **removed**, and passing it now fails with a non-zero exit pointing
to [`admin-users add`](#admin-users-add). Seed admins out of band with
that subcommand instead.
