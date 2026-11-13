"""soliplex-v0.93

AGUI: add 'Thread.text_search', a full-text search vector, with a GIN
index on PostgreSQL only

Revision ID: e5d2f5ef98a3
Revises: 98cd91f27cb5
Create Date: 2026-11-13 13:11:30.391459

"""

import typing

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5d2f5ef98a3"
down_revision: str | typing.Sequence[str] | None = "98cd91f27cb5"
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
        "thread",
        sa.Column(
            "text_search",
            postgresql.TSVECTOR().with_variant(sa.Text(), "sqlite"),
            nullable=True,
        ),
    )
    # Autogenerate drops the model's 'ddl_if': without this branch,
    # SQLite would get a plain index the models do not declare.
    if op.get_context().dialect.name == "postgresql":
        op.create_index(
            "ix_thread_text_search",
            "thread",
            ["text_search"],
            unique=False,
            postgresql_using="gin",
        )


def downgrade_agui() -> None:
    """Downgrade agui schema."""
    if op.get_context().dialect.name == "postgresql":
        op.drop_index(
            "ix_thread_text_search",
            table_name="thread",
            postgresql_using="gin",
        )
    op.drop_column("thread", "text_search")


def upgrade_authz() -> None:
    """Upgrade authz schema."""
    pass


def downgrade_authz() -> None:
    """Downgrade authz schema."""
    pass
