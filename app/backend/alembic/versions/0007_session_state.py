"""Session turn state, message status/idempotency key, resume draft columns

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "sessions",
        sa.Column("turn_state", sa.String(20), nullable=False, server_default="idle"),
    )
    op.add_column(
        "sessions", sa.Column("turn_started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("sessions", sa.Column("resume_draft", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("approved_resume", sa.Text(), nullable=True))
    # Interviews already under way predate question ids and RESUME markers: mark them so the
    # new completion rules don't strand them (they finish the old way).
    op.add_column(
        "sessions",
        sa.Column("legacy_flow", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute("UPDATE sessions SET legacy_flow = true")
    op.add_column(
        "messages",
        sa.Column("status", sa.String(20), nullable=False, server_default="ok"),
    )
    op.add_column("messages", sa.Column("client_message_id", UUID(as_uuid=True), nullable=True))
    op.create_index(
        "uq_messages_session_client_message",
        "messages",
        ["session_id", "client_message_id"],
        unique=True,
        postgresql_where=sa.text("client_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_messages_session_client_message", table_name="messages")
    op.drop_column("messages", "client_message_id")
    op.drop_column("messages", "status")
    op.drop_column("sessions", "legacy_flow")
    op.drop_column("sessions", "approved_resume")
    op.drop_column("sessions", "resume_draft")
    op.drop_column("sessions", "turn_started_at")
    op.drop_column("sessions", "turn_state")
    op.drop_column("sessions", "version")
