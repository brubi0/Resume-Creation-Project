"""Widen sessions.status to VARCHAR(50)

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("sessions", "status", type_=sa.String(50), existing_nullable=False)


def downgrade() -> None:
    op.alter_column("sessions", "status", type_=sa.String(20), existing_nullable=False)
