# Database Migrations

Soliplex keeps two SQLAlchemy databases -- one for AG-UI threads and runs,
one for authorization data -- and drives both from a single
[Alembic](https://alembic.sqlalchemy.org/en/latest/) revision tree. Their
DBURIs come from the installation config rather than from Alembic's own
settings (see [SQLAlchemy DBURIs](../config/dburis.md)), so every `alembic`
command has to be told which installation it is working on:

```text
-x soliplex.installation_path=/path/to/installation.yaml
```

The revision tree lives inside the `soliplex` package, at
`src/soliplex/alembic_migrations/`, so it ships in the wheel: soliplex runs
these revisions itself, on every writable open, which is how a database it
creates ends up stamped. A deployment can therefore migrate from its own
image, with no source checkout. `env.py` is a shim over
`soliplex.alembic_migrations`, where that logic and its tests live.

## Migrating a deployment

`soliplex-cli database` drives the same revision tree, out of the
installed package, so it works in a deployment image -- where the
`alembic` CLI does not (see [below](#running-alembic-by-hand)).

A deployment which lets Soliplex migrate for itself needs none of these
commands: the first writable open brings each database to head. They are
for the deployment which has taken that job away from the application
role (see
[`migration_dburi` / `migration_policy`](../config/dburis.md#migrations)),
and for anyone who would rather migrate at a moment of their own choosing
than at the next restart.

### Reporting

```bash
soliplex-cli database status <installation-path>
```

reports, for each of the two databases: the DBURI a migration would use
(with its password masked), the policy in force, the revisions already
applied, and those still pending. Nothing is created, migrated or
stamped. It exits non-zero when a database cannot be migrated as it
stands -- unreachable, unstamped, or stamped by a newer release -- so it
is also the pre-flight for the two commands below.

This is not what `soliplex-cli audit databases` reports. That is one line
per database inside a whole-installation audit, answering "is anything
wrong?"; this answers "what would an upgrade do?".

### Upgrading and downgrading

```bash
soliplex-cli database upgrade <installation-path>
soliplex-cli database upgrade <installation-path> --revision <revision>
soliplex-cli database downgrade <installation-path> <revision>
```

Both databases move in one run, committing together, and the whole run is
refused if any target cannot be moved: `migration_policy: disabled`, a
database which will not open, one which is unstamped, or one stamped by a
release newer than this one. `--database agui` / `--database authz`
narrows a run to one of them, which is what a configuration giving the two
databases different policies needs.

### Emitting SQL instead

```bash
soliplex-cli database upgrade <installation-path> --sql
```

writes `agui.sql` and `authz.sql` into the current directory and runs
nothing, for a deployment whose DDL somebody else applies. Each file
covers that database's own pending range, taken from its stamp, so the
output is the delta rather than a replay from base.

Where the databases cannot be reached from wherever the command runs,
name the range instead and nothing is connected to:

```bash
soliplex-cli database upgrade <path> --sql --revision <from>:head
```

## Running `alembic` by hand

This is mostly a development task -- writing the revision that goes with a
schema change. The examples below presume the `example/minimal.yaml`
installation, and this `alx` alias:

```bash
alias alx="alembic -x soliplex.installation_path=example/minimal.yaml"
```

They also presume a **source checkout**. Alembic reads `script_location`
from `[tool.alembic]` in the project's `pyproject.toml`, which a deployment
image does not carry, so running the `alembic` CLI there reports `No
'script_location' key found in configuration`. That is what
`soliplex-cli database` is for.

## Rolling a version back

Migrating happens on the way *up* only. A database stamped by a newer
Soliplex than the one now running is refused, naming the revision it
carries: this release does not have the revisions between its own head and
that stamp, so it cannot move the database in either direction.

Downgrade before rolling the code back, from the version that still has
those revisions and with every writer stopped:

```bash
soliplex-cli database downgrade <path> <the older release's head revision>
alx downgrade <the older release's head revision>   # from a checkout
```

`soliplex-cli database status` and `soliplex-cli audit databases` both
report the condition, so it surfaces there rather than at the next
restart.

## Cheat Sheet

See the [Alembic docs](https://alembic.sqlalchemy.org/en/latest/) for details.

### Querying

To see the history tree:

```bash
alx history
```

To discover if updates are required from the running schema to match the
current `soliplex` schemae:

```bash
alx check
```

Nothing creates tables on the way in, so `check` compares the models
against the migrated database. A difference means the revisions and the
models disagree: either a revision is missing a change the models make, or
a model changed without one. `scripts/lint_alembic_chain.py` fails CI for
the same reason.

### Snapshotting

To create a new revison if needed:

```bash
alx revision --autogenerate
```

### Upgrading

To run a migration live to a given revision:

```bash
alx upgrade <revision hash>
```

To generate DDL for a migration to a given revision (generates
`agui.sql` and `authz.sql` files in the CWD):

```bash
alx upgrade --sql <revision hash>
```
