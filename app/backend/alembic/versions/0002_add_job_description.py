"""Add job_description to sessions

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("job_description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "job_description")
