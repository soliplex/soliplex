"""soliplex-v0.82

Revision ID: b7e2f41c9d05
Revises: a1c7d3e90b42
Create Date: 2026-09-16 10:00:00.000000

Adds the output-token count of a run's *final* model request. That reply
is what the thread now ends with, and the next request carries it as
input -- so 'final_input_tokens' alone reads one reply short of what the
window holds. Nullable for the same reasons as its sibling: existing rows
predate it, and a run that never reached the model has no final request.
"""

import typing

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2f41c9d05"
down_revision: str | typing.Sequence[str] | None = "a1c7d3e90b42"
branch_labels: str | typing.Sequence[str] | None = None
depends_on: str | typing.Sequence[str] | None = None


def upgrade(engine_name: str) -> None:
    """Upgrade schema."""
    globals()[f"upgrade_{engine_name}"]()


def downgrade(engine_name: str) -> None:
    """Downgrade schema."""
    globals()[f"downgrade_{engine_name}"]()


def upgrade_agui() -> None:
    """Upgrade agui schema."""
    op.add_column(
        "run_usage",
        sa.Column("final_output_tokens", sa.Integer(), nullable=True),
    )


def downgrade_agui() -> None:
    """Downgrade agui schema."""
    op.drop_column("run_usage", "final_output_tokens")


def upgrade_authz() -> None:
    """Upgrade authz schema."""
    pass


def downgrade_authz() -> None:
    """Downgrade authz schema."""
    pass
