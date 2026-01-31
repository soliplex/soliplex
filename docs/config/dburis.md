# SQLAlchemy DBURI Configuration

Soliplex uses SQLAlchemy to store persistent data in two separate databases:

- One database holds history for AG-UI threads and runs, created by clients
  interacting with its AG-UI endpoints.  See
  [below](#thread_persistence_dburi).

- Another database holds authorization information:  a list of
  administrative users, and a list of room authorization policies and
  the access control list (ACL) entries they contain. See
  [below](#authorization_dburi).

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
  via the [`aiosqlite`]()
  async dialect

- [Postgres](https://docs.sqlalchemy.org/en/20/core/engines.html#postgresql)
  via the [`asyncpg`]()
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

## `thread_persistence_dburi`

Soliplex uses this pair of URLs to record and query information about
AG-UI threads and runs initiated by clients.  If this sections is
not configured, Soliplex uses an in-memory Sqlite database, e.g.:

```yaml
thread_persistence_dburi:
  sync: "sqlite://"
  async: "sqlite+aiosqlite://"
```

To use an on-disk SQLite database for thread persistence (note the four
forward-slashes!):

```yaml
thread_persistence_dburi:
  sync: "sqlite:////path/to/thread_persistence.sqlite"
  async: "sqlite+aiosqlite:////path/to/thread_persistence.sqlite"
```

To use a Postgres server, assuming the login is `"soliplex"` and the
password is defined as a [secret](secrets.md) named `"POSTGRES_PASSWORD"`:

```yaml
thread_persistence_dburi:
  sync: "postgresql://soliplex:secret:POSTGRES_PASSWORD@/soliplex_threads"
  async: "postgresql+asyncpg://soliplex:secret:POSTGRES_PASSWORD@/soliplex_threads"
```

## `authorization_dburi`

Soliplex uses this pair of URLs to record and query authorization information:
a list of administrative users, and a list of room authorization policies
and the access control list (ACL) entries they contain.  If this sections is
not configured, Soliplex uses an in-memory Sqlite database, e.g.:

```yaml
authorization_dburi:
  sync: "sqlite://"
  async: "sqlite+aiosqlite://"
```

To use an on-disk SQLite database for thread persistence (note the four
forward-slashes!):

```yaml
authorization_dburi:
  sync: "sqlite:////path/to/authorization.sqlite"
  async: "sqlite+aiosqlite:////path/to/authorization.sqlite"
```

To use a Postgres server, assuming the login is `"soliplex"` and the
password is defined as a [secret](secrets.md) named `"POSTGRES_PASSWORD"`:

```yaml
authorization_dburi:
  sync: "postgresql://soliplex:secret:POSTGRES_PASSWORD@/soliplex_authorization"
  async: "postgresql+asyncpg://soliplex:secret:POSTGRES_PASSWORD@/soliplex_authorization"
```
