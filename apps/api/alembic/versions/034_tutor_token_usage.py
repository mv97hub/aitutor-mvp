"""Store one token-usage row per tutor model call.

Revision ID: 034_tutor_token_usage
Revises: 033_kc_message_step
Create Date: 2026-11-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034_tutor_token_usage"
down_revision: Union[str, None] = "033_kc_message_step"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tutor_token_usage",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("kc_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("kc_goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "message_id",
            sa.Uuid(),
            sa.ForeignKey("kc_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("kind IN ('speak', 'answer')", name="ck_tutor_token_usage_kind"),
    )
    op.create_index(
        "ix_tutor_token_usage_student_created",
        "tutor_token_usage",
        ["student_id", "created_at"],
    )
    op.create_index("ix_tutor_token_usage_created_at", "tutor_token_usage", ["created_at"])
    op.create_index("ix_tutor_token_usage_session_id", "tutor_token_usage", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_tutor_token_usage_session_id", table_name="tutor_token_usage")
    op.drop_index("ix_tutor_token_usage_created_at", table_name="tutor_token_usage")
    op.drop_index("ix_tutor_token_usage_student_created", table_name="tutor_token_usage")
    op.drop_table("tutor_token_usage")
