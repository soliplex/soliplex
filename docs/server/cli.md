# `soliplex-cli` Command Reference

## Global Options

These apply to all `soliplex-cli` subcommands:

- `-v` / `--version` — show installed version (plus git tag / branch / hash
  when run from a source checkout) and exit.
- `-h` / `--help` — show help and exit. Note: on the `serve` subcommand the
  short form `-h` is bound to `--host`; use the long form `--help` there.

## A Note on Renamed Commands

Several subcommands were renamed and regrouped in a recent release.
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

- `-h HOST` / `--host HOST` — bind to this host (default: `127.0.0.1`).
  Use `0.0.0.0` to accept connections on any interface.
- `-p PORT` / `--port PORT` — listen on this port (default: `8000`).
- `--uds PATH` — bind to a Unix domain socket instead of a TCP address.
- `--fd INTEGER` — bind to an already-open socket from this file descriptor
  (useful for socket-activated deployments).

### Authentication Options

- `--no-auth-mode` — disable OIDC authentication providers
  (development/testing only). **Never use in production.** Incompatible with
  `--add-admin-user`.
- `--add-admin-user USERNAME` — add `USERNAME` to the authorization
  database as an admin before starting. Incompatible with `--no-auth-mode`.

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

Bootstrap the first admin user on a fresh authz database:

```bash
soliplex-cli serve example/installation.yaml \
  --add-admin-user alice@example.com
```

## `audit`

The `audit` group bundles read-only validation and listing commands —
each one inspects some aspect of an installation configuration without
mutating state. Run `soliplex-cli audit --help` for the full list.

