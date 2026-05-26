# Soliplex installation multi-database configuration

Uses a soliplex installation config to discover DBURIs for the thread
persistence and authorization databases.

Prefix all `alembic` commands with
`-x soliplex.installation_path=/path/to/installation.yaml`

The following examples presume that we are using the 'example/minimal.yaml'
installation, and that we have defined the 'alx' alias:

```bash
alias alx="alembix -x soliplex.installation_path=example/minimal.yaml"
```

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
