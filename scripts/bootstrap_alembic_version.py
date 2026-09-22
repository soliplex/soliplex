#!/usr/bin/env python
# /// script
# requires-python = ">=3.12"
# dependencies = ["sqlalchemy >= 2.0, < 3", "psycopg[binary]"]
# ///
r"""Stamp missing ``alembic_version`` into existing ``soliplex`` databases.

See https://github.com/soliplex/soliplex/issues/1367.

Rationale
---------

When a ``soliplex`` server starts for the first time, it builds the
deployment's ``agui`` and ``authz`` databases (in
``soliplex.installation.lifespan``) using ``Base.metadata.create_all``.

For ``soliplex <= 0.81``, the ``lifespan`` function does not write an
``alembic_version`` row: such databases are schema-current but *unstamped*.

When invoked to upgrade a database without its ``alembic_version`` row,
Alembic concludes that the database is empty, and tries to replay from base,
failing: the baseline revision creates tables that already exist.

This script detects the correct Alembic revision stamp by fingerprinting
the live schema for both databases: the result is the newest Alembic revision
whose changes are already present in both databases.

This script writes the missing ``alembic_version`` row into each database,
and nothing else. It applies no migrations and never touches an application
table.

Run this script by hand, once per deployment, before upgrading to a newer
soliplex version: it is not part of the ordinary upgrade path.

Checking whether your databases need bootstrapping
--------------------------------------------------

Use the ``--dry-run`` flag to test first, always::

  # inside the deployment's own image (resolves both DBURIs from the
  # installation config -- the migration ones where configured -- using
  # the soliplex that is installed there)
  python scripts/bootstrap_alembic_version.py \
      --installation-path /environment --dry-run

  # or from a host, importing no soliplex at all
  uv run scripts/bootstrap_alembic_version.py \
      --agui-dburi postgresql+psycopg://user:pw@host/soliplex_agui \
      --authz-dburi postgresql+psycopg://user:pw@host/soliplex_authz \
      --dry-run

Running the bootstrap
---------------------

If the ``--dry-run`` report shows that the stamps are missing:

- Make a backup of each database first.

- Run the same command without the ``--dry-run`` flag to apply the stamp.

- Confirm if desired using::

    soliplex-cli database status <installation-path>

Checking the fingerprinting
---------------------------

Running the script with just its ``--self-test`` flag iterates over
the past version ranges where schema changes were applied, rebuilding the
two databases from that release's own models, with its own era-correct
dependencies.  It then re-checks that the fingerprint this script detects
matches the revision recorded for it.

The ``--self-test`` flag prints each command it runs, so the whole thing
can be repeated by hand. It touches no database of yours, needs ``uv`` and
network access, and exits non-zero on any mismatch::

  uv run scripts/bootstrap_alembic_version.py --self-test

It proves the release-to-revision mapping. It does *not* run the migrations
afterwards -- that needs a soliplex checkout, and the procedure is in the
issue above.

Prerequisites
-------------

Both modes use a **sync** DBURI, so a sync driver has to be importable;
the PEP 723 dependencies above cover PostgreSQL and SQLite when invoked via
``uv run``.

Stamping writes ``CREATE TABLE alembic_version``. Where a deployment has
given the schema to an administrative role, that DDL is refused to the
application role, so ``--installation-path`` uses each stanza's
``migration_dburi`` when one is configured, falling back to its
``sync_dburi``. Passing ``--agui-dburi`` / ``--authz-dburi`` names the
credential directly, and is the mode to use when soliplex is not importable
at all.

Finding your databases
----------------------

A relative SQLite URI resolves against the current directory, so either
run from the installation's working directory or pass absolute URIs.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

import sqlalchemy as sa

SCRIPT = pathlib.Path(__file__).resolve()

AGUI = "agui"
AUTHZ = "authz"
DATABASES = (AGUI, AUTHZ)

# Alembic's own version table, as built by 'alembic.ddl.impl.DefaultImpl.
# version_table_impl': one 32-character column, primary key named for the
# table. Reproduced rather than imported so the script does not depend on
# alembic being installed.
VERSION_TABLE = "alembic_version"


@dataclasses.dataclass(frozen=True)
class Fingerprint:
    """A revision, and the schema change that proves it was applied.

    ``column`` is the column the revision added, or ``None`` when the
    revision created ``table`` outright. ``absent`` names columns the
    revision *dropped*, which must therefore be gone.

    ``release`` is the release whose models first produced this shape --
    what ``--release`` has to answer -- and not necessarily the release
    that shipped the migration. The two diverge in both directions: the
    ``review_history`` model arrived a patch release before its migration,
    while ``a1c7d3e90b42`` is named for 0.80 but shipped in 0.81.
    """

    revision: str
    release: str
    database: str
    table: str
    column: str | None = None
    absent: tuple[str, ...] = ()

    @property
    def location(self) -> str:
        if self.column is None:
            return f"{self.database}.{self.table}"
        return f"{self.database}.{self.table}.{self.column}"

    @property
    def release_key(self) -> tuple[int, ...]:
        return parse_release(self.release)

    def __str__(self) -> str:
        return f"{self.revision} (soliplex v{self.release})"


# Newest first. The two databases share one linear revision history, so the
# stamp is a single revision id written to both; a revision that touches only
# one of them is only observable there.
FINGERPRINTS = (
    #
    # This Alembic revision was released in 0.81, despite having
    # 'soliplex_v0_80' in its filename (uncorrected when the PR merged).
    # The release recorded here # is the one that shipped it, since that is
    # what '--release' answers.
    #
    Fingerprint(
        "a1c7d3e90b42", "0.81", AGUI, "run_usage", "final_input_tokens"
    ),
    #
    # This revision *migrated* existing 'email'/'preferred_username' columns
    # to their equivalent 'json_path' expressions, dropping both.
    #
    Fingerprint(
        "63edaa5987f6",
        "0.67",
        AUTHZ,
        "room_acl_entries",
        "json_path",
        absent=("email", "preferred_username"),
    ),
    Fingerprint("216d48e1e2e5", "0.53", AGUI, "thread", "email"),
    #
    # Recorded as 0.51. Although the Alembic revision shipped in 0.51.1,
    # the # 'review_history' *model* landed in 0.51, so 'create_all' in a
    # 0.51 # deployment already made the table.
    #
    Fingerprint("4b63e5f3f39e", "0.51", AGUI, "review_history"),
    #
    # First soliplex version containing '{agui,authz}.schema' modules.
    # Any existing database created from an earlier version needs
    # by-hand migration to match the '0.44' schema.
    #
    Fingerprint("d5009d4f9874", "0.44", AGUI, "thread"),
)
# The baseline: its fingerprint failing means there is no schema at all.
BASELINE = FINGERPRINTS[-1]


class BootstrapError(Exception):
    """A user-facing error (reported without a traceback)."""


class NoDatabasesGiven(BootstrapError):
    def __init__(self):
        super().__init__(
            "need --installation-path, or both --agui-dburi and --authz-dburi"
        )


class InstallationUnavailable(BootstrapError):
    def __init__(self, exc):
        self.exc = exc
        super().__init__(
            f"cannot resolve the installation config ({exc}); pass "
            "--agui-dburi and --authz-dburi instead, which import no soliplex"
        )


class AlreadyStamped(BootstrapError):
    def __init__(self, stamped):
        self.stamped = stamped
        found = ", ".join(
            f"{name} at {', '.join(rows)}"
            for name, rows in sorted(stamped.items())
        )
        super().__init__(
            f"{VERSION_TABLE} already carries a revision ({found}); this "
            "database has been bootstrapped already -- upgrade it with "
            "'alembic upgrade head' instead"
        )


class SchemaAbsent(BootstrapError):
    def __init__(self):
        super().__init__(
            f"no soliplex schema found ({BASELINE.location} is missing), so "
            "there is nothing to bootstrap: an empty database gets its "
            "version row from the migrations themselves"
        )


class InconsistentSchema(BootstrapError):
    def __init__(self, newest, missing):
        self.newest = newest
        self.missing = missing
        gaps = ", ".join(f"{fp} at {fp.location}" for fp in missing)
        super().__init__(
            f"schema looks like {newest}, but changes from earlier "
            f"revisions are missing ({gaps}); the two databases may be at "
            "different revisions -- inspect them and pass --revision"
        )


class UnknownRelease(BootstrapError):
    def __init__(self, release):
        self.release = release
        known = ", ".join(fp.release for fp in reversed(FINGERPRINTS))
        super().__init__(
            f"no revision for release {release!r}; releases that changed the "
            f"schema are: {known}"
        )


class BadRelease(BootstrapError):
    def __init__(self, release):
        self.release = release
        super().__init__(
            f"cannot parse release {release!r}; use a dotted version such "
            "as 0.79"
        )


def parse_release(release: str) -> tuple[int, ...]:
    """``"0.51.1"`` -> ``(0, 51, 1)``, for ordering releases."""
    try:
        return tuple(int(part) for part in release.split("."))
    except ValueError as exc:
        raise BadRelease(release) from exc


def version_table() -> sa.Table:
    """Alembic's version table, defined exactly as alembic defines it."""
    return sa.Table(
        VERSION_TABLE,
        sa.MetaData(),
        sa.Column("version_num", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("version_num", name=f"{VERSION_TABLE}_pkc"),
    )


def redacted(dburi: str) -> str:
    """The URI with its password masked, safe to print."""
    return sa.engine.make_url(dburi).render_as_string(hide_password=True)


def satisfied(inspectors: dict, fingerprint: Fingerprint) -> bool:
    """True when ``fingerprint``'s revision has been applied."""
    inspector = inspectors[fingerprint.database]
    if not inspector.has_table(fingerprint.table):
        return False
    if fingerprint.column is None and not fingerprint.absent:
        return True
    columns = {
        column["name"] for column in inspector.get_columns(fingerprint.table)
    }
    if fingerprint.column is not None and fingerprint.column not in columns:
        return False
    return not (columns & set(fingerprint.absent))


def detect(inspectors: dict) -> Fingerprint:
    """The newest revision the live schema shows evidence of.

    Raises :class:`SchemaAbsent` when there is no schema, and
    :class:`InconsistentSchema` when an *older* revision's changes are
    missing -- impossible in a linear history, and the shape a pair of
    databases at different revisions takes.
    """
    if not satisfied(inspectors, BASELINE):
        raise SchemaAbsent()

    newest, rest = None, []
    for fingerprint in FINGERPRINTS:
        if newest is None:
            if satisfied(inspectors, fingerprint):
                newest = fingerprint
            continue
        rest.append(fingerprint)

    missing = [fp for fp in rest if not satisfied(inspectors, fp)]
    if missing:
        raise InconsistentSchema(newest, missing)
    return newest


def for_release(release: str) -> Fingerprint:
    """The newest revision introduced at or before ``release``."""
    wanted = parse_release(release)
    for fingerprint in FINGERPRINTS:
        if fingerprint.release_key <= wanted:
            return fingerprint
    raise UnknownRelease(release)


def installation_dburis(installation_path: pathlib.Path) -> dict[str, str]:
    """The DBURI to stamp each database through, read via the installed
    soliplex.

    Each is the stanza's ``migration_dburi`` where one is configured, and
    its runtime ``sync_dburi`` where none is. Stamping writes ``CREATE
    TABLE alembic_version``, which an application role granted only DML is
    refused.

    ``installation_path`` may be the YAML file or the directory holding
    it. Only the installation config is loaded, not the rooms, completions
    or OIDC beside it, so an unrelated broken config cannot block a
    bootstrap.
    """
    try:
        from soliplex import alembic_migrations
    except ImportError as exc:  # pragma: no cover - depends on the host
        raise InstallationUnavailable(exc) from exc

    try:
        i_config = alembic_migrations.load_installation_config(
            installation_path
        )
    except Exception as exc:
        raise InstallationUnavailable(exc) from exc

    return alembic_migrations.migration_dburis(i_config)


def resolve_dburis(args: argparse.Namespace) -> dict[str, str]:
    """The two DBURIs to stamp through, from flags or the installation."""
    explicit = {AGUI: args.agui_dburi, AUTHZ: args.authz_dburi}
    if all(explicit.values()):
        return explicit
    if args.installation_path is None:
        raise NoDatabasesGiven()

    dburis = installation_dburis(args.installation_path)
    # Explicit flags win, so one database can be overridden while the other
    # still comes from the config.
    return {name: explicit[name] or dburis[name] for name in DATABASES}


def version_rows(engines: dict, inspectors: dict) -> dict:
    """Per database: the version rows, or ``None`` when there is no table.

    An existing table with *no* rows is not a stamp. Alembic creates the
    version table before it runs any migration, so an upgrade that failed
    part-way -- which is what an unstamped database does -- leaves an empty
    one behind. Such a table is a leftover to fill in, not a baseline.
    """
    rows = {}
    for name in DATABASES:
        if not inspectors[name].has_table(VERSION_TABLE):
            rows[name] = None
            continue
        with engines[name].connect() as connection:
            found = connection.execute(
                sa.select(version_table().c.version_num)
            ).scalars()
            rows[name] = list(found)
    return rows


def stamp(engine, revision: str) -> None:
    """Create the version table and write ``revision`` into it."""
    table = version_table()
    with engine.begin() as connection:
        table.create(connection, checkfirst=True)
        connection.execute(sa.insert(table).values(version_num=revision))


@dataclasses.dataclass(frozen=True)
class SelfTestCase:
    """One release to rebuild, and the stamp its schema should produce."""

    release: str
    uploaded: str
    expected: str


# Every release below was checked by hand when this script was written; the
# self-test re-checks them from scratch. 'uploaded' is the release's PyPI
# upload date, which pins dependency resolution to that era -- resolving a
# 2026-02 soliplex against today's transitive dependencies fails to import.
SELF_TEST_CASES = (
    #
    # Range for initial '{agui,authz}.schema' models
    #
    SelfTestCase("0.44", "2026-02-23", "d5009d4f9874"),
    SelfTestCase("0.50", "2026-03-16", "d5009d4f9874"),
    #
    # Range for models including the 'agui.review_history' table.
    #
    # Includes extra testcases because of the confusion between
    # the revision's filename and the actual soliplex release with the
    # equivalent model.
    #
    SelfTestCase("0.51", "2026-03-18", "4b63e5f3f39e"),
    SelfTestCase("0.51.1", "2026-03-18", "4b63e5f3f39e"),
    SelfTestCase("0.51.2", "2026-03-18", "4b63e5f3f39e"),
    SelfTestCase("0.52", "2026-03-22", "4b63e5f3f39e"),
    #
    # Range for models including the 'agui.thread.email' column
    #
    SelfTestCase("0.53", "2026-03-23", "216d48e1e2e5"),
    SelfTestCase("0.66", "2026-05-19", "216d48e1e2e5"),
    SelfTestCase("0.66.2", "2026-05-27", "216d48e1e2e5"),
    #
    # Range for models migrating
    # 'authz.room_acl_entries.{email,preferred_username}' to the equivalent
    # 'json_path' expressions.
    #
    SelfTestCase("0.67", "2026-05-27", "63edaa5987f6"),
    SelfTestCase("0.80", "2026-09-15", "63edaa5987f6"),
    #
    # Last soliplex release lacking 'alembic_version' stamps on creation.
    #
    SelfTestCase("0.81", "2026-09-15", "a1c7d3e90b42"),
)

# Run inside the per-release environment: build the two schemas exactly the
# way a server of that release does, from its own models.
SELF_TEST_SNIPPET = """\
import sys

import sqlalchemy as sa

from soliplex.agui import schema as agui_schema
from soliplex.authz import schema as authz_schema

for module, path in ((agui_schema, sys.argv[1]), (authz_schema, sys.argv[2])):
    engine = sa.create_engine("sqlite:///" + path)
    module.Base.metadata.create_all(engine)
    engine.dispose()
    print(f"created {path}")
"""

_REVISION_LINE = re.compile(r"^revision: ([0-9a-f]+) ")


def _built_or_failed(line: str) -> bool:
    """Lines worth showing from a per-release schema build."""
    return line.startswith("created ") or "rror" in line


def _revision_or_failed(line: str) -> bool:
    """Lines worth showing from one of this script's own dry runs."""
    return line.startswith("revision: ") or "error:" in line


class SelfTestNeedsUv(BootstrapError):
    def __init__(self):
        super().__init__(
            "--self-test needs 'uv' on PATH and network access: it installs "
            "each past soliplex release to rebuild that release's schema"
        )


def shown(argv: list[str], keep=None) -> subprocess.CompletedProcess:
    """Run ``argv`` after printing it, then print the lines that matter.

    Printing the command first is the point: every step of the self-test is
    one an operator can copy, paste, and check independently.
    """
    print(f"  $ {shlex.join(argv)}")
    result = subprocess.run(argv, capture_output=True, text=True)
    lines = (result.stdout + result.stderr).splitlines()
    for line in lines:
        if keep is None or keep(line):
            print(f"  | {line}")
    if result.returncode != 0 and keep is not None:
        print(f"  | (exit {result.returncode})")
    return result


def revision_from(result: subprocess.CompletedProcess) -> str:
    """The revision a ``--dry-run`` reported, or ``"-"``."""
    for line in result.stdout.splitlines():
        found = _REVISION_LINE.match(line)
        if found:
            return found.group(1)
    return "-"


def ascii_table(headers, rows) -> str:
    """The results as a plain-ASCII table."""
    widths = [
        max(len(str(row[i])) for row in (headers, *rows))
        for i in range(len(headers))
    ]
    rule = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def line(cells):
        body = " | ".join(
            str(cell).ljust(w) for cell, w in zip(cells, widths, strict=True)
        )
        return f"| {body} |"

    return "\n".join(
        [rule, line(headers), rule, *(line(row) for row in rows), rule]
    )


def self_test_case(case: SelfTestCase, workdir: pathlib.Path) -> tuple:
    """Rebuild one release's schema and ask this script what it sees."""
    print(f"--- soliplex {case.release} (expecting {case.expected})")
    agui_db = workdir / "agui.sqlite"
    authz_db = workdir / "authz.sqlite"

    created = shown(
        [
            "uv",
            "run",
            "--no-project",
            "--quiet",
            "--with",
            f"soliplex=={case.release}",
            "--exclude-newer",
            f"{case.uploaded}T23:59:59Z",
            "python",
            "-c",
            SELF_TEST_SNIPPET,
            str(agui_db),
            str(authz_db),
        ],
        keep=_built_or_failed,
    )
    if created.returncode != 0:
        return "-", "-", "build failed"

    dburis = [
        "--agui-dburi",
        f"sqlite:///{agui_db}",
        "--authz-dburi",
        f"sqlite:///{authz_db}",
    ]
    detected = revision_from(
        shown(
            [sys.executable, str(SCRIPT), *dburis, "--dry-run"],
            keep=_revision_or_failed,
        )
    )
    released = revision_from(
        shown(
            [
                sys.executable,
                str(SCRIPT),
                *dburis,
                "--release",
                case.release,
                "--dry-run",
            ],
            keep=_revision_or_failed,
        )
    )
    ok = detected == case.expected == released
    return detected, released, "ok" if ok else "MISMATCH"


def self_test() -> int:
    """Rebuild each past release's schema and re-check the mapping.

    Proves that what this script detects (and what ``--release`` answers)
    matches the recorded stamp for every release below. It does *not* run
    the migrations afterwards -- that needs a soliplex checkout, and the
    procedure is in the issue this script came with.
    """
    if shutil.which("uv") is None:
        raise SelfTestNeedsUv()

    print(f"Self-test: {len(SELF_TEST_CASES)} releases, each schema built")
    print("from that release's own models. Commands are shown so they can")
    print("be re-run by hand; each takes a moment to install.")
    print()

    rows = []
    for case in SELF_TEST_CASES:
        with tempfile.TemporaryDirectory(prefix="bootstrap-selftest-") as td:
            detected, released, result = self_test_case(case, pathlib.Path(td))
        rows.append([case.release, case.expected, detected, released, result])
        print()

    print(
        ascii_table(
            ["release", "expected", "detected", "--release", "result"], rows
        )
    )
    failed = [row for row in rows if row[-1] != "ok"]
    if failed:
        print()
        print(f"{len(failed)} release(s) did not match; see the runs above.")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--installation-path",
        type=pathlib.Path,
        default=None,
        metavar="PATH",
        help=(
            "installation directory (or installation.yaml) to read both "
            "DBURIs from, using the installed soliplex"
        ),
    )
    parser.add_argument(
        "--agui-dburi",
        default=None,
        metavar="URI",
        help="sync DBURI of the thread-persistence (agui) database",
    )
    parser.add_argument(
        "--authz-dburi",
        default=None,
        metavar="URI",
        help="sync DBURI of the authorization (authz) database",
    )
    parser.add_argument(
        "--revision",
        default=None,
        metavar="ID",
        help="stamp this revision instead of the detected one",
    )
    parser.add_argument(
        "--release",
        default=None,
        metavar="X.Y",
        help=(
            "stamp the newest revision introduced at or before this "
            "soliplex release, instead of the detected one"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be stamped, and write nothing",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "verify this script's release-to-revision mapping from "
            "scratch, by rebuilding each past release's schema; touches no "
            "database of yours, and needs 'uv' plus network access"
        ),
    )
    return parser


