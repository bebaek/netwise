"""add users and household memberships

Revision ID: 0006_user_management
Revises: 0005_account_yield_assumptions
Create Date: 2026-07-17 00:00:00.000000

"""
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "0006_user_management"
down_revision: str | Sequence[str] | None = "0005_account_yield_assumptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    users_table = op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    memberships_table = op.create_table(
        "household_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", "user_id", name="uq_household_memberships_household_user"),
    )
    op.create_index(
        "ix_household_memberships_household_id",
        "household_memberships",
        ["household_id"],
    )
    op.create_index("ix_household_memberships_user_id", "household_memberships", ["user_id"])

    bind = op.get_bind()
    existing_household_ids = [
        row[0] if isinstance(row[0], UUID) else UUID(str(row[0]))
        for row in bind.execute(sa.text("select id from households")).all()
    ]
    if existing_household_ids:
        now = datetime.now(UTC)
        local_user_id = uuid4()
        op.bulk_insert(
            users_table,
            [
                {
                    "id": local_user_id,
                    "display_name": "Local User",
                    "email": None,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )
        op.bulk_insert(
            memberships_table,
            [
                {
                    "id": uuid4(),
                    "household_id": household_id,
                    "user_id": local_user_id,
                    "role": "owner",
                    "created_at": now,
                }
                for household_id in existing_household_ids
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_household_memberships_user_id", table_name="household_memberships")
    op.drop_index("ix_household_memberships_household_id", table_name="household_memberships")
    op.drop_table("household_memberships")
    op.drop_table("users")
