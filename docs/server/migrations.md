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

Running `alembic` by hand is mostly a development task -- writing the
revision that goes with a schema change. The examples below presume the
`example/minimal.yaml` installation, and this `alx` alias:

```bash
alias alx="alembic -x soliplex.installation_path=example/minimal.yaml"
```

They also presume a **source checkout**. Alembic reads `script_location`
from `[tool.alembic]` in the project's `pyproject.toml`, which a deployment
image does not carry, so running the `alembic` CLI there reports `No
'script_location' key found in configuration`. A deployed Soliplex migrates
its databases itself, on the first writable open, so there is normally
nothing for an operator to run.

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
