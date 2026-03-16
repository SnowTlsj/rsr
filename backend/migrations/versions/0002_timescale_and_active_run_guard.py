"""Add active run uniqueness guard

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-16 09:40:00.000000
"""

from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_runs_single_active ON runs ((ended_at IS NULL)) WHERE ended_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_runs_single_active")