This group replaces the deprecated flat `check-config` / `list-*`
commands; see [Deprecated Command Names](#deprecated-command-names).

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
one of its subcommands (`installation`, `secrets`, `environment`,
`oidc`, `rooms`, `completions`, `skills`), it is treated as the
`INSTALLATION_CONFIG_PATH` argument to `audit installation`. In other
words, the following two invocations are equivalent:

```bash
soliplex-cli audit example/minimal.yaml          # preferred
soliplex-cli audit installation example/minimal.yaml
```

The shorthand is the **preferred spelling** for invoking
`audit installation`. Use the explicit `audit installation` form only
when you need the `SOLIPLEX_INSTALLATION_PATH` env-var fallback (the
shorthand requires a positional argument; with no positional,
`soliplex-cli audit` prints group help instead).

### `audit installation`

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
soliplex-cli audit [OPTIONS] installation [INSTALLATION_CONFIG_PATH]
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

The command runs the following validation passes in order, printing a
section header and an `OK` / error summary for each:

1. **Secrets** — every secret declared in the installation resolves via
   its configured sources.
2. **Environment** — every environment variable required by the
   installation is either configured in the YAML or present in the OS
   environment.
3. **Installation model** — the top-level installation config converts
   cleanly to its runtime model.
4. **OIDC authentication systems** — each configured OIDC provider
   converts cleanly to its runtime model.
5. **Rooms** — each room converts cleanly to its runtime model. For
   rooms (and their skills / tools) that use RAG, the referenced
   LanceDB path is also resolved.
6. **Completions** — each completion endpoint converts cleanly to its
   runtime model.
7. **Quizzes** — every `*.json` question file under each configured
   quizzes path loads and parses.
8. **Python logging** — if a `logging_config_file` is configured, it
   parses as YAML and the logging headers / claims maps are printed.
9. **Skills** — every skill found under each configured filesystem
   skills path passes `skills_ref` validation.
10. **Logfire** — the Logfire config (if any) is printed for review.

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

Use the env-var form instead of a positional argument (the canonical
`audit installation` spelling is required here, since the shorthand
needs a positional path):

```bash
export SOLIPLEX_INSTALLATION_PATH=example/minimal.yaml
soliplex-cli audit installation
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
their names, descriptions, and any RAG databases they reference
(including a live document count for each). (Replaces the deprecated
`soliplex-cli list-rooms`.)

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

   Haiku Rag DBs
   - <source>              : <db_path>                     <N> documents
```

`<source>` identifies where the RAG database reference came from within
the room (for example the agent, a named skill, or a named tool);
`<db_path>` is shown relative to the current working directory.

Rooms with no RAG configuration omit the "Haiku Rag DBs" block. If a
configured RAG database file cannot be located, an `Invalid Haiku Rag
configs` line is printed in place of the document listing. If a
particular database is present but the document count query fails, the
count column is shown as `error` rather than a number.

#### Behavior Notes

- **Bypasses authorization.** This command deliberately lists every room
  configured in the installation, regardless of which rooms any given
  user would be authorized to see via the normal `get_room_configs`
  path. It reflects configuration, not per-user visibility.
- **Tolerant of missing environment variables.** Unresolved entries do
  not abort the listing — use `audit installation` (or
  `audit environment`) to validate the environment separately.
- **Opens each RAG database.** The document count is obtained by
  opening the LanceDB at each configured `db_path` and issuing a
  `count_documents` query. Expect the command to be slower than the
  other `audit` subcommands when many rooms have large RAG databases,
  and to require read access to those files.
- **Paths are `cwd`-relative.** The `<db_path>` column depends on where
  you run the command from; two invocations from different directories
  may show different-looking (but equivalent) paths.

#### Exit Status

- `0` — every room's RAG configuration resolved and every document
  count completed.
- `1` — at least one room had a missing RAG file (`Invalid Haiku Rag
  configs`) or a failing `count_documents` query. In `--quiet` mode,
  the per-room errors are printed as JSON on stdout before exit.

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

For each completion endpoint declared in the installation, one line is
printed of the form:

```text
- [ <completion_id> ] <name>:
```

`<completion_id>` is the key Soliplex uses internally to refer to the
endpoint; `<name>` is the human-readable label. Descriptions, model
bindings, and authorization rules are not shown — use
`audit installation` (or read the YAML directly) to inspect those. If
the completion fails runtime-model validation, an `ERROR: <message>`
line is appended to its entry.

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

### `audit skills`

List the Haiku skills declared in the installation configuration,
showing each skill's kind, identifier, and description — or the
validation errors produced while loading it. (Replaces the deprecated
`soliplex-cli list-skills`.)

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

For each skill declared in the installation, an entry is printed of the
form:

```text
- [ <kind>:<skill_name>  ]
  <description>
```

`<kind>` names the skill source type (e.g., the mechanism used to
discover or load it); `<skill_name>` is the identifier Soliplex uses
internally.

If a skill failed validation at load time, its description is replaced
by a list of errors:

```text
- [ <kind>:<skill_name>  ]
  Validation errors:
  - <first error message>
  - <second error message>
```

#### Behavior Notes

- **Validation surface is the configured skill list.** This command
  reports the validation errors recorded on each `skill_config` at load
  time. For deeper checks (every skill found under each configured
  filesystem skills path, run through the full `skills_ref` validator),
  use `audit installation`.

#### Exit Status

- `0` — every declared skill loaded without validation errors.
- `1` — at least one skill recorded one or more validation errors. In
  `--quiet` mode, the per-skill error lists are printed as JSON on
  stdout before exit.

#### Examples

List skills for the full installation example:

```bash
soliplex-cli audit skills example/installation.yaml
```

Audit a directory-style installation:

```bash
soliplex-cli audit skills example/
```

## `admin-users`

The `admin-users` group manages the installation's admin-user table.
Admin users are entries in the installation's authorization database,
keyed by email address. A user whose OIDC-authenticated email matches
an entry in this table is granted administrator privileges by the
Soliplex authorization policy engine. The subcommands below read from
and modify that table directly.

This group replaces the deprecated flat `list-admin-users` /
`add-admin-user` / `clear-admin-users` commands; see
[Deprecated Command Names](#deprecated-command-names).

All three subcommands share one safety behavior: they only make sense
against a *persistent* authorization database (configured via
`authorization_dburi` in the installation YAML). When the installation
uses the default in-memory SQLite DB (`sqlite://`), the commands
detect the RAM-based URI, print a note that the operation would be a
no-op, and exit. Pass `-s` / `--skip-ram-db-check` to override the
guard — useful mostly for tests and smoke-diagnostics against a
throwaway installation.

All three commands share the following conventions:

- Positional argument `INSTALLATION_CONFIG_PATH` — path to the
  installation configuration. May be a YAML file or a directory
  containing an `installation.yaml`. If omitted, falls back to the
  `SOLIPLEX_INSTALLATION_PATH` environment variable.
- Option `-s` / `--skip-ram-db-check` — bypass the RAM-DB guard
  described above. The command will still exit immediately if the
  DBURI does not actually point to a writable database, but the
  no-op guard is skipped.
- On completion, the current admin-user list is printed as a single
  JSON object on stdout:

  ```json
  {"admin_users": ["alice@example.com", "bob@example.com"]}
  ```

  Emitted via plain `print(...)` (not Rich), so the output pipes
  cleanly into `jq` or other tooling.
- Exit status is always `0`, including when the RAM-DB guard fires.

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

Insert a new admin-user row into the installation's authorization
database and then dump the resulting list. (Replaces the deprecated
`soliplex-cli add-admin-user`.)

```bash
soliplex-cli admin-users add [OPTIONS] INSTALLATION_CONFIG_PATH EMAIL
```

#### Positional Arguments

- `INSTALLATION_CONFIG_PATH` — as described above.
- `EMAIL` — the email address to grant admin privileges. This is the
  value Soliplex will match against the authenticated user's
  OIDC-asserted email; no format validation is performed by the CLI.

#### Behavior Notes

- **No deduplication.** The command inserts a row unconditionally; if
  the same email is added twice, two rows are created (whether that
  is rejected or quietly tolerated depends on the schema of the
  authorization table you have configured). Use `admin-users list`
  first if you need to check for an existing entry.
- **Compare with `serve --add-admin-user`.** The `serve` subcommand's
  `--add-admin-user` option bootstraps a single admin during startup
  and is incompatible with `--no-auth-mode`. The standalone
  `admin-users add` subcommand is for offline / ongoing administration
  and has no such interaction with `--no-auth-mode`.

#### Examples

Grant admin privileges to a new operator:

```bash
soliplex-cli admin-users add example/installation.yaml alice@example.com
```

Add an admin against an ephemeral RAM database (will only last for the
lifetime of the command; mostly useful for tests):

```bash
soliplex-cli admin-users add --skip-ram-db-check \
  example/minimal.yaml alice@example.com
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

This group replaces the deprecated flat `show-room-authz` /
`add-room-user` / `clear-room-authz` commands; see
[Deprecated Command Names](#deprecated-command-names).

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

The three commands below create, inspect, populate, and delete these
rows.

### Shared Conventions

All three commands share the following:

- Positional argument `INSTALLATION_CONFIG_PATH` — as documented in the
  [`admin-users`](#admin-users) section. If omitted, falls back to
  `SOLIPLEX_INSTALLATION_PATH`.
- Positional argument `ROOM_ID` — the `id` of a configured room (the
  same identifier surfaced by `audit rooms`). The commands do **not**
  validate that `ROOM_ID` matches any currently-configured room; you
  can create or inspect a policy for a room that doesn't exist in the
  YAML, and that policy will continue to sit in the DB until you clear
  it.
- Option `-s` / `--skip-ram-db-check` — bypass the RAM-DB guard
  described under [`admin-users`](#admin-users). When the installation's
  `authorization_dburi` is the in-memory default (`sqlite://`), the
  commands treat themselves as a no-op and exit; pass this flag to
  force them to proceed anyway (useful for tests).
- On completion, the resulting `RoomPolicy` is dumped as a single JSON
  object on stdout (emitted via plain `print(...)`, not Rich). If no
  policy row exists for the room, `null` is printed instead.

  Example output:

  ```json
  {
    "room_id": "chat",
    "default_allow_deny": "AllowDeny.DENY",
    "acl_entries": [
      {
        "allow_deny": "AllowDeny.ALLOW",
        "everyone": false,
        "authenticated": false,
        "preferred_username": null,
        "email": "alice@example.com"
      }
    ]
  }
  ```

- Exit status is always `0`, including when the RAM-DB guard fires and
  when no policy row exists for the room.

### `room-authz show`

Dump the current `RoomPolicy` for a single room without changing it.
(Replaces the deprecated `soliplex-cli show-room-authz`.)

```bash
soliplex-cli room-authz show [OPTIONS] INSTALLATION_CONFIG_PATH ROOM_ID
```

#### Examples

Inspect the policy for the `chat` room:

```bash
soliplex-cli room-authz show example/installation.yaml chat
```

Extract just the list of allowed emails with `jq`:

```bash
soliplex-cli room-authz show example/installation.yaml chat \
  | jq -r '.acl_entries[] | select(.allow_deny == "AllowDeny.ALLOW") | .email'
```

A `null` response means no `RoomPolicy` row exists yet — i.e. the room
is in its default public state:

```bash
$ soliplex-cli room-authz show example/installation.yaml search
null
```

### `room-authz add-user`

Grant a single user access to a room by inserting an `ALLOW`-by-`email`
ACL entry. If no `RoomPolicy` exists for the room yet, one is created
with the default `default_allow_deny=DENY` — so **the first call to
`room-authz add-user` against a previously-public room flips the room
from "public to all authenticated users" to "private except for this
one user."** Plan accordingly. (Replaces the deprecated
`soliplex-cli add-room-user`.)

```bash
soliplex-cli room-authz add-user [OPTIONS] INSTALLATION_CONFIG_PATH ROOM_ID EMAIL
```

#### Positional Arguments

- `INSTALLATION_CONFIG_PATH` — as described above.
- `ROOM_ID` — as described above.
- `EMAIL` — the email address to grant access. Matched against the
  authenticated user's OIDC-asserted email at request time.

#### Behavior Notes

- **Idempotent per email.** Any existing ACL entries for the same email
  on this room (including `DENY` entries) are deleted before the new
  `ALLOW` entry is inserted. Running the command twice with the same
  email leaves exactly one row.
- **ALLOW + email only.** The CLI offers no way to create a `DENY`
  entry, an `everyone` / `authenticated` entry, or an entry keyed by
  `preferred_username`. For those, use your database tooling or edit
  the installation's authorization seed YAML.
- **Policy creation side effect.** As noted above, the first call may
  silently convert a public room to a private-with-one-exception room.
  Run `room-authz show` beforehand if you're uncertain of the current
  state.

#### Examples

Grant Alice access to the `chat` room:

```bash
soliplex-cli room-authz add-user example/installation.yaml chat alice@example.com
```

Re-run with the same email to confirm idempotence (exactly one ACL
entry for `alice@example.com` remains):

```bash
soliplex-cli room-authz add-user example/installation.yaml chat alice@example.com
```

### `room-authz clear`

Delete the `RoomPolicy` row for a single room (cascades to all of its
`ACLEntry` rows). By default this returns the room to the
**public-to-all-authenticated-users** state; pass `--make-room-private`
to replace the deleted policy with a fresh empty one, which leaves the
room **closed to everyone**. (Replaces the deprecated
`soliplex-cli clear-room-authz`.)

```bash
soliplex-cli room-authz clear [OPTIONS] INSTALLATION_CONFIG_PATH ROOM_ID
```

#### Options

- `--make-room-private` — after deleting the existing policy, create a
  new empty `RoomPolicy` (no ACL entries, default `DENY`) so that the
  room remains inaccessible until new ACL entries are added. Without
  this flag, the command deletes the policy outright and the room
  reverts to its default **public** state.
- `-s` / `--skip-ram-db-check` — see the shared conventions above.

#### Behavior Notes

- **Destructive and unconditional.** There is no per-email filter and
  no confirmation prompt. If you have five users allowed and only want
  to revoke one, clearing and re-running `room-authz add-user` for the
  other four is the only route through this CLI.
- **`--make-room-private` is not a synonym for "deny everyone".** It
  works by relying on `default_allow_deny=DENY` on the new empty
  policy, matching the current database default. If a future schema
  change alters that default, `--make-room-private` will follow the
  new default rather than hard-coding `DENY`.

#### Examples

Open the `search` room back up to all authenticated users:

```bash
soliplex-cli room-authz clear example/installation.yaml search
```

Wipe the ACL on the `chat` room and lock it down completely:

```bash
soliplex-cli room-authz clear --make-room-private \
  example/installation.yaml chat
```

Clear-and-seed — start from a clean private state, then allow one user
in:

```bash
soliplex-cli room-authz clear --make-room-private \
  example/installation.yaml chat
soliplex-cli room-authz add-user example/installation.yaml chat alice@example.com
```

## `ollama`

The `ollama` group bundles subcommands that interact with Ollama servers
referenced by the installation. Currently a single subcommand,
`ollama pull`.

This group replaces the deprecated flat `pull-models` command; see
[Deprecated Command Names](#deprecated-command-names).

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

- `-u URL` / `--ollama-url URL` — restrict the scan to a single Ollama
  base URL. If omitted, the command pulls models on *every* Ollama URL
  referenced by the installation (installations may point different
  rooms at different Ollama instances). Defaults to the
  `OLLAMA_BASE_URL` value in the installation's resolved environment.
- `-n` / `--dry-run` — scan the installation and print the model list
  per URL without actually pulling. Useful for verifying what *would*
  happen before committing to potentially slow downloads.

#### Behavior

For each Ollama URL in scope, the command:

1. Reports the URL and the count of distinct models the installation
   references at it.
2. Lists the model names in sorted order.
3. Unless `--dry-run` is set, pulls each model via Ollama's REST API
   (`stream=False` — each pull blocks until complete, so no per-chunk
   progress is shown) and prints the final status line returned by
   Ollama for each model.
4. Prints a summary in the form
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
  total, but do not abort the overall command. Other models on the
  same URL will still be pulled.
- **`--ollama-url` filters, it doesn't inject.** If you pass a URL that
  the installation doesn't reference, the scan finds an empty model
  set for it and reports "No Ollama models for URL" — the command
  won't pull arbitrary models to arbitrary servers.
- **Non-Ollama providers are ignored.** Models bound to OpenAI, Gemini,
  or any other non-Ollama provider are not considered here; this
  command deals strictly with the local-model case.

#### Exit Status

- Always `0`, even when some pulls failed. Check the printed summary
  (`Pulled X/N …`) to detect partial failure. Use `audit installation`
  if you need a non-zero exit for configuration problems before
  pulling.

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

- Always `0`. Use `audit installation` if you need a non-zero exit on
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
| `check-config`                | `audit` (or `audit installation`) |
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
| `add-room-user`               | `room-authz add-user`      |
| `clear-room-authz`            | `room-authz clear`         |
| `pull-models`                 | `ollama pull`              |

The `serve --add-admin-user` option on the `serve` subcommand is **not**
affected by this rename: it remains spelled `--add-admin-user` and is
distinct from the standalone `admin-users add` subcommand (see the note
under [`admin-users add`](#admin-users-add)).
