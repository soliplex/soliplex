"""soliplex-v0.80

Revision ID: a1c7d3e90b42
Revises: 63edaa5987f6
Create Date: 2026-09-04 17:05:00.000000

Adds the two columns a client needs to size a context-usage indicator:
the input-token count of a run's *final* model request, and the model id
the provider actually served. Both are nullable -- existing rows predate
them, and a run that never reached the model has no final request.
"""

import typing

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c7d3e90b42"
down_revision: str | typing.Sequence[str] | None = "63edaa5987f6"
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
        sa.Column("final_input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "run_usage",
        sa.Column("resolved_model_name", sa.String(), nullable=True),
    )


def downgrade_agui() -> None:
    """Downgrade agui schema."""
    op.drop_column("run_usage", "resolved_model_name")
    op.drop_column("run_usage", "final_input_tokens")


def upgrade_authz() -> None:
    """Upgrade authz schema."""
    pass


def downgrade_authz() -> None:
    """Downgrade authz schema."""
    pass
