"""soliplex-v0.86

Authz: add 'ACLEntry.permission', with new type 'Permission'

Revision ID: f13fea6c1953
Revises: b7e2f41c9d05
Create Date: 2026-10-20 12:04:57.539891

"""

import typing

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f13fea6c1953"
down_revision: str | typing.Sequence[str] | None = "b7e2f41c9d05"
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
    pass


def downgrade_agui() -> None:
    """Downgrade agui schema."""
    pass


def upgrade_authz() -> None:
    """Upgrade authz schema."""
    # Postgres: 'add_column' does not emit 'CREATE TYPE' the way
    # 'create_table' does
    if op.get_context().dialect.name == "postgresql":
        op.execute("CREATE TYPE permission AS ENUM ('READ', 'WRITE', 'ADMIN')")
    op.add_column(
        "room_acl_entries",
        sa.Column(
            "permission",
            sa.Enum("READ", "WRITE", "ADMIN", name="permission"),
            server_default="READ",
            nullable=False,
        ),
    )


def downgrade_authz() -> None:
    """Downgrade authz schema."""
    op.drop_column("room_acl_entries", "permission")
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TYPE permission")
