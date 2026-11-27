"""Document generation state on sessions; kind/posting on deliverables

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("generation_status", sa.String(20), nullable=False, server_default="idle"),
    )
    op.add_column("sessions", sa.Column("generation_error", sa.Text(), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("generation_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "deliverables",
        sa.Column("kind", sa.String(20), nullable=False, server_default="base"),
    )
    op.add_column("deliverables", sa.Column("posting_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_deliverables_posting_id", "deliverables", "postings",
        ["posting_id"], ["id"], ondelete="SET NULL",
    )
    # Rows created before this migration default to 'base'; targeted documents were
    # never base documents, so classify them (regeneration must not delete them).
    op.execute(
        "UPDATE deliverables SET kind='targeted' WHERE type IN "
        "('resume_targeted_md','resume_targeted_docx','cover_letter_md','cover_letter_docx')"
    )


def downgrade() -> None:
    op.drop_constraint("fk_deliverables_posting_id", "deliverables", type_="foreignkey")
    op.drop_column("deliverables", "posting_id")
    op.drop_column("deliverables", "kind")
    op.drop_column("sessions", "generation_started_at")
    op.drop_column("sessions", "generation_error")
    op.drop_column("sessions", "generation_status")
