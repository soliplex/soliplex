"""The installed distribution's metadata:  what a consumer's resolver sees.

Downstream projects depend on these names ('soliplex[postgres]'), so a
renamed extra, or a driver slipping back into the unconditional
dependencies, breaks them without failing anything else in this suite:
no unit test needs a PostgreSQL driver, so none would notice.
"""

import importlib.metadata

import pytest
from packaging import requirements

POSTGRES_DRIVERS = {"asyncpg", "psycopg", "psycopg-binary"}


def _requirements():
    metadata = importlib.metadata.metadata("soliplex")
    return [
        requirements.Requirement(line)
        for line in metadata.get_all("Requires-Dist")
    ]


def _for_extra(extra):
    """The requirements installed with 'extra', beyond the base set."""
    return {
        req.name: req.extras
        for req in _requirements()
        if req.marker is not None
        and req.marker.evaluate({"extra": extra})
        and not req.marker.evaluate({"extra": ""})
    }


def test_postgres_drivers_are_not_unconditional_dependencies():
    unconditional = {
        req.name
        for req in _requirements()
        if req.marker is None or req.marker.evaluate({"extra": ""})
    }

    assert not unconditional & POSTGRES_DRIVERS


@pytest.mark.parametrize(
    "extra, expected",
    [
        # Pure-Python psycopg over the host's libpq.
        ("postgres", {"psycopg": set(), "asyncpg": set()}),
        # psycopg with its bundled libpq.
        ("postgres-binary", {"psycopg": {"binary"}, "asyncpg": set()}),
    ],
)
def test_postgres_extras(extra, expected):
    found = _for_extra(extra)

    assert found == expected