def chosen_revision(args, inspectors) -> tuple[str, str]:
    """``(revision, how)`` -- the revision to stamp, and why."""
    if args.revision is not None:
        return args.revision, "given by --revision"
    if args.release is not None:
        fingerprint = for_release(args.release)
        return fingerprint.revision, f"newest at v{args.release}"
    fingerprint = detect(inspectors)
    return fingerprint.revision, f"detected from {fingerprint.location}"


def run(args: argparse.Namespace) -> int:
    dburis = resolve_dburis(args)
    engines = {name: sa.create_engine(dburis[name]) for name in DATABASES}
    try:
        inspectors = {name: sa.inspect(engines[name]) for name in DATABASES}
        for name in DATABASES:
            # Flushed: a refusal below goes to stderr, which is unbuffered,
            # and would otherwise be printed ahead of this report.
            print(f"{name}: {redacted(dburis[name])}", flush=True)

        rows = version_rows(engines, inspectors)
        stamped = {name: found for name, found in rows.items() if found}
        if stamped:
            raise AlreadyStamped(stamped)
        for name, found in sorted(rows.items()):
            if found == []:
                print(
                    f"{name}: empty {VERSION_TABLE} table, left by an "
                    "earlier failed upgrade; it will be filled in",
                    flush=True,
                )

        revision, how = chosen_revision(args, inspectors)
        print(f"revision: {revision} ({how})", flush=True)

        if args.dry_run:
            print("dry run: nothing written")
            return 0

        for name in DATABASES:
            stamp(engines[name], revision)
            print(f"stamped {name} at {revision}")
    finally:
        for engine in engines.values():
            engine.dispose()

    print()
    print("Both databases now have a baseline. Apply the migrations with:")
    print("  soliplex-cli database upgrade <installation-path>")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.self_test:
            return self_test()
        return run(args)
    except BootstrapError as exc:
        print(f"bootstrap_alembic_version: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
