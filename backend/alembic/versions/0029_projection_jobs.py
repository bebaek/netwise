"""add durable projection jobs

Revision ID: 0029_projection_jobs
Revises: 0028_api_token_audit_events
Create Date: 2026-08-31 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0029_projection_jobs"
down_revision: str | Sequence[str] | None = "0028_api_token_audit_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projection_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("algorithm_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("request", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["projection_scenarios.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'stale')",
            name="ck_projection_jobs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_projection_jobs_household_status",
        "projection_jobs",
        ["household_id", "status"],
    )
    op.create_index("ix_projection_jobs_expires_at", "projection_jobs", ["expires_at"])
    op.create_index(
        "ix_projection_jobs_cache_completed",
        "projection_jobs",
        ["cache_key", "completed_at"],
    )
    op.create_index(
        "uq_projection_jobs_active_cache_key",
        "projection_jobs",
        ["cache_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_projection_jobs_active_cache_key", table_name="projection_jobs")
    op.drop_index("ix_projection_jobs_cache_completed", table_name="projection_jobs")
    op.drop_index("ix_projection_jobs_expires_at", table_name="projection_jobs")
    op.drop_index("ix_projection_jobs_household_status", table_name="projection_jobs")
    op.drop_table("projection_jobs")
