#!/usr/bin/env python
"""Check that the alembic chain reproduces the models.

Any writable open of the ``agui`` or ``authz`` databases migrates them
via ``alembic`` to the current ``head`` revision  (see
``soliplex.alembic_migrations``). Such a migration is only safe
if migrating an empty database from base produces exactly what the models
would have created.

This script flags schema changes (an omitted column, a model changed without
a revision) which would break that invariant silently.

It builds both databases into throwaway SQLite files, and compares them
structurally: tables, columns (name, type, nullability, default, order),
primary keys, unique constraints, foreign keys, indexes and CHECK
constraints.

The ``alembic_version`` is marker ignored -- only the migrated side has
one, by design.

Usage::

    uv run python scripts/lint_alembic_chain.py [--verbose]
    uv run python scripts/lint_alembic_chain.py --self-test

``--self-test`` migrates to the revision *before* head instead, and requires
the comparison to fail: the newest revision changes the schema, so a
comparator that reports no difference there is blind, and would pass this
check no matter what difference exists.

.. note::

  a head revision that changes no schema at all -- a data-only migration --
  would make the self-test fail; say so in the commit rather than weakening
  the check.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import tempfile

import sqlalchemy as sa
from alembic import script as alembic_script

from soliplex import alembic_migrations
from soliplex.agui import schema as agui_schema
from soliplex.authz import schema as authz_schema

METADATA = {
    alembic_migrations.AGUI: agui_schema.metadata,
    alembic_migrations.AUTHZ: authz_schema.metadata,
}
IGNORED_TABLES = {alembic_migrations.VERSION_TABLE}
ASPECTS = ("columns", "pk", "unique", "fks", "indexes", "checks")


def _shape(dburi: str) -> dict:
    """Every structural detail of a database, as plain data."""
    engine = sa.create_engine(dburi)
    try:
        inspector = sa.inspect(engine)
        tables = set(inspector.get_table_names()) - IGNORED_TABLES
        shape = {}
        for table in sorted(tables):
            pk = inspector.get_pk_constraint(table)
            shape[table] = {
                "columns": [
                    (
                        column["name"],
                        str(column["type"]),
                        bool(column["nullable"]),
                        str(column.get("default")),
                    )
                    for column in inspector.get_columns(table)
                ],
                "pk": (
                    pk.get("name"),
                    tuple(pk.get("constrained_columns", ())),
                ),
                "unique": sorted(
                    (u.get("name"), tuple(u.get("column_names", ())))
                    for u in inspector.get_unique_constraints(table)
                ),
                "fks": sorted(
                    (
                        f.get("name"),
                        tuple(f.get("constrained_columns", ())),
                        f.get("referred_table"),
                        tuple(f.get("referred_columns", ())),
                    )
                    for f in inspector.get_foreign_keys(table)
                ),
                "indexes": sorted(
                    (
                        i.get("name"),
                        tuple(i.get("column_names", ())),
                        bool(i.get("unique")),
                    )
                    for i in inspector.get_indexes(table)
                ),
                "checks": sorted(
                    (c.get("name"), c.get("sqltext"))
                    for c in inspector.get_check_constraints(table)
                ),
            }
        return shape
    finally:
        engine.dispose()


def _differences(migrated: dict, declared: dict) -> list[str]:
    """Human-readable differences between two shapes, empty when equal."""
    found = []
    for table in sorted(set(migrated) - set(declared)):
        found.append(f"{table}: only the migrated schema has this table")
    for table in sorted(set(declared) - set(migrated)):
        found.append(f"{table}: no revision creates this table")
    for table in sorted(set(migrated) & set(declared)):
        for aspect in ASPECTS:
            left, right = migrated[table][aspect], declared[table][aspect]
            if left == right:
                continue
            found.append(f"{table}.{aspect}:")
            found.append(f"    migrated: {left}")
            found.append(f"    declared: {right}")
    return found


def _dburis(directory: pathlib.Path, suffix: str) -> dict[str, str]:
    return {
        name: f"sqlite:///{directory / f'{name}-{suffix}.sqlite'}"
        for name in alembic_migrations.DATABASE_NAMES
    }


def _build_declared(dburis: dict[str, str]) -> None:
    """Create each schema the way the models declare it."""
    for name, dburi in dburis.items():
        engine = sa.create_engine(dburi)
        try:
            with engine.begin() as connection:
                METADATA[name].create_all(connection)
        finally:
            engine.dispose()


def penultimate_revision() -> str | None:
    """The revision before head, or ``None`` when head is the baseline."""
    directory = alembic_script.ScriptDirectory(str(alembic_migrations.TREE))
    head = directory.get_revision(directory.get_current_head())
    return head.down_revision


def compare(revision: str, *, verbose: bool = False) -> list[str]:
    """Differences between migrating to ``revision`` and the models."""
    with tempfile.TemporaryDirectory(prefix="alembic-chain-") as raw:
        directory = pathlib.Path(raw)
        migrated = _dburis(directory, "migrated")
        declared = _dburis(directory, "declared")

        if verbose:
            print(f"migrating an empty database to {revision}")
        alembic_migrations.upgrade(revision, dburis=migrated)

        if verbose:
            print("creating the same schema from the models")
        _build_declared(declared)

        found = []
        for name in alembic_migrations.DATABASE_NAMES:
            differences = _differences(
                _shape(migrated[name]), _shape(declared[name])
            )
            found += [f"{name}: {line}" for line in differences]
            if verbose and not differences:
                print(f"{name}: identical")
        return found


def self_test(verbose: bool = False) -> int:
    """Require the comparison to notice what the newest revision changes."""
    previous = penultimate_revision()
    if previous is None:
        print(
            "lint_alembic_chain: self-test needs at least two revisions",
            file=sys.stderr,
        )
        return 1

    found = compare(previous, verbose=verbose)
    if not found:
        print(
            "lint_alembic_chain: self-test FAILED -- migrating to "
            f"{previous} (one before head) matched the models, so this "
            "check cannot see what the newest revision does, and would "
            "pass whatever difference exists",
            file=sys.stderr,
        )
        return 1

    if verbose:
        print(
            f"self-test OK: stopping at {previous} differs from the models "
            f"in {len(found)} way(s), as it must"
        )
    return 0


def check(verbose: bool = False) -> int:
    """Require migrating to head to reproduce the models exactly."""
    found = compare("head", verbose=verbose)
    if found:
        print(
            "lint_alembic_chain: the migrated schema does not match the "
            "models. Either a revision is missing a change the models "
            "make, or a model changed without one:",
            file=sys.stderr,
        )
        for line in found:
            print(f"  {line}", file=sys.stderr)
        return 1

    if verbose:
        print("the chain reproduces the models exactly")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="say what is being built and compared",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "check the comparison itself, by stopping one revision short "
            "of head, where it must report a difference"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        return self_test(args.verbose)
    return check(args.verbose)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
