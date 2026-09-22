# SQLAlchemy DBURI Configuration

Soliplex uses SQLAlchemy to store persistent data in two separate databases:

- One database holds history for AG-UI threads and runs, created by clients
  interacting with its AG-UI endpoints.  See
  [below](#thread_persistence_db).

- Another database holds authorization information:  a list of
  administrative users, and a list of room authorization policies and
  the access control list (ACL) entries they contain. See
  [below](#authorization_db).

Configuration for these databases uses SQLAlchemy
[database URLs](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls), in two flavors:

- Synchronous URLs, used by code which is not written to run using
  Python's `async` mechanisms (e.g., the CLI and TUI modules).  This style
  of database URLs is the default described in the SQLAlchemy docs.

- Asynchronous URLs, used by code which *does* use Python's `async`
  mechanisms (e.g., FastAPI endpoint functions).  See this SQLAlchemy
  [page](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
  for details on the extension which adds `async` support to SQLAlchemy.

Because of the requirement for `async` support, Soliplex cannot use
all possible SQLAlchemy engines.  Known to work:

- [SQLite](https://docs.sqlalchemy.org/en/20/core/engines.html#sqlite)
  via the [`aiosqlite`](https://pypi.org/project/aiosqlite/)
  async dialect

- [Postgres](https://docs.sqlalchemy.org/en/20/core/engines.html#postgresql)
  via the [`asyncpg`](https://pypi.org/project/asyncpg/)
  async dialect

Untested:

- [MySQL](https://docs.sqlalchemy.org/en/20/dialects/mysql.html)
  via the [`asyncmy`](https://docs.sqlalchemy.org/en/20/dialects/mysql.html#module-sqlalchemy.dialects.mysql.asyncmy)
  async dialect

- [MySQL](https://docs.sqlalchemy.org/en/20/dialects/mysql.html)
  via the [`aiomysql`](https://docs.sqlalchemy.org/en/20/dialects/mysql.html#aiomysql`)
  async dialect

- [Oracle](https://docs.sqlalchemy.org/en/20/dialects/oracle.html)
  via its built-in async dialect

- [Microsolt SQL Server](https://docs.sqlalchemy.org/en/20/dialects/mssql.html)
  via the [`aioodbc`](https://docs.sqlalchemy.org/en/20/dialects/mssql.html#module-sqlalchemy.dialects.mssql.aioodbc)
  async dialect

## `thread_persistence_db`

Soliplex uses this pair of URLs to record and query information about
AG-UI threads and runs initiated by clients.  If this sections is
not configured, Soliplex uses an in-memory Sqlite database, e.g.:

```yaml
thread_persistence_db:
  sync_dburi: "sqlite://"
  async_dburi: "sqlite+aiosqlite://"
```

To use an on-disk SQLite database for thread persistence (note the four
forward-slashes!):

```yaml
thread_persistence_db:
  sync_dburi: "sqlite:////path/to/thread_persistence.sqlite"
  async_dburi: "sqlite+aiosqlite:////path/to/thread_persistence.sqlite"
```

To use a Postgres server, assuming the login is `"soliplex"` and the
password is defined as a [secret](secrets.md) named `"POSTGRES_PASSWORD"`:

```yaml
thread_persistence_db:
  sync_dburi: "postgresql://soliplex:secret:POSTGRES_PASSWORD@/soliplex_threads"
  async_dburi: "postgresql+asyncpg://soliplex:secret:POSTGRES_PASSWORD@/soliplex_threads"
```

## `authorization_db`

Soliplex uses this pair of URLs to record and query authorization information:
a list of administrative users, and a list of room authorization policies
and the access control list (ACL) entries they contain.  If this sections is
not configured, Soliplex uses an in-memory Sqlite database, e.g.:

```yaml
authorization_db:
  sync_dburi: "sqlite://"
  async_dburi: "sqlite+aiosqlite://"
```

To use an on-disk SQLite database for thread persistence (note the four
forward-slashes!):

```yaml
authorization_db:
  sync_dburi: "sqlite:////path/to/authorization.sqlite"
  async_dburi: "sqlite+aiosqlite:////path/to/authorization.sqlite"
```

To use a Postgres server, assuming the login is `"soliplex"` and the
password is defined as a [secret](secrets.md) named `"POSTGRES_PASSWORD"`:

```yaml
authorization_db:
  sync_dburi: "postgresql://soliplex:secret:POSTGRES_PASSWORD@/soliplex_authorization"
  async_dburi: "postgresql+asyncpg://soliplex:secret:POSTGRES_PASSWORD@/soliplex_authorization"
```

## Migrations

Soliplex keeps both databases at the schema revision its release expects,
and by default does that itself, on the first writable open (see
[Database Migrations](../server/migrations.md)).  That is the right
arrangement when the application role also owns its schema, which is the
case for SQLite and for a default PostgreSQL stack.

It does not work for a deployment which deliberately runs the application
as a least-privilege role -- every object owned by an administrative role,
the application granted only `SELECT, INSERT, UPDATE, DELETE`.  Such a
role is refused `CREATE TABLE` and `ALTER TABLE`, correctly.  Two optional
sub-keys, available on both stanzas, hand the job to somebody else.

### `migration_dburi`

A **synchronous** DBURI naming the role which owns the schema.  Only a
sync URL is needed, because Alembic's online mode is synchronous.

```yaml
authorization_db:
  sync_dburi: "postgresql://soliplex:secret:APP_PASSWORD@/soliplex_authz"
  async_dburi: "postgresql+asyncpg://soliplex:secret:APP_PASSWORD@/soliplex_authz"
  migration_dburi: "postgresql://owner:secret:OWNER_PASSWORD@/soliplex_authz"
```

When it is absent, migrations use `sync_dburi`, which is exactly what
every release before this key existed did.  A SQLite deployment, a
`soliplex-template` stack, or a PostgreSQL deployment which has not
separated owner from application role needs no change and sees no
difference.

Like the other two URLs, it interpolates both `secret:` and `env:`
markers.

### `migration_policy`

Two named values; absence is the third state:

| value | meaning |
| --- | --- |
| absent | migrate automatically, on any writable open |
| `explicit` | only `soliplex-cli database upgrade` migrates |
| `disabled` | nothing migrates this database from this configuration |

Configuring a `migration_dburi` and leaving `migration_policy` unset
implies `explicit`.  That is not merely a convenient default: the
migration tool is the only consumer of that credential, so configuring one
while leaving the automatic path in charge would name a credential nothing
reads.

`disabled` earns its own value rather than folding into `explicit`,
because it is what lets a single `installation.yaml` serve services
running as different roles: the server resolves `disabled`, and whatever
runs the migration resolves `explicit`.  The whole value may be a single
`env:` marker instead of a literal, and Compose already gives each service
its own environment:

```yaml
authorization_db:
  sync_dburi: "postgresql://soliplex:secret:APP_PASSWORD@/soliplex_authz"
  async_dburi: "postgresql+asyncpg://soliplex:secret:APP_PASSWORD@/soliplex_authz"
  migration_dburi: "postgresql://owner:secret:OWNER_PASSWORD@/soliplex_authz"
  migration_policy: "env:SOLIPLEX_MIGRATION_POLICY"
```

Both the ordinary server container and a special-purpose migrations
container read that one stanza, and they differ only in what
`SOLIPLEX_MIGRATION_POLICY` says:

| container | policy resolves to | what it does |
| --- | --- | --- |
| server | `disabled` | runs as `soliplex`, migrates nothing |
| migrations | `explicit` | runs `soliplex-cli database upgrade` as `owner` |

Which is why the stanza names two credentials.  `soliplex` /
`APP_PASSWORD` is the least-privilege role the application runs as,
granted only DML; `owner` / `OWNER_PASSWORD` owns the schema, and nothing
but the migrations container's `soliplex-cli database` invocation ever
connects with it.

A value which is neither policy name is an error, reported when the policy
is read.  Absence means automatic migration, so an unrecognized value must
not fall through to it.

**Not yet enforced at runtime.**  `soliplex-cli database` honors both
values today.  The automatic migration on a writable open does not yet
consult them: a server started against a database which is still behind
head will try to migrate it with the runtime credential, and fail as it
always did, rather than reporting that a migration is owed.  Migrate
before starting it.

## Interpolation

Each of the DBURI values can include values
[interpolated](installation.md#installation-secret-environment-interpolation)
from the installation configuration's environment.  E.g:

```yaml
authorization_db:
  sync_dburi: "postgresql://env:SOLIPLEX_AUTHZ_USER:secret:POSTGRES_PASSWORD@/env:SOLIPLEX_AUTHZ_DBNAME"
  async_dburi: "postgresql+asyncpg://env:SOLIPLEX_AUTHZ_USER:secret:POSTGRES_PASSWORD@/env:SOLIPLEX_AUTHZ_DBNAME"
```

## Deprecated spelling

Through Soliplex v0.81, these two stanzas named the URL flavor as the
sub-key, with the word `dburi` in the stanza name instead:

```yaml
thread_persistence_dburi:
  sync: "<sync dburi>"
  async: "<async dburi>"

authorization_dburi:
  sync: "<sync dburi>"
  async: "<async dburi>"
```

That spelling is still read, but is deprecated and will be removed after
Soliplex v0.84.  Loading a configuration which uses it emits a
`DeprecationWarning` naming the stanza and the configuration file.

The mapping to the current spelling is mechanical:

| Deprecated | Current |
| --- | --- |
| `thread_persistence_dburi` | `thread_persistence_db` |
| `authorization_dburi` | `authorization_db` |
| `sync` | `sync_dburi` |
| `async` | `async_dburi` |

A configuration which somehow sets *both* spellings for the same database
uses the current one, ignoring the deprecated one.

`soliplex-cli config <installation-path>` exports the resolved
configuration using the current spelling, which makes it a convenient way
to derive the replacement text:  `secret:` and `env:` markers within the
DBURIs are exported as written, not resolved, so the exported stanzas can
be pasted back into `installation.yaml`.
