"""soliplex-v0.94

AGUI: delete stored 'THINKING_*' events, which ag-ui-protocol 1.0 removed

Revision ID: 6fc1ea379a76
Revises: e5d2f5ef98a3
Create Date: 2026-11-25 20:42:57

"""

import typing

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6fc1ea379a76"
down_revision: str | typing.Sequence[str] | None = "e5d2f5ef98a3"
branch_labels: str | typing.Sequence[str] | None = None
depends_on: str | typing.Sequence[str] | None = None

# Data only:  'scripts/lint_alembic_chain.py --self-test' steps back over it.
SCHEMA_UNCHANGED = True


# The event types ag-ui-protocol 1.0 removed, frozen here:  1.0 no longer
# defines them, and a revision must not depend on live code anyway.
_THINKING_EVENT_TYPES = (
    "THINKING_START",
    "THINKING_END",
    "THINKING_TEXT_MESSAGE_START",
    "THINKING_TEXT_MESSAGE_CONTENT",
    "THINKING_TEXT_MESSAGE_END",
)


def _thinking_events_where() -> str:
    """Return a SQL condition matching the stored 'THINKING_*' events

    Matches on the prefix of each row's stored text, which 'json.dumps'
    wrote with 'type' first:  '{"type": "THINKING_START", ...'.  The same
    SQL serves SQLite and PostgreSQL, online and offline.
    """
    # Not 'data->>'type'':  a row holding a '\u0000' escape makes every
    # PostgreSQL 'json' operator on it fail (soliplex#1589).
    prefixes = [
        f'{{"type": "{event_type}"' for event_type in _THINKING_EVENT_TYPES
    ]
    return " OR ".join(
        f"substr(CAST(data AS TEXT), 1, {len(prefix)}) = '{prefix}'"
        for prefix in prefixes
    )


def upgrade(engine_name: str) -> None:
    """Upgrade schema."""
    globals()[f"upgrade_{engine_name}"]()


def downgrade(engine_name: str) -> None:
    """Downgrade schema."""
    globals()[f"downgrade_{engine_name}"]()


def upgrade_agui() -> None:
    """Upgrade agui schema:  delete the stored 'THINKING_*' events."""
    op.execute(f"DELETE FROM run_event WHERE {_thinking_events_where()}")


def downgrade_agui() -> None:
    """Downgrade agui schema:  nothing;  deleted events are not restored."""
    pass


def upgrade_authz() -> None:
    """Upgrade authz schema."""
    pass


def downgrade_authz() -> None:
    """Downgrade authz schema."""
    pass
